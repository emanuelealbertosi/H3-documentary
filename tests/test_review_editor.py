import copy
import hashlib
import json
import threading
from concurrent.futures import Future

import pytest
from fastapi.testclient import TestClient

from app import presentations, review_editor, runner, store
from app.models import ProjectRequest
from app.server import app


@pytest.fixture
def job(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA", tmp_path)
    monkeypatch.setattr(store, "JOBS", tmp_path / "jobs")
    (tmp_path / "jobs").mkdir()
    store.init()
    project = store.create(ProjectRequest(topic="Revisione del racconto", start=False))
    pid = project["id"]
    store.update(pid, status="review")
    pack = {"schema_version": 2, "documentary_type": "exploration", "slug": "prova",
            "locations": [{"id": "rome", "name": "Roma", "pos": [12.5, 41.9]},
                          {"id": "athens", "name": "Atene", "pos": [23.7, 37.9]}],
            "events": [{"id": "arrival", "location_id": "rome"}],
            "scenes": [{"id": "01", "title": "Partenza", "date": "Un periodo storico",
                        "location_ids": ["athens"], "lines": ["Il viaggio inizia ad Atene.", "Il racconto prosegue."]},
                       {"id": "02", "title": "Arrivo", "event_ids": ["arrival"], "lines": ["Il viaggio arriva a Roma."]}],
            "sources": [{"id": "source", "url": "https://example.org", "title": "Fonte conservata"}]}
    path = store.JOBS / pid / "workspace/documentaries/prova/documentary.json"
    store.write_json(path, pack)
    monkeypatch.setattr(runner, "FUTURES", {})
    monkeypatch.setattr(presentations, "FUTURES", {})
    monkeypatch.setattr(presentations, "STOPPING", False)
    client = TestClient(app)
    client.headers["X-DocumentariAI"] = "studio"
    return pid, path, pack, client


def url(pid):
    return f"/api/projects/{pid}/editorial-review"


def save(job, **changes):
    pid, _, _, client = job
    state = client.get(url(pid)).json()
    return client.put(url(pid), json={"revision": state["revision"], **changes})


def test_get_legacy_and_generic_editor_without_changing_pack(job):
    pid, path, pack, client = job
    original = hashlib.sha256(path.read_bytes()).hexdigest()
    state = client.get(url(pid)).json()
    assert state["available"] and state["editable"] and not state["dirty"]
    assert state["scenes"][0]["lines"] == pack["scenes"][0]["lines"]
    assert state["places"][0]["scene_ids"] == ["02"]
    assert state["places"][1]["scene_ids"] == ["01"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == original
    assert not (path.parents[3] / "checkpoints/editorial-review.json").exists()
    old = copy.deepcopy(pack)
    old["schema_version"] = 1
    old["places"] = {p["id"]: p for p in old.pop("locations")}
    old["scenes"][0]["visible_places"] = old["scenes"][0].pop("location_ids")
    battle_path = path.parents[2] / "battles/prova/battle.json"
    store.write_json(battle_path, old)
    path.unlink()
    state = client.get(url(pid)).json()
    assert state["editable"] and len(state["places"]) == 2
    assert state["places"][1]["scene_ids"] == ["01"]


def test_sparse_save_is_a_draft_preserves_cues_and_can_restore_original(job):
    pid, path, pack, client = job
    original = path.read_bytes()
    changed = ["Da Atene prende avvio il viaggio.", "La seconda frase rimane associata alla sua animazione."]
    result = save(job, scenes=[{"id": "01", "lines": changed}])
    assert result.status_code == 200
    state = result.json()
    assert state["dirty"] and state["changed_scene_ids"] == ["01"]
    result = save(job, places=[{"id": "rome", "pos": [12.48, 41.89]}])
    assert result.status_code == 200
    assert result.json()["scenes"][0]["lines"] == changed
    assert result.json()["scenes"][0]["base_lines"] == pack["scenes"][0]["lines"]
    assert result.json()["places"][0]["base_pos"] == [12.5, 41.9]
    assert result.json()["changed_place_ids"] == ["rome"]
    assert path.read_bytes() == original
    draft = review_editor.pending(pid, pack)
    assert draft["scenes"] == [{"id": "01", "lines": changed}]
    assert draft["places"] == [{"id": "rome", "pos": [12.48, 41.89]}]
    assert draft["base_fingerprint"] == review_editor.fingerprint(pack)
    result = save(job, scenes=[{"id": "01", "lines": pack["scenes"][0]["lines"]}],
                  places=[{"id": "rome", "pos": [12.5, 41.9]}])
    assert result.status_code == 200 and not result.json()["dirty"]
    assert review_editor.pending(pid, pack) is None
    assert path.read_bytes() == original


@pytest.mark.parametrize("pos", [[180, 0], [0, 79], [-179.1, 0], [0, -78.1], [0], [0, 0, 0], [True, 1], ["12", 0], [None, 0]])
def test_invalid_coordinates_are_rejected_without_any_write(job, pos):
    pid, path, _, _ = job
    original = path.read_bytes()
    result = save(job, places=[{"id": "rome", "pos": pos}])
    assert result.status_code == 422
    assert not review_editor._path(pid).exists() and path.read_bytes() == original


def test_nonfinite_coordinates_and_long_payloads_fail_schema():
    for value in (float("inf"), float("-inf"), float("nan")):
        with pytest.raises(ValueError, match="Coordinate"):
            review_editor.PlaceEdit(id="rome", pos=[value, 0])
    with pytest.raises(ValueError, match="500.000"):
        review_editor.EditorialEdit(revision="0" * 64, scenes=[{"id": "01", "lines": ["x" * 8000] * 63}])


@pytest.mark.parametrize("changes,status", [
    ({"scenes": [{"id": "01", "lines": ["Una sola frase."]}]}, 400),
    ({"scenes": [{"id": "unknown", "lines": ["Una frase."]}]}, 400),
    ({"places": [{"id": "unknown", "pos": [0, 0]}]}, 400),
    ({"scenes": [{"id": "01", "lines": [" ", "Una frase."]}]}, 422),
    ({"scenes": [{"id": "01", "lines": ["x" * 8001, "Una frase."]}]}, 422),
    ({"scenes": [{"id": "01", "lines": [42, "Una frase."]}]}, 422),
    ({"places": [{"id": "rome", "pos": [0, 0]}, {"id": "rome", "pos": [1, 1]}]}, 422),
    ({"scenes": [{"id": "02", "lines": ["Prima."]}, {"id": "02", "lines": ["Seconda."]}]}, 422),
])
def test_invalid_editorial_edits_leave_original_and_draft_unchanged(job, changes, status):
    pid, path, _, _ = job
    original = path.read_bytes()
    assert save(job, **changes).status_code == status
    assert path.read_bytes() == original and not review_editor._path(pid).exists()


def test_revision_conflict_prevents_lost_updates_and_visual_edits_do_not_stale_draft(job):
    pid, path, pack, client = job
    before = client.get(url(pid)).json()["revision"]
    changed = save(job, places=[{"id": "rome", "pos": [12.48, 41.89]}]).json()
    conflict = client.put(url(pid), json={"revision": before, "places": [{"id": "athens", "pos": [0, 0]}]})
    assert conflict.status_code == 409
    visual_pack = copy.deepcopy(pack)
    visual_pack["visual_slots"] = [{"id": "image", "enabled": False}]
    visual_pack["scenes"][0]["image_insets"] = [{"asset_id": "new"}]
    store.write_json(path, visual_pack)
    assert client.get(url(pid)).json()["revision"] == changed["revision"]
    assert review_editor.pending(pid, visual_pack)["places"] == [{"id": "rome", "pos": [12.48, 41.89]}]
    visual_pack["scenes"][0]["lines"][0] = "Un racconto nuovo."
    store.write_json(path, visual_pack)
    state = client.get(url(pid)).json()
    assert not state["editable"] and "cambiate" in state["reason"]
    with pytest.raises(ValueError, match="cambiate"):
        review_editor.pending(pid, visual_pack)


@pytest.mark.parametrize("status", ["draft", "queued", "running", "failed", "cancelled", "completed"])
def test_editor_is_read_only_outside_review(job, status):
    pid, path, _, client = job
    store.update(pid, status=status)
    state = client.get(url(pid)).json()
    assert state["available"] and not state["editable"] and state["scenes"]
    result = client.put(url(pid), json={"revision": state["revision"], "places": [{"id": "rome", "pos": [0, 0]}]})
    assert result.status_code == 409
    assert not review_editor._path(pid).exists()


def test_active_worker_and_pdf_export_block_editor(job):
    pid, _, _, client = job
    future = Future()
    runner.FUTURES[pid] = future
    state = client.get(url(pid)).json()
    assert not state["editable"] and "motore" in state["reason"]
    assert client.put(url(pid), json={"revision": state["revision"]}).status_code == 409
    future.set_result(None)
    presentations.FUTURES[pid] = Future()
    state = client.get(url(pid)).json()
    assert not state["editable"] and "PDF" in state["reason"]
    assert client.put(url(pid), json={"revision": state["revision"]}).status_code == 409


def test_two_simultaneous_writes_share_locks_and_only_one_revision_wins(job):
    pid, _, _, client = job
    revision = client.get(url(pid)).json()["revision"]
    barrier = threading.Barrier(2)
    results = []
    def writer(position):
        own_client = TestClient(app)
        barrier.wait(timeout=3)
        response = own_client.put(url(pid), headers={"X-DocumentariAI": "studio"},
                                 json={"revision": revision, "places": [{"id": "rome", "pos": position}]})
        results.append(response.status_code)
    threads = [threading.Thread(target=writer, args=(point,)) for point in ([12.48, 41.89], [12.49, 41.88])]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
    assert all(not thread.is_alive() for thread in threads)
    assert sorted(results) == [200, 409]
    assert client.get(url(pid)).json()["dirty"]


def test_successful_application_keeps_audit_and_cannot_clear_a_newer_draft(job):
    pid, path, pack, _ = job
    result = save(job, places=[{"id": "rome", "pos": [12.48, 41.89]}]).json()
    original = path.read_bytes()
    with pytest.raises(ValueError, match="Nessuna bozza"):
        review_editor.mark_applied(pid, {"revision": "0" * 64})
    assert review_editor.pending(pid, pack)
    audit = review_editor.mark_applied(pid, {"revision": result["revision"], "changed_place_ids": ["rome"]})
    assert audit.is_file() and review_editor.pending(pid, pack) is None
    assert store.read_json(audit)["draft"]["places"] == [{"id": "rome", "pos": [12.48, 41.89]}]
    assert path.read_bytes() == original


def test_no_pack_and_unknown_project_are_explicit(job):
    pid, path, _, client = job
    path.unlink()
    state = client.get(url(pid)).json()
    assert not state["available"] and not state["editable"] and state["reason"]
    assert client.get(url("unknown")).status_code == 404
