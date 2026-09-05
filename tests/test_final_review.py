import hashlib
import sys
import threading
from concurrent.futures import Future
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import final_review, presentations, review_editor, runner, store
from app.models import ProjectRequest
from app.server import app


@pytest.fixture
def job(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA", tmp_path)
    monkeypatch.setattr(store, "JOBS", tmp_path / "jobs")
    monkeypatch.setattr(runner, "JOBS", tmp_path / "jobs")
    monkeypatch.setattr(runner, "FUTURES", {})
    monkeypatch.setattr(runner, "FLAGS", {})
    monkeypatch.setattr(presentations, "FUTURES", {})
    monkeypatch.setattr(presentations, "STOPPING", False)
    (tmp_path / "jobs").mkdir()
    store.init()
    project = store.create(ProjectRequest(topic="Revisione del film completato", start=False))
    pid = project["id"]
    store.update(pid, status="completed", progress=100, stage="Documentario completato",
                 result={"sha256": "previous-film", "duration": 90}, processing_seconds=12)
    root = store.JOBS / pid
    pack = {"schema_version": 2, "documentary_type": "general_history", "slug": "example",
            "locations": [{"id": "rome", "name": "Roma", "pos": [12.5, 41.9]}],
            "scenes": [{"id": "01", "title": "Il luogo", "lines": ["Questa è Roma."], "location_ids": ["rome"]}]}
    store.write_json(root / "workspace/documentaries/example/documentary.json", pack)
    store.write_json(root / "checkpoints/verify.done.json", {"done": True})
    store.write_json(root / "workspace/timeline.json", {"scenes": []})
    output = root / "workspace/output"
    output.mkdir()
    (output / "film.mp4").write_bytes(b"previous verified film")
    (output / "presentations").mkdir()
    (output / "presentations/original.pdf").write_bytes(b"previous exported presentation")
    client = TestClient(app)
    client.headers["X-DocumentariAI"] = "studio"
    monkeypatch.setattr(runner, "POOL", SimpleNamespace(submit=lambda *args: Future()))
    monkeypatch.setitem(sys.modules, "app.final_review_worker", SimpleNamespace(run_revision=lambda *args: None))
    return pid, root, client


def endpoint(pid):
    return f"/api/projects/{pid}/final-review"


def queue(job):
    pid, root, client = job
    assert client.post(endpoint(pid)).status_code == 200
    result = client.post(endpoint(pid) + "/render")
    assert result.status_code == 202, result.text
    return final_review.read(pid)["revision_id"]


def digest_tree(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


def test_open_completed_review_same_identity_and_optional_draft(job):
    pid, root, client = job
    before = store.project(pid)
    immutable = digest_tree(root / "workspace")
    assert not client.get(f"/api/projects/{pid}/editorial-review").json()["editable"]
    response = client.post(endpoint(pid))
    assert response.status_code == 200 and response.json()["editing"]
    state = client.get(f"/api/projects/{pid}/editorial-review").json()
    assert state["editable"]
    saved = client.put(f"/api/projects/{pid}/editorial-review", json={"revision": state["revision"],
        "scenes": [{"id": "01", "lines": ["Un testo corretto per Roma."]}]})
    assert saved.status_code == 200 and saved.json()["dirty"]
    assert client.post(endpoint(pid)).json()["editing"]
    after = store.project(pid)
    assert all(after[key] == before[key] for key in ("id", "family_id", "version", "parent_id", "result", "status"))
    assert len(store.projects()) == 1
    assert digest_tree(root / "workspace") == immutable


def test_discard_restores_project_drafts_and_keeps_shared_library(job):
    pid, root, client = job
    baseline = {"slots": {"original": False}, "layouts": {}}
    store.write_json(root / "checkpoints/visual-options.json", baseline)
    assert client.post(endpoint(pid)).status_code == 200
    state = review_editor.state(pid)
    review_editor.put_review(pid, review_editor.EditorialEdit(revision=state["revision"], scenes=[{"id": "01", "lines": ["Testo nuovo."]}]))
    store.write_json(root / "checkpoints/visual-options.json", {"slots": {"new": True}})
    library = store.DATA / "media" / "kept.json"
    store.write_json(library, {"image": "global reusable asset"})
    result = client.delete(endpoint(pid))
    assert result.status_code == 200 and not result.json()["editing"]
    assert not (root / "checkpoints/editorial-review.json").exists()
    assert store.read_json(root / "checkpoints/visual-options.json") == baseline
    assert library.is_file()
    assert store.project(pid)["status"] == "completed"


@pytest.mark.parametrize("status", ["draft", "running", "review", "failed", "interrupted"])
def test_only_completed_projects_can_open_final_review(job, status):
    pid, _, client = job
    store.update(pid, status=status)
    assert client.post(endpoint(pid)).status_code == 409
    assert not final_review.read(pid)


def test_render_requires_open_review_and_never_calls_full_pipeline(job):
    pid, _, client = job
    assert client.post(endpoint(pid) + "/render").status_code == 409
    assert client.post(endpoint(pid)).status_code == 200
    response = client.post(f"/api/projects/{pid}/start")
    assert response.status_code == 409 and "Aggiorna" in response.json()["detail"]


def test_busy_revision_blocks_mutation_and_keeps_previous_video_readable(job, monkeypatch):
    pid, root, client = job
    import app.server as server
    monkeypatch.setattr(server, "JOBS", store.JOBS)
    queue(job)
    assert final_review.status(pid)["busy"]
    for method, path in (("post", endpoint(pid)), ("delete", endpoint(pid)),
                         ("post", f"/api/projects/{pid}/regenerate"), ("delete", f"/api/projects/{pid}")):
        assert getattr(client, method)(path).status_code == 409
    assert not review_editor.state(pid)["editable"]
    assert not presentations.status(pid)["available"]
    result = client.get(f"/api/projects/{pid}/file", params={"path": "workspace/output/film.mp4"})
    assert result.status_code == 200 and result.content == b"previous verified film"


def test_candidate_copies_preserve_old_movie_pdf_and_independent_mutable_files(job):
    pid, root, _ = job
    rid = queue(job)
    old = digest_tree(root / "workspace")
    candidate = final_review.prepare_candidate(pid, rid)
    assert digest_tree(candidate / "workspace") == old
    path = candidate / "workspace/output/film.mp4"
    path.write_bytes(b"new candidate film")
    assert (root / "workspace/output/film.mp4").read_bytes() == b"previous verified film"
    assert (candidate / "workspace/output/presentations/original.pdf").is_file()
    assert not (candidate / "final-revisions").exists()


def test_publication_requires_verified_matching_revision(job):
    pid, root, _ = job
    rid = queue(job)
    candidate = final_review.prepare_candidate(pid, rid)
    old = digest_tree(root / "workspace")
    for report in ({"revision_id": rid, "verified": False}, {"revision_id": "other", "verified": True}):
        with pytest.raises(ValueError):
            final_review.publish(pid, candidate, report)
    assert digest_tree(root / "workspace") == old


def test_successful_publication_updates_same_project_and_retains_backup(job):
    pid, root, _ = job
    original = store.project(pid)
    rid = queue(job)
    candidate = final_review.prepare_candidate(pid, rid)
    (candidate / "workspace/output/film.mp4").write_bytes(b"new verified film")
    final_review.publish(pid, candidate, {"revision_id": rid, "verified": True,
        "changed_scene_ids": ["01"], "result": {"sha256": "new-sha", "duration": 91}})
    current = store.project(pid)
    assert all(current[key] == original[key] for key in ("id", "family_id", "version", "parent_id"))
    assert current["status"] == "completed" and current["result"]["sha256"] == "new-sha"
    assert current["processing_seconds"] >= 12
    assert (root / "workspace/output/film.mp4").read_bytes() == b"new verified film"
    assert (candidate.parent / "previous/workspace/output/film.mp4").read_bytes() == b"previous verified film"
    assert (root / "workspace/output/presentations/original.pdf").is_file()
    assert final_review.read(pid)["revision_number"] == 1
    assert len(store.projects()) == 1
    final_review.finish_failure(pid, rid, "Errore successivo nel diario")
    assert store.project(pid)["result"]["sha256"] == "new-sha"
    assert final_review.read(pid)["status"] == "completed"


def test_directory_swap_failure_rolls_back_every_public_file(job, monkeypatch):
    pid, root, _ = job
    rid = queue(job)
    candidate = final_review.prepare_candidate(pid, rid)
    old_work = digest_tree(root / "workspace")
    old_cp = digest_tree(root / "checkpoints")
    (candidate / "workspace/output/film.mp4").write_bytes(b"unverified replacement")
    rename = Path.rename
    def failing(self, target):
        if self == candidate / "checkpoints":
            raise OSError("simulated Windows directory lock")
        return rename(self, target)
    monkeypatch.setattr(Path, "rename", failing)
    with pytest.raises(OSError, match="directory lock"):
        final_review.publish(pid, candidate, {"revision_id": rid, "verified": True})
    assert digest_tree(root / "workspace") == old_work
    assert digest_tree(root / "checkpoints") == old_cp
    assert store.project(pid)["status"] == "completed"
    assert store.project(pid)["result"]["sha256"] == "previous-film"


def test_failed_candidate_keeps_editable_draft_and_allows_retry_without_version(job):
    pid, root, client = job
    rid = queue(job)
    runner.FUTURES[pid].set_result(None)
    final_review.finish_failure(pid, rid, "Errore simulato della verifica")
    state = final_review.status(pid)
    assert state["editing"] and not state["busy"] and state["error"]
    assert store.project(pid)["status"] == "completed"
    assert client.post(endpoint(pid) + "/render").status_code == 202
    assert final_review.read(pid)["revision_id"] != rid
    assert len(store.projects()) == 1


def test_cancel_queued_revision_restores_completed_film_and_retains_drafts(job):
    pid, root, client = job
    queue(job)
    response = client.post(f"/api/projects/{pid}/cancel")
    assert response.status_code == 200
    assert store.project(pid)["status"] == "completed"
    assert final_review.status(pid)["status"] == "cancelled"
    assert final_review.status(pid)["editing"]
    assert (root / "workspace/output/film.mp4").read_bytes() == b"previous verified film"


def test_restart_recovers_interrupted_publication_to_previous_film(job):
    pid, root, _ = job
    rid = queue(job)
    candidate = final_review.prepare_candidate(pid, rid)
    (candidate / "workspace/output/film.mp4").write_bytes(b"new film not yet committed")
    previous = candidate.parent / "previous"
    previous.mkdir()
    (root / "workspace").rename(previous / "workspace")
    (candidate / "workspace").rename(root / "workspace")
    final_review.set_state(pid, status="publishing")
    runner.FUTURES.clear()
    store.init()
    final_review.recover()
    assert store.project(pid)["status"] == "completed"
    assert (root / "workspace/output/film.mp4").read_bytes() == b"previous verified film"
    assert final_review.status(pid)["editing"]
    assert not final_review.status(pid)["busy"]


def test_pdf_export_prevents_open_and_publish(job):
    pid, _, client = job
    presentations.FUTURES[pid] = Future()
    assert client.post(endpoint(pid)).status_code == 409
    presentations.FUTURES[pid].set_result(None)
    rid = queue(job)
    candidate = final_review.prepare_candidate(pid, rid)
    presentations.FUTURES[pid] = Future()
    with pytest.raises(ValueError, match="PDF"):
        final_review.publish(pid, candidate, {"revision_id": rid, "verified": True})


def test_media_request_snapshot_preserves_bytes_after_library_changes(job):
    pid, _, client = job
    from app import media
    ident = "a" * 24
    image = media.folder(ident) / "image.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"original local asset")
    store.write_json(image.parent / "record.json", {"id": ident, "title": "Roma", "created": store.now()})
    rid = queue(job)
    snapshot = final_review.request_snapshot(pid, rid)
    image.write_bytes(b"library changed later")
    media.remove(ident)
    frozen = final_review.staging_root(pid, rid).parent / "media" / ident / "image.png"
    assert frozen.read_bytes() == b"original local asset"
    assert snapshot["media_records"][0]["title"] == "Roma"
    assert snapshot["original_result"]["sha256"] == "previous-film"


def test_cancel_running_revision_uses_flag_and_failure_restores_original(job, monkeypatch):
    pid, root, client = job
    rid = queue(job)
    runner.FUTURES[pid].set_running_or_notify_cancel()
    stopped = []
    monkeypatch.setattr(runner, "stop_process", lambda project_id: stopped.append(project_id))
    assert client.post(f"/api/projects/{pid}/cancel").status_code == 200
    assert runner.FLAGS[pid].is_set() and stopped == [pid]
    assert final_review.status(pid)["status"] == "cancelling"
    final_review.finish_failure(pid, rid, "", cancelled=True)
    runner.FUTURES[pid].set_result(None)
    assert store.project(pid)["status"] == "completed"
    assert (root / "workspace/output/film.mp4").read_bytes() == b"previous verified film"
    assert client.post(f"/api/projects/{pid}/cancel").json()["status"] == "completed"


def test_cancel_flag_prevents_publication_even_after_verification(job):
    pid, root, _ = job
    rid = queue(job)
    candidate = final_review.prepare_candidate(pid, rid)
    runner.FLAGS[pid].set()
    with pytest.raises(runner.Cancelled):
        final_review.publish(pid, candidate, {"revision_id": rid, "verified": True})
    assert (root / "workspace/output/film.mp4").read_bytes() == b"previous verified film"
