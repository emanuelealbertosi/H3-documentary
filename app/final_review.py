"""Optional revisions of a completed film, published only after verification.

The public workspace is never a worker's scratch directory. A small journal
allows the previous completed film to be restored after interrupted publication.
"""
from __future__ import annotations

import copy
import re
import shutil
import threading
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException

from . import store
from .presentations import project_mutation

router = APIRouter(prefix="/api/projects")
BUSY = {"queued", "running", "cancelling", "publishing"}
EDITING = {"editing", "failed", "cancelled", "interrupted"}
DRAFT_FILES = ("editorial-review.json", "visual-options.json")


def _folder(pid):
    store.project(pid)
    root = store.JOBS.resolve()
    folder = (root / pid).resolve()
    if folder.parent != root:
        raise ValueError("Progetto non valido.")
    return folder


def state_path(pid):
    return _folder(pid) / "final-review.json"


def read(pid):
    path = state_path(pid)
    data = store.read_json(path) if path.is_file() else {}
    if not isinstance(data, dict):
        raise ValueError("Lo stato della revisione non è leggibile.")
    return data


def set_state(pid, **changes):
    with store.LOCK:
        data = read(pid)
        data.update(changes, updated=store.now())
        store.write_json(state_path(pid), data)
        return data


def is_editing(pid):
    return read(pid).get("status") in EDITING


def staging_root(pid, revision_id):
    if not isinstance(revision_id, str) or not re.fullmatch(r"[a-f0-9-]{8,80}", revision_id):
        raise ValueError("Revisione non valida.")
    return _folder(pid) / "final-revisions" / revision_id / "candidate"


def request_snapshot(pid, revision_id):
    return store.read_json(staging_root(pid, revision_id).parent / "request.json")


def _copy_tree(source, target, check=lambda: None):
    """Copy every mutable byte; never share writable hard links or follow links."""
    if source.is_symlink() or (hasattr(source, "is_junction") and source.is_junction()):
        raise ValueError("La revisione non può usare cartelle collegate all’esterno.")
    target.mkdir(parents=True, exist_ok=False)
    for child in source.iterdir():
        check()
        if child.is_symlink() or (hasattr(child, "is_junction") and child.is_junction()):
            raise ValueError("La revisione non può usare file collegati all’esterno.")
        if child.is_dir():
            _copy_tree(child, target / child.name, check)
        elif child.is_file():
            shutil.copy2(child, target / child.name)


def prepare_candidate(pid, revision_id):
    """Return an isolated workspace/checkpoint copy of the requested revision."""
    from . import runner
    target = staging_root(pid, revision_id)
    current = read(pid)
    if current.get("revision_id") != revision_id or current.get("status") not in BUSY:
        raise ValueError("Questa revisione non è più quella richiesta.")
    if target.exists():
        raise ValueError("I materiali di questa revisione esistono già. Riprova dalla revisione.")
    target.mkdir(parents=True)
    original = _folder(pid)
    for name in ("workspace", "checkpoints"):
        source = original / name
        if source.is_dir():
            _copy_tree(source, target / name, lambda: runner.check(pid))
        else:
            (target / name).mkdir()
    return target


def _restore_publication(pid, data):
    """Idempotent recovery of a partial directory swap before it was committed."""
    revision_id = data.get("revision_id")
    if not revision_id:
        return
    root = staging_root(pid, revision_id).parent
    previous = root / "previous"
    folder = _folder(pid)
    for name in ("checkpoints", "workspace"):
        backup = previous / name
        canonical = folder / name
        if backup.exists():
            if canonical.exists():
                displaced = root / ("unpublished-" + name)
                if displaced.exists():
                    displaced = root / ("unpublished-" + name + "-" + str(time.time_ns()))
                canonical.rename(displaced)
            backup.rename(canonical)
    original = data.get("original_project", {})
    if original:
        store.update(pid, status="completed", stage=original.get("stage", "Documentario completato"),
                     progress=100, error="", result=original.get("result", {}))


