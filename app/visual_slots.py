"""Automatic, attributable visual subjects and selective user replacements."""
from __future__ import annotations

import hashlib
import os
import re
import shutil
from pathlib import Path

from . import media, store


def project_pack(pid: str) -> Path:
    work = store.JOBS / pid / "workspace"
    candidates = sorted((work / "battles").glob("*/battle.json")) + sorted((work / "documentaries").glob("*/documentary.json"))
    if not candidates:
        raise ValueError("Il progetto non contiene ancora scene utilizzabili.")
    return candidates[0]


def _safe(value: str) -> str:
    value = media.normalized(value).replace(" ", "-")
    return re.sub(r"[^a-z0-9_-]", "", value)[:48] or "soggetto"


def _collections(pack):
    persons = pack.get("persons", [])
    if not persons:
        persons = [{"id": ident, **row} for ident, row in pack.get("commanders", {}).items()]
    locations = pack.get("locations", [])
    if not locations:
        locations = [{"id": ident, **row} for ident, row in pack.get("places", {}).items()]
    return persons, locations


def _uses(pack, kind, subject):
    result = []
    ident, label = subject["id"], subject.get("name", subject["id"])
    for scene in pack.get("scenes", []):
        lines = scene.get("lines", [])
        cues = [i for i, line in enumerate(lines) if media.mention(line, label)]
        if kind == "person" and not cues:
            explicit = ident in scene.get("person_ids", [])
            explicit = explicit or any((x.get("id") if isinstance(x, dict) else x) == ident for x in scene.get("commanders", []))
            if explicit and lines:
                cues = [0]
        for cue in cues[:1]:
            result.append({"scene_id": scene["id"], "cue": cue})
    return result


def derive(pack):
    """Create stable slots from the pack without requiring a newer schema."""
    existing = {x.get("id"): x for x in pack.get("visual_slots", []) if isinstance(x, dict)}
    persons, locations = _collections(pack)
    slots = []
    for kind, rows in (("person", persons), ("place", locations)):
        for row in rows:
            if not isinstance(row, dict) or not row.get("id") or not row.get("name"):
                continue
            uses = _uses(pack, kind, row)
            if not uses:
                continue
            ident = f"visual-{kind}-{_safe(str(row['id']))}"
            old = existing.get(ident, {})
            slot = {
                "id": ident,
                "kind": kind,
                "subject_id": row["id"],
                "label": row["name"],
                "uses": uses,
                "path": f"assets/user/automatic/{ident}.jpg",
                "wikipedia_page": row.get("wikipedia_page") or row["name"],
                "source_type": kind,
                "source_path": row.get("portrait", "") if kind == "person" else "",
            }
            for key in ("replacement_media_id", "search_note"):
                if old.get(key):
                    slot[key] = old[key]
            slots.append(slot)
    for asset in pack.get("visual_assets", []):
        if not isinstance(asset, dict) or not asset.get("id") or not asset.get("path"):
            continue
        uses = [{"scene_id": s["id"], "cue": 0} for s in pack.get("scenes", []) if asset["id"] in s.get("asset_ids", [])]
        if not uses:
            continue
        ident = f"visual-asset-{_safe(str(asset['id']))}"
        slots.append({"id": ident, "kind": "topic", "subject_id": asset["id"],
            "label": asset.get("title", asset["id"]), "uses": uses, "path": asset["path"],
            "source_path": asset["path"], "source_type": "visual_asset", "wikipedia_page": asset.get("wikipedia_page", "")})
    for item in pack.get("user_media", []):
        if not isinstance(item, dict) or str(item.get("id", "")).startswith("visual-"):
            continue
        bindings = item.get("bindings", [])
        binding = bindings[0] if bindings else {"kind": "topic", "label": item.get("title", "Immagine")}
        uses = [{"scene_id": scene["id"], "cue": inset.get("cue", 0)} for scene in pack.get("scenes", [])
                for inset in scene.get("image_insets", []) if inset.get("asset_id") == item.get("id")]
        if not uses:
            continue
        slots.append({"id": f"visual-media-{_safe(str(item['id']))}", "kind": binding.get("kind", "topic"),
            "subject_id": item["id"], "label": binding.get("label") or item.get("title", "Immagine"), "uses": uses,
            "path": item["path"], "source_path": item["path"], "source_type": "manual_media",
            "existing_media_id": item["id"], "wikipedia_page": ""})
    return slots


