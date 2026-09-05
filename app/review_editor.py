"""Optional, project-local text and map corrections staged before production."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator, model_validator

from . import store, visual_slots
from .presentations import project_mutation

router = APIRouter(prefix="/api/projects")
MAX_TEXT = 500_000


class SceneEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: StrictStr = Field(min_length=1, max_length=100)
    lines: list[StrictStr] = Field(min_length=1, max_length=512)

    @field_validator("lines")
    @classmethod
    def clean_lines(cls, value):
        if any(not line.strip() or len(line) > 8000 for line in value):
            raise ValueError("Ogni frase deve contenere da 1 a 8000 caratteri.")
        return value


class PlaceEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: StrictStr = Field(min_length=1, max_length=100)
    pos: list[float] = Field(min_length=2, max_length=2)

    @field_validator("pos", mode="before")
    @classmethod
    def coordinates(cls, value):
        if (not isinstance(value, (list, tuple)) or len(value) != 2
                or any(isinstance(n, bool) or not isinstance(n, (int, float)) or not math.isfinite(n) for n in value)
                or not (-179 <= value[0] <= 179 and -78 <= value[1] <= 78)):
            raise ValueError("Coordinate non valide: longitudine da −179 a 179, latitudine da −78 a 78.")
        return value


class EditorialEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: StrictStr = Field(pattern=r"^[a-f0-9]{64}$")
    scenes: list[SceneEdit] = Field(default_factory=list, max_length=500)
    places: list[PlaceEdit] = Field(default_factory=list, max_length=2000)

    @model_validator(mode="after")
    def bounded_unique(self):
        if sum(len(line) for scene in self.scenes for line in scene.lines) > MAX_TEXT:
            raise ValueError("Il testo da salvare supera il limite di 500.000 caratteri.")
        for name in ("scenes", "places"):
            rows = getattr(self, name)
            if len({row.id for row in rows}) != len(rows):
                raise ValueError("Non puoi indicare due volte la stessa scena o lo stesso luogo.")
        return self


def _hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _folder(pid) -> Path:
    store.project(pid)
    root = store.JOBS.resolve()
    folder = (root / pid).resolve()
    if folder.parent != root:
        raise ValueError("Progetto non valido.")
    return folder / "checkpoints"


def _path(pid):
    return _folder(pid) / "editorial-review.json"


def _collections(pack):
    scenes = pack.get("scenes", [])
    places = pack.get("locations") or pack.get("places") or []
    if isinstance(places, dict):
        places = [{**row, "id": ident} for ident, row in places.items()]
    if (not isinstance(scenes, list) or not isinstance(places, list)
            or any(not isinstance(row, dict) or not isinstance(row.get("id"), str) for row in [*scenes, *places])):
        raise ValueError("Le scene e i luoghi del progetto non sono leggibili.")
    if len({s["id"] for s in scenes}) != len(scenes) or len({p["id"] for p in places}) != len(places):
        raise ValueError("Il progetto contiene identificatori duplicati.")
    if any(not isinstance(s.get("lines"), list) or any(not isinstance(line, str) for line in s["lines"]) for s in scenes):
        raise ValueError("La sceneggiatura del progetto non è ancora disponibile.")
    return scenes, places


def fingerprint(pack):
    """Visual/layout edits never invalidate an unrelated editorial draft."""
    scenes, places = _collections(pack)
    return _hash({"scenes": [{"id": s["id"], "lines": s["lines"]} for s in scenes],
                  "places": sorted([{"id": p["id"], "pos": p.get("pos")} for p in places], key=lambda p: p["id"])})


def _revision(base, scenes, places):
    return _hash({"base_fingerprint": base, "scenes": scenes, "places": places})


def _changes(pack, scenes, places):
    base_scenes, base_places = _collections(pack)
    by_scene = {s["id"]: s for s in base_scenes}
    by_place = {p["id"]: p for p in base_places}
    for scene in scenes:
        if scene["id"] not in by_scene:
            raise ValueError("La scena selezionata non appartiene a questo progetto.")
        if len(scene["lines"]) != len(by_scene[scene["id"]]["lines"]):
            raise ValueError("Mantieni il numero delle frasi: ogni frase è associata alle animazioni della scena.")
    for place in places:
        if place["id"] not in by_place:
            raise ValueError("Il luogo selezionato non appartiene a questo progetto.")
    # Stable ordering makes repeated saves idempotent, irrespective of request order.
    changed_scenes = sorted([s for s in scenes if s["lines"] != by_scene[s["id"]]["lines"]], key=lambda s: s["id"])
    changed_places = sorted([p for p in places if p["pos"] != by_place[p["id"]].get("pos")], key=lambda p: p["id"])
    return changed_scenes, changed_places


def pending(pid, pack):
    """Return a validated, unapplied draft; called under the production/store locks."""
    path = _path(pid)
    if not path.is_file():
        return None
    data = store.read_json(path)
    if not isinstance(data, dict) or data.get("base_fingerprint") != fingerprint(pack):
        raise ValueError("La sceneggiatura o la geografia sono cambiate dopo la revisione. Riapri la revisione prima di continuare.")
    edit = EditorialEdit.model_validate({key: data.get(key, []) for key in ("scenes", "places")} | {"revision": data.get("revision", "")})
    scenes, places = _changes(pack, [s.model_dump() for s in edit.scenes], [p.model_dump() for p in edit.places])
    revision = _revision(data["base_fingerprint"], scenes, places)
    if revision != edit.revision:
        raise ValueError("La revisione salvata non è coerente. Riapri il progetto prima di continuare.")
    if not scenes and not places:
        return None
    return {"base_fingerprint": data["base_fingerprint"], "revision": revision,
            "scenes": scenes, "places": places, "updated": data.get("updated", "")}


def mark_applied(pid, report):
    """Keep an audit before clearing a successfully applied draft; never write the pack."""
    path = _path(pid)
    if not path.is_file():
        return None
    draft = store.read_json(path)
    expected = report.get("revision") if isinstance(report, dict) else None
    if expected and draft.get("revision") != expected:
        raise ValueError("La revisione è stata modificata durante l’applicazione. Nessuna bozza è stata cancellata.")
    audit = {"applied": store.now(), "draft": draft, "report": report}
    target = path.parent / "editorial-review-applied" / f"{time.time_ns()}-{_hash(audit)[:12]}.json"
    store.write_json(target, audit)
    path.unlink()
    return target


def _scene_ids(place_id, scenes, events):
    event_places = {e.get("id"): e.get("location_id") for e in events if isinstance(e, dict)}
    result = []
    for scene in scenes:
        referenced = [x for key in ("location_ids", "visible_places", "focus")
                      for x in scene.get(key, []) if isinstance(x, str)]
        if place_id in referenced or any(event_places.get(e) == place_id for e in scene.get("event_ids", []) if isinstance(e, str)):
            result.append(scene["id"])
    return result


def state(pid):
    from . import presentations, runner
    with runner.LOCK, store.LOCK:
        project = store.project(pid)
        empty = {"available": False, "editable": False, "reason": "Disponibile dopo la preparazione delle scene.",
                 "revision": "", "scenes": [], "places": [], "dirty": False,
                 "changed_scene_ids": [], "changed_place_ids": []}
        try:
            pack = store.read_json(visual_slots.project_pack(pid))
            scenes, places = _collections(pack)
            base = fingerprint(pack)
        except (ValueError, OSError):
            return empty
        reason = ""
        from .final_review import is_editing
        if project["status"] != "review" and not (project["status"] == "completed" and is_editing(pid)):
            reason = "Puoi modificare testo e luoghi quando il progetto è fermo per la revisione."
        elif runner.active(pid):
            reason = "Attendi che il motore termini il passaggio corrente."
        elif presentations.active(pid):
            reason = "Attendi la fine dell’esportazione PDF."
        draft = None
        try:
            draft = pending(pid, pack)
        except (ValueError, OSError) as error:
            reason = str(error)
        changes = draft or {"scenes": [], "places": []}
        scene_edits = {s["id"]: s["lines"] for s in changes["scenes"]}
        place_edits = {p["id"]: p["pos"] for p in changes["places"]}
        return {"available": bool(scenes), "editable": bool(scenes) and not reason, "reason": reason,
                "revision": draft["revision"] if draft else _revision(base, [], []),
                "scenes": [{"id": s["id"], "title": s.get("title", s["id"]),
                            "date": s.get("date", s.get("date_label", "")),
                            "lines": copy.deepcopy(scene_edits.get(s["id"], s["lines"])),
                            "base_lines": copy.deepcopy(s["lines"])} for s in scenes],
                "places": [{"id": p["id"], "name": p.get("name", p["id"]),
                            "pos": copy.deepcopy(place_edits.get(p["id"], p.get("pos"))),
                            "base_pos": copy.deepcopy(p.get("pos")),
                            "scene_ids": _scene_ids(p["id"], scenes, pack.get("events", []))} for p in places],
                "dirty": bool(draft), "changed_scene_ids": sorted(scene_edits), "changed_place_ids": sorted(place_edits)}


@router.get("/{pid}/editorial-review")
def get_review(pid: str):
    return state(pid)


@router.put("/{pid}/editorial-review")
@project_mutation
def put_review(pid: str, value: EditorialEdit):
    current = state(pid)
    if not current["editable"]:
        raise HTTPException(409, current["reason"])
    if value.revision != current["revision"]:
        raise HTTPException(409, "Questa revisione è stata aggiornata in un’altra finestra. Ricarica prima di salvare.")
    pack = store.read_json(visual_slots.project_pack(pid))
    previous = pending(pid, pack) or {"scenes": [], "places": []}
    scenes = {s["id"]: s for s in previous["scenes"]}
    places = {p["id"]: p for p in previous["places"]}
    scenes.update({s.id: s.model_dump() for s in value.scenes})
    places.update({p.id: p.model_dump() for p in value.places})
    EditorialEdit.model_validate({"revision": current["revision"], "scenes": list(scenes.values()), "places": list(places.values())})
    changed_scenes, changed_places = _changes(pack, list(scenes.values()), list(places.values()))
    path = _path(pid)
    if changed_scenes or changed_places:
        base = fingerprint(pack)
        store.write_json(path, {"base_fingerprint": base,
                               "revision": _revision(base, changed_scenes, changed_places),
                               "scenes": changed_scenes, "places": changed_places, "updated": store.now()})
    elif path.is_file():
        path.unlink()
    return state(pid)