def publish(pid, staged_root, report):
    """Commit verified output as this project's film, retaining a local backup."""
    from . import runner, presentations
    with runner.LOCK, store.LOCK:
        data = read(pid)
        rid = data.get("revision_id")
        if not isinstance(report, dict) or report.get("verified") is not True:
            raise ValueError("Il video aggiornato deve superare la verifica prima di sostituire il film.")
        if report.get("revision_id") != rid or data.get("status") not in BUSY:
            raise ValueError("La revisione verificata non corrisponde a quella richiesta.")
        candidate = staging_root(pid, rid)
        if Path(staged_root).resolve() != candidate.resolve():
            raise ValueError("La cartella della revisione non appartiene al progetto.")
        if any(not (candidate / name).is_dir() for name in ("workspace", "checkpoints")):
            raise ValueError("I materiali della revisione sono incompleti.")
        runner.check(pid)
        presentations.ensure_idle(pid)
        folder = _folder(pid)
        previous = candidate.parent / "previous"
        if previous.exists():
            raise ValueError("Esiste già una copia precedente per questa revisione.")
        previous.mkdir()
        set_state(pid, status="publishing", message="Verifica superata: aggiorno il film del progetto.")
        store.write_json(candidate.parent / "verified-report.json", report)
        try:
            for name in ("workspace", "checkpoints"):
                (folder / name).rename(previous / name)
                (candidate / name).rename(folder / name)
            old_result = data.get("original_project", {}).get("result", store.project(pid).get("result", {}))
            number = int(data.get("revision_number", 0)) + 1
            elapsed = store.pause_processing(pid)
            result = {**old_result, **report.get("result", {}), "final_revision_number": number,
                      "final_revision_scenes": report.get("changed_scene_ids", [])}
            store.update(pid, status="completed", stage="Documentario aggiornato", progress=100,
                         error="", result=result, processing_seconds=elapsed)
            set_state(pid, status="completed", revision_number=number, error="",
                      changed_scenes=report.get("changed_scene_ids", []),
                      changed_scene_ids=report.get("changed_scene_ids", []),
                      message="Revisione completata. Il film aggiornato è disponibile nello stesso progetto.",
                      report=report, completed=store.now())
        except Exception:
            _restore_publication(pid, data)
            raise
        return status(pid)


def finish_failure(pid, revision_id, error, cancelled=False):
    from . import runner
    with runner.LOCK, store.LOCK:
        data = read(pid)
        if data.get("revision_id") != revision_id:
            return
        if data.get("status") not in BUSY:
            # A post-publication diary failure must not revert committed result
            # metadata or report the already verified film as a failed draft.
            return
        if data.get("status") == "publishing":
            _restore_publication(pid, data)
        elapsed = store.pause_processing(pid)
        store.update(pid, status="completed", stage="Documentario completato", progress=100,
                     error="", processing_seconds=elapsed,
                     result=data.get("original_project", {}).get("result", store.project(pid).get("result", {})))
        message = "Revisione interrotta. Il film precedente e le modifiche salvate sono conservati." if cancelled else "Revisione non completata. Il film precedente è disponibile; correggi le modifiche o riprova."
        set_state(pid, status="cancelled" if cancelled else "failed", error=str(error)[:2500], message=message)
        store.event(pid, message + (" " + str(error) if error else ""), "info" if cancelled else "error")


def recover():
    """Called once after database startup recovery, before accepting requests."""
    from . import runner
    for project in store.projects():
        pid = project["id"]
        data = read(pid)
        if data.get("status") in BUSY and not runner.active(pid):
            finish_failure(pid, data.get("revision_id"), "L’app si è chiusa durante l’aggiornamento. Puoi riprovare.", cancelled=True)


def status(pid):
    from . import runner, presentations, visual_slots
    project = store.project(pid)
    data = read(pid)
    try:
        available = bool(store.read_json(visual_slots.project_pack(pid)).get("scenes"))
    except (ValueError, OSError):
        available = False
    eligible = project["status"] == "completed" or data.get("status") in BUSY
    return {"available": available and eligible, "editing": data.get("status") in EDITING,
            "busy": data.get("status") in BUSY, "status": data.get("status", "idle"),
            "message": data.get("message", "Rivedi testo, luoghi e immagini del film completato."),
            "error": data.get("error", ""), "revision_number": data.get("revision_number", 0), "updated": data.get("updated", ""),
            "changed_scenes": data.get("changed_scene_ids", data.get("changed_scenes", [])),
            "can_open": available and project["status"] == "completed" and not runner.active(pid) and not presentations.active(pid)}


@router.get("/{pid}/final-review")
def get_review(pid: str):
    return status(pid)