def prepare(pack):
    """Declare all reusable slots before the offline asset acquisition stage."""
    # General-history people used to receive portraits only when the model also
    # supplied a Wikipedia page. Searching the person's own name makes every
    # declared person eligible, while the downloader retains its strict licence
    # check and neutral fallback.
    if pack.get("schema_version") == 2:
        for person in pack.get("persons", []):
            if not person.get("wikipedia_page"):person["wikipedia_page"] = person.get("name", "")
            person.setdefault("portrait", f"assets/portraits/{pack['slug']}/{person['id']}.jpg")
    slots = derive(pack)
    pack["visual_slots"] = slots
    pack["auto_visual_assets"] = [
        {"id": s["id"], "kind": s["kind"], "name": s["label"], "path": s["path"], "wikipedia_page": s["wikipedia_page"], "optional": True}
        for s in slots if s["kind"] == "place"
    ]
    return slots


def _metadata_state(path: Path):
    metadata = path.with_suffix(".metadata.json")
    if not path.is_file():
        return "missing", {}
    info = store.read_json(metadata) if metadata.is_file() else {}
    ex = info.get("extmetadata", {})
    if info.get("h3_user_replacement"):
        return "user", info
    placeholder = bool(info.get("h3_placeholder")) or "riquadro generico" in str(ex.get("ObjectName", {}).get("value", "")).lower()
    return ("blank" if placeholder else "available"), info


def _credit(info, label, state):
    ex = info.get("extmetadata", {})
    def value(key, default=""):
        row = ex.get(key, {})
        return row.get("value", default) if isinstance(row, dict) else default
    return {
        "title": value("ObjectName", label),
        "credit": value("Attribution") or value("Artist", "H3-documentary" if state == "blank" else ""),
        "source": info.get("descriptionurl", ""),
        "rights": value("LicenseShortName", "Licenza indicata nella scheda sorgente"),
    }


def _binding_match(item, slot):
    for binding in item.get("bindings", []):
        if binding.get("kind") != slot["kind"]:
            continue
        terms = [binding.get("label", ""), *binding.get("aliases", [])]
        if any(media.normalized(term) == media.normalized(slot["label"]) for term in terms):
            return True
    return False


def _copy_replacement(item, slot, work):
    source = media.folder(item["id"])
    target = work / slot["path"]
    target.parent.mkdir(parents=True, exist_ok=True)
    if hashlib.sha256((source / "image.png").read_bytes()).hexdigest() != item["image_sha256"]:
        raise ValueError("Un’immagine collegata è stata modificata sul disco: caricala nuovamente.")
    target.unlink(missing_ok=True)
    shutil.copy2(source / "image.png", target)
    metadata = {
        "descriptionurl": item.get("source") or "caricamento locale",
        "h3_placeholder": False,
        "h3_user_replacement": True,
        "extmetadata": {
            "ObjectName": {"value": item["title"]},
            "Artist": {"value": item.get("credit") or "attribuzione non indicata"},
            "LicenseShortName": {"value": item.get("rights") or "diritti dichiarati dall’utente"},
        },
    }
    store.write_json(target.with_suffix(".metadata.json"), metadata)
    slot["replacement_media_id"] = item["id"]
    return target, metadata


def _person_source(pack, slot, work):
    persons, _ = _collections(pack)
    row = next((p for p in persons if p.get("id") == slot["subject_id"]), None)
    if not row or not row.get("portrait"):
        return None
    source = work / row["portrait"]
    if not source.is_file():
        return None
    target = work / slot["path"]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True)
    shutil.copy2(source, target)
    meta = source.with_suffix(".metadata.json")
    if meta.is_file():
        shutil.copy2(meta, target.with_suffix(".metadata.json"))
    return target


def materialize(pack, work, records=None, replacements_only=False):
    """Attach automatic cards or user replacements to the exact spoken cues."""
    work = Path(work)
    slots = prepare(pack)
    records = list(records or [])
    old_entries = {x.get("id"): x for x in pack.get("user_media", []) if isinstance(x, dict)}
    manual_entries = [dict(x) for x in pack.get("user_media", []) if not str(x.get("id", "")).startswith("visual-")]
    changed_scenes = set()
    superseded_manual_ids = set()
    automatic = []
    for slot in slots:
        current_manual=next((x for x in manual_entries if _binding_match(x,slot)),None) if slot.get('source_type') in ('person','place') else None
        current_ids={slot.get("existing_media_id"),slot.get('replacement_media_id'),current_manual.get('id') if current_manual else None}
        replacement = next((x for x in records if x.get("enabled") and x.get("id") not in current_ids and _binding_match(x, slot)), None)
        if current_manual and not replacement:
            continue
        if slot.get("source_type") == "visual_asset":
            if replacement:
                source = media.folder(replacement["id"]) / "image.png"; target = work / slot["source_path"]
                previous_sha = hashlib.sha256(target.read_bytes()).hexdigest() if target.is_file() else ""
                target.unlink(missing_ok=True); target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, target)
                metadata = target.with_suffix(".metadata.json"); metadata.unlink(missing_ok=True)
                store.write_json(metadata, {"descriptionurl": replacement.get("source") or "caricamento locale", "h3_user_replacement": True,
                    "extmetadata": {"ObjectName": {"value": replacement["title"]}, "Artist": {"value": replacement.get("credit") or "attribuzione non indicata"},
                    "LicenseShortName": {"value": replacement.get("rights") or "diritti dichiarati dall’utente"}}})
                current_sha = hashlib.sha256(target.read_bytes()).hexdigest()
                if current_sha != previous_sha: changed_scenes.update(use["scene_id"] for use in slot["uses"])
                asset = next(x for x in pack.get("visual_assets", []) if x["id"] == slot["subject_id"])
                asset.update(title=replacement["title"], creator=replacement.get("credit", ""), source=replacement.get("source") or "caricamento locale",
                             license=replacement.get("rights") or "diritti dichiarati dall’utente")
                slot["replacement_media_id"] = replacement["id"]
            continue
        if slot.get("source_type") == "manual_media":
            if replacement:
                entry = next((x for x in manual_entries if x.get("id") == slot["existing_media_id"]), None)
                if entry:
                    target = work / entry["path"]; previous_sha = entry.get("image_sha256", "")
                    target.unlink(missing_ok=True); shutil.copy2(media.folder(replacement["id"]) / "image.png", target)
                    entry.update(title=replacement["title"], filename=replacement["filename"], image_sha256=replacement["image_sha256"], sha256=replacement["sha256"],
                                 credit=replacement.get("credit", ""), source=replacement.get("source", ""), rights=replacement.get("rights", ""), origin="user_replacement")
                    if entry["image_sha256"] != previous_sha: changed_scenes.update(use["scene_id"] for use in slot["uses"])
                    slot["replacement_media_id"] = replacement["id"]
            continue
        if replacement:
            if current_manual:
                superseded_manual_ids.add(current_manual['id']);manual_entries=[x for x in manual_entries if x.get('id')!=current_manual['id']]
            target, info = _copy_replacement(replacement, slot, work)
            state, origin = "user", "user_replacement"
            if slot["kind"] == "person" and slot.get("source_path"):
                portrait = work / slot["source_path"]
                portrait.unlink(missing_ok=True); portrait.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(target, portrait)
                portrait_meta = portrait.with_suffix(".metadata.json"); portrait_meta.unlink(missing_ok=True); shutil.copy2(target.with_suffix(".metadata.json"), portrait_meta)
        elif replacements_only:
            previous = old_entries.get(slot["id"])
            if previous:
                automatic.append(previous)
            continue
        else:
            if current_manual:
                continue
            target = work / slot["path"]
            if slot["kind"] == "person":
                _person_source(pack, slot, work)
            state, info = _metadata_state(target)
            origin = "automatic"
        if not target.is_file():
            continue
        current_sha = hashlib.sha256(target.read_bytes()).hexdigest()
        previous_sha = old_entries.get(slot["id"], {}).get("image_sha256")
        if replacement and current_sha != previous_sha:
            changed_scenes.update(use["scene_id"] for use in slot["uses"])
        credit = _credit(info, slot["label"], state)
        entry = {
            "id": slot["id"], "asset_id": slot["id"], "filename": target.name,
            "path": slot["path"], "image_sha256": current_sha, "sha256": current_sha,
            "origin": origin, "subject_kind": slot["kind"], "subject_id": slot["subject_id"],
            "bindings": [{"kind": slot["kind"], "label": slot["label"], "aliases": []}],
            "layout": {"x": .71, "y": .21, "width": .25, "fit": "contain"},
            "visual_state": state, **credit,
        }
        automatic.append(entry)
    pack["user_media"] = manual_entries + automatic
    by_scene = {scene["id"]: scene for scene in pack.get("scenes", [])}
    for scene in by_scene.values():
        scene["image_insets"] = [x for x in scene.get("image_insets", []) if not str(x.get("asset_id", "")).startswith("visual-") and x.get('asset_id') not in superseded_manual_ids]
    available = {x["id"] for x in automatic}
    for slot in slots:
        if slot["id"] not in available:
            continue
        entry = next(x for x in automatic if x["id"] == slot["id"])
        for use in slot["uses"]:
            scene = by_scene.get(use["scene_id"])
            if scene is None:
                continue
            scene.setdefault("image_insets", []).append({
                "asset_id": slot["id"], "cue": use["cue"], "slot": 0, "slots": 1,
                "title": slot["label"], "layout": entry["layout"], "sha256": entry["image_sha256"],
            })
    # All images bound to one cue alternate instead of covering each other.
    for scene in by_scene.values():
        groups = {}
        for inset in scene.get("image_insets", []):
            groups.setdefault(inset["cue"], []).append(inset)
        for rows in groups.values():
            for index, inset in enumerate(rows):
                inset["slot"], inset["slots"] = index, len(rows)
    manifest = work / "assets/user/automatic/visual-slots.json"
    store.write_json(manifest, slots)
    if pack.get("video_license") and automatic:
        pack["base_video_license"] = pack.pop("video_license")
    return sorted(changed_scenes)