@router.post("/{pid}/final-review")
@project_mutation
def open_review(pid: str):
    from . import runner
    current = status(pid)
    if current["busy"] or runner.active(pid):
        raise HTTPException(409, "Attendi la fine dell’aggiornamento prima di modificare la revisione.")
    if not current["can_open"]:
        raise HTTPException(409, "La revisione finale è disponibile per un documentario completato con scene conservate.")
    if current["editing"]:
        return current
    folder = _folder(pid)
    baseline = {name: store.read_json(folder / "checkpoints" / name) if (folder / "checkpoints" / name).is_file() else None
                for name in DRAFT_FILES}
    set_state(pid, status="editing", message="Modifica facoltativamente testo, luoghi e immagini, poi aggiorna il film.",
              error="", draft_baseline=baseline, original_project=copy.deepcopy(store.project(pid)))
    return status(pid)


@router.delete("/{pid}/final-review")
@project_mutation
def discard(pid: str):
    from . import runner
    data = read(pid)
    if data.get("status") in BUSY or runner.active(pid):
        raise HTTPException(409, "Interrompi l’aggiornamento prima di scartare le modifiche.")
    if data.get("status") not in EDITING:
        return status(pid)
    for name, value in data.get("draft_baseline", {}).items():
        if name not in DRAFT_FILES:
            continue
        target = _folder(pid) / "checkpoints" / name
        if value is None:
            target.unlink(missing_ok=True)
        else:
            store.write_json(target, value)
    set_state(pid, status="idle", error="", message="Revisione chiusa. Il film è rimasto invariato.")
    return status(pid)


@router.post("/{pid}/final-review/render", status_code=202)
@project_mutation
def render(pid: str):
    from . import runner, media, visual_slots, review_editor
    from .final_review_worker import run_revision
    data = read(pid)
    if data.get("status") not in EDITING or store.project(pid)["status"] != "completed":
        raise HTTPException(409, "Apri la revisione del film prima di aggiornarlo.")
    if runner.active(pid):
        raise HTTPException(409, "Questo progetto è già in coda o in esecuzione.")
    from .voice_delivery import preview_active
    if preview_active():
        raise HTTPException(409, "Attendi la fine della prova vocale prima di avviare la revisione.")
    pack = store.read_json(visual_slots.project_pack(pid))
    draft = review_editor.pending(pid, pack)
    rid = f"{time.time_ns():x}-{threading.get_ident():x}"
    preferences = visual_slots.preferences(pid)
    records = media.catalog()
    revision_root = staging_root(pid, rid).parent
    # Catalog metadata and bytes form one immutable snapshot under store.LOCK;
    # edits in another project may continue without changing this revision.
    for record in records:
        source = media.folder(record["id"])
        target = revision_root / "media" / record["id"]
        target.mkdir(parents=True, exist_ok=True)
        for name in ("image.png", "thumb.jpg", "record.json"):
            if (source / name).is_file():
                shutil.copy2(source / name, target / name)
    request = {"revision_id": rid, "editorial": draft, "visual_options": preferences["slots"],
               "layout_options": preferences["layouts"], "media_records": records,
               "original_result": copy.deepcopy(store.project(pid).get("result", {})), "requested": store.now()}
    store.write_json(revision_root / "request.json", request)
    cfg = store.settings(True)
    runner.FLAGS[pid] = threading.Event()
    set_state(pid, status="queued", revision_id=rid, error="", changed_scenes=[], changed_scene_ids=[],
              message="Revisione in coda. Il film precedente rimane disponibile.")
    store.begin_processing(pid)
    store.update(pid, status="queued", stage="Aggiornamento del film in coda", error="", progress=0)
    try:
        runner.FUTURES[pid] = runner.POOL.submit(run_revision, pid, cfg, rid)
    except Exception as error:
        finish_failure(pid, rid, error)
        raise
    store.event(pid, "Revisione dello stesso progetto in coda. Saranno aggiornate solo le scene interessate dalle modifiche.")
    return status(pid)


def cancel(pid):
    from . import runner
    with runner.LOCK, store.LOCK:
        data = read(pid)
        if data.get("status") not in BUSY:
            # A delayed click after publication must never turn the completed
            # film into a cancelled full production.
            return bool(data and store.project(pid)["status"] == "completed")
        if pid in runner.FLAGS:
            runner.FLAGS[pid].set()
        future = runner.FUTURES.get(pid)
        if future and future.cancel():
            finish_failure(pid, data["revision_id"], "", cancelled=True)
        else:
            set_state(pid, status="cancelling", message="Interruzione della revisione in corso. Il film precedente resta disponibile.")
            store.update(pid, status="cancelling", stage="Interruzione della revisione")
            runner.stop_process(pid)
        return True