def sync_timeline(pack, work):
    path = work / "build" / pack["slug"] / "timeline.json"
    if not path.is_file():
        raise ValueError("La voce e la timeline non sono ancora complete: riprendi prima la produzione normale.")
    timeline = store.read_json(path)
    for key in ("user_media","visual_slots","visual_assets","persons"):
        if key in pack:timeline[key]=pack[key]
    authored = {s["id"]: s for s in pack["scenes"]}
    for scene in timeline["scenes"]:
        scene["image_insets"] = authored[scene["id"]].get("image_insets", [])
    store.write_json(path, timeline)
    store.write_json(work / "timeline.json", timeline)
    return timeline


def status(pid):
    p = store.project(pid)
    try:
        packpath = project_pack(pid)
    except ValueError:
        return {"ready": False, "slots": [], "blank_count": 0, "replacement_count": 0}
    pack = store.read_json(packpath)
    slots = pack.get("visual_slots") or derive(pack)
    entries = {x.get("id"): x for x in pack.get("user_media", []) if isinstance(x, dict)}
    records = media.catalog()
    result = []
    for slot in slots:
        entry = entries.get(slot["id"], {})
        path = packpath.parents[2] / entry.get("path", slot["path"])
        if not path.is_file() and slot.get("source_path"):
            path = packpath.parents[2] / slot["source_path"]
        state, _ = _metadata_state(path)
        current_manual=next((x for x in pack.get('user_media',[]) if not str(x.get('id','')).startswith('visual-') and _binding_match(x,slot)),None) if slot.get('source_type') in ('person','place') else None
        if entry.get("origin") == "user_replacement" or slot.get('source_type')=='manual_media' or current_manual:
            state = "user"
        current_ids={slot.get('existing_media_id'),slot.get('replacement_media_id'),current_manual.get('id') if current_manual else None}
        replacement = next((x for x in records if x.get("enabled") and x.get("id") not in current_ids and _binding_match(x, slot)), None)
        result.append({**slot, "state": state, "replacement_ready": bool(replacement), "has_preview": path.is_file(),
                       "replacement_title": replacement.get("title", "") if replacement else "",
                       "scene_ids": sorted({u["scene_id"] for u in slot["uses"]})})
    return {
        "ready": bool(result), "completed": p["status"] == "completed", "slots": result,
        "blank_count": sum(x["state"] in ("blank", "missing") for x in result),
        "replacement_count": sum(x["replacement_ready"] for x in result),
    }


def slot_file(pid, slot_id):
    packpath=project_pack(pid);pack=store.read_json(packpath);work=packpath.parents[2]
    slot=next((x for x in (pack.get('visual_slots') or derive(pack)) if x['id']==slot_id),None)
    if slot is None:raise KeyError(slot_id)
    entry=next((x for x in pack.get('user_media',[]) if x.get('id')==slot_id),{})
    path=work/entry.get('path',slot['path'])
    if not path.is_file() and slot.get('source_path'):path=work/slot['source_path']
    if not path.is_file() or not path.resolve().is_relative_to(work.resolve()):raise KeyError(slot_id)
    return path


def clone_workspace(source_pid, target_pid):
    """Clone a completed workspace, hard-linking only large immutable inputs."""
    source = store.JOBS / source_pid; target = store.JOBS / target_pid
    for top in ("checkpoints", "workspace", "research"):
        root = source / top
        if not root.exists():continue
        for item in root.rglob("*"):
            rel = item.relative_to(source);parts = rel.parts
            if "output" in parts or ("build" in parts and "sound" in parts):continue
            if item.is_dir():(target / rel).mkdir(parents=True, exist_ok=True);continue
            if item.name in ("picture.mp4", "scenes.txt", "chapters.ffmetadata"):continue
            dest = target / rel;dest.parent.mkdir(parents=True, exist_ok=True)
            can_link = item.stat().st_size > 4 * 1024 * 1024 and ("assets" in parts or "scenes" in parts or "voice" in parts)
            if can_link:
                try:os.link(item, dest)
                except OSError:shutil.copy2(item, dest)
            else:shutil.copy2(item, dest)
    return target / "workspace"
