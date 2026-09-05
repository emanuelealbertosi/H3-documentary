"""Automatic, attributable visual subjects and selective user replacements."""
from __future__ import annotations

import hashlib
import os
import re
import shutil
from pathlib import Path

from . import media, store
from pipeline.engine.image_rights import manual_allowed, metadata_policy, usage_for

NONMAP_SCENES = {"timeline", "person_intro", "event_focus", "comparison", "data_visualization", "quote", "artwork", "document", "transition", "summary"}


def project_pack(pid: str) -> Path:
    work = store.JOBS / pid / "workspace"
    candidates = sorted((work / "battles").glob("*/battle.json")) + sorted((work / "documentaries").glob("*/documentary.json"))
    if not candidates:
        raise ValueError("Il progetto non contiene ancora scene utilizzabili.")
    return candidates[0]


def _options_path(pid: str) -> Path:
    return store.JOBS / pid / "checkpoints" / "visual-options.json"


def preferences(pid: str) -> dict:
    path = _options_path(pid)
    if not path.is_file():
        return {"slots": {}, "layouts": {}}
    data = store.read_json(path)
    return {
        "slots": {str(key): bool(value) for key, value in data.get("slots", {}).items()},
        "layouts": {str(key): media.Layout.model_validate(value).model_dump() for key, value in data.get("layouts", {}).items()},
    }


def options(pid: str) -> dict:
    return preferences(pid)["slots"]


def layout_options(pid: str) -> dict:
    return preferences(pid)["layouts"]


def apply_options(pack, selected, layouts=None):
    """Overlay project-local choices without changing the reusable source model."""
    slots = derive(pack)
    for slot in slots:
        if slot["id"] in selected:
            slot["enabled"] = bool(selected[slot["id"]])
    changed_scenes=set()
    for slot_id,layout in (layouts or {}).items():
        slot=next((item for item in slots if item["id"]==slot_id),None)
        if slot is None:continue
        layout=media.Layout.model_validate(layout).model_dump()
        entry=next((item for item in pack.get("user_media",[]) if item.get("id")==slot_id),None)
        if entry is not None and entry.get("layout")!=layout:
            entry["layout"]=layout;changed_scenes.update(use["scene_id"] for use in slot["uses"])
        for scene in pack.get("scenes",[]):
            for inset in scene.get("image_insets",[]):
                if inset.get("asset_id")==slot_id and inset.get("layout")!=layout:
                    inset["layout"]=layout;changed_scenes.add(scene["id"])
    if changed_scenes:pack["_pending_visual_layout_scenes"]=sorted(changed_scenes)
    pack["visual_slots"] = slots
    return slots


def set_enabled(pid: str, slot_id: str, enabled: bool):
    project = store.project(pid)
    if project["status"] not in ("review", "completed"):
        raise ValueError("Puoi attivare o escludere riferimenti durante la revisione visuale oppure dopo il completamento del film.")
    pack = store.read_json(project_pack(pid));slots = derive(pack)
    slot = next((item for item in slots if item.get("id") == slot_id), None)
    if slot is None:
        raise KeyError(slot_id)
    chosen = preferences(pid);chosen["slots"][slot_id] = bool(enabled);chosen["updated"] = store.now()
    store.write_json(_options_path(pid), chosen)
    action = "attivato" if enabled else "escluso"
    store.event(pid, f"Riferimento visuale {action}: {slot['label']}.")
    return status(pid)


def set_layout(pid: str, slot_id: str, layout):
    project=store.project(pid)
    if project["status"] not in ("review","completed"):
        raise ValueError("Puoi cambiare posizione e dimensione durante la revisione visuale oppure dopo il completamento del film.")
    slot=next((item for item in derive(store.read_json(project_pack(pid))) if item.get("id")==slot_id),None)
    if slot is None:raise KeyError(slot_id)
    value=media.Layout.model_validate(layout).model_dump()
    chosen=preferences(pid);chosen["layouts"][slot_id]=value;chosen["updated"]=store.now()
    store.write_json(_options_path(pid),chosen)
    store.event(pid,f"Inquadratura visuale modificata: {slot['label']}.")
    return status(pid)


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
    terms = [label, *media.subject_aliases(subject)]
    for scene in pack.get("scenes", []):
        lines = scene.get("lines", [])
        cues = [i for i, line in enumerate(lines) if any(media.mention(line, term) for term in terms)]
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
                "aliases": media.subject_aliases(row),
                "uses": uses,
                "path": f"assets/user/automatic/{ident}.jpg",
                "wikipedia_page": row.get("wikipedia_page") or row["name"],
                "source_type": kind,
                "source_path": row.get("portrait", "") if kind == "person" else "",
                "required": True, "optional": False,
                "enabled": bool(old.get("enabled", True)),
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
        old = existing.get(ident, {})
        slots.append({"id": ident, "kind": "topic", "subject_id": asset["id"],
            "label": asset.get("title", asset["id"]), "uses": uses, "path": asset["path"],
            "aliases": media.subject_aliases(asset),
            "source_path": asset["path"], "source_type": "visual_asset", "wikipedia_page": asset.get("wikipedia_page", ""),
            "required": True, "optional": False, "enabled": bool(old.get("enabled", True))})
    # Non-map cards deliberately use a dark editorial canvas. Expose that canvas
    # as an optional slot so the user can keep it or supply one full-scene image
    # before speech synthesis and the expensive render begin.
    direction = pack.get("visual_direction") or pack.get("metadata", {}).get("visual_direction", {})
    for scene in pack.get("scenes", []):
        kind = scene.get("scene_type", "")
        recovery = scene.get('visual_recovery') or {}
        manual = isinstance(recovery, dict) and recovery.get('placeholder') is True and recovery.get('version') == 1
        map_led = bool(direction.get("map_led") and kind in {"event_focus", "summary"})
        if pack.get("documentary_schema_version") != 2 and pack.get("schema_version") != 2:
            continue
        if (kind not in NONMAP_SCENES or map_led) and not manual:
            continue
        if kind in {"artwork", "document"} and scene.get("asset_ids"):
            continue
        ident = f"visual-background-{_safe(str(scene['id']))}"
        old = existing.get(ident, {})
        slot = {
            "id": ident, "kind": "scene", "subject_id": scene["id"],
            "label": ("Visuale da completare · " if manual else "Sfondo · ") + scene.get("title", f"Scena {scene['id']}"),
            "aliases": [],
            "uses": [{"scene_id": scene["id"], "cue": 0}],
            "path": f"assets/user/automatic/{ident}.jpg", "source_path": "",
            "source_type": "scene_background", "wikipedia_page": "", "optional": not manual,
            "required": manual, "enabled": bool(old.get("enabled", manual)),
        }
        if manual:
            slot['recovery_reason'] = str(recovery.get('reason', 'Visuale da completare.'))
            slot['aliases'] = [scene.get('title',str(scene['id']))]
        if old.get("replacement_media_id"):
            slot["replacement_media_id"] = old["replacement_media_id"]
        slots.append(slot)
    for item in pack.get("user_media", []):
        if not isinstance(item, dict) or str(item.get("id", "")).startswith("visual-"):
            continue
        bindings = item.get("bindings", [])
        binding = bindings[0] if bindings else {"kind": "topic", "label": item.get("title", "Immagine")}
        ident = f"visual-media-{_safe(str(item['id']))}";old = existing.get(ident, {})
        uses = [{"scene_id": scene["id"], "cue": inset.get("cue", 0)} for scene in pack.get("scenes", [])
                for inset in scene.get("image_insets", []) if inset.get("asset_id") == item.get("id")]
        if not uses:
            uses = [dict(use) for use in old.get("uses", [])]
        if not uses:
            continue
        slots.append({"id": ident, "kind": binding.get("kind", "topic"),
            "subject_id": item["id"], "label": binding.get("label") or item.get("title", "Immagine"), "uses": uses,
            "aliases": list(binding.get("aliases", [])),
            "path": item["path"], "source_path": item["path"], "source_type": "manual_media",
            "existing_media_id": item["id"], "wikipedia_page": "", "required": True, "optional": False,
            "enabled": bool(old.get("enabled", True))})
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
    try:
        info = store.read_json(metadata) if metadata.is_file() else {}
    except (OSError, ValueError):
        return "missing", {}
    if not isinstance(info, dict):
        return "missing", {}
    ex = info.get("extmetadata", {})
    if not isinstance(ex, dict) or any(not isinstance(value, dict) for value in ex.values()):
        return "missing", {}
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
        "license_url": value("LicenseUrl") or info.get("license_url", ""),
    }


def _usable_image(path, usage, declared=None):
    """Cached discovery has the same rules as a fresh download; uploads stay explicit."""
    state, info = _metadata_state(path)
    if state == "missing":
        return False
    if state == "blank":
        return True
    if info.get("h3_user_replacement"):
        return manual_allowed(_credit(info, path.stem, state), usage)
    if info:
        return metadata_policy(info, usage)["allowed"]
    # Authored visual assets can have their attribution in the pack itself.
    if declared and declared.get("license"):
        return metadata_policy({"extmetadata": {"LicenseShortName": {"value": declared["license"]},
            "LicenseUrl": {"value": declared.get("license_url", "")}}}, usage)["allowed"]
    return False


def _binding_match(item, slot):
    slot_terms = {media.normalized(term) for term in [slot.get("label", ""), *slot.get("aliases", [])] if media.normalized(term)}
    for binding in item.get("bindings", []):
        if binding.get("kind") != slot["kind"]:
            continue
        terms = [binding.get("label", ""), *binding.get("aliases", [])]
        if slot_terms.intersection(media.normalized(term) for term in terms if media.normalized(term)):
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
            "LicenseUrl": {"value": item.get("license_url", "")},
        },
    }
    store.write_json(target.with_suffix(".metadata.json"), metadata)
    slot["replacement_media_id"] = item["id"]
    return target, metadata


def seed_reusable(pack, work, records):
    """Place remembered subject images before acquisition so no web lookup is needed."""
    work = Path(work)
    slots = prepare(pack)
    reused = []
    for slot in slots:
        if slot.get("source_type") not in ("person", "place", "visual_asset"):
            continue
        if not slot.get("enabled", not slot.get("optional")):
            continue
        item = next((record for record in records if record.get("enabled") and manual_allowed(record, usage_for(pack)) and _binding_match(record, slot)), None)
        if item is None:
            continue
        target, metadata = _copy_replacement(item, slot, work)
        source_path = slot.get("source_path")
        if source_path:
            source = work / source_path
            if source != target:
                source.parent.mkdir(parents=True, exist_ok=True)
                source.unlink(missing_ok=True)
                shutil.copy2(target, source)
                source_meta = source.with_suffix(".metadata.json")
                source_meta.unlink(missing_ok=True)
                shutil.copy2(target.with_suffix(".metadata.json"), source_meta)
        reused.append({"slot_id": slot["id"], "label": slot["label"], "media_id": item["id"]})
    return reused


def _person_source(pack, slot, work):
    persons, _ = _collections(pack)
    row = next((p for p in persons if p.get("id") == slot["subject_id"]), None)
    if not row or not row.get("portrait"):
        return None
    source = work / row["portrait"]
    if not source.is_file():
        return None
    if not _usable_image(source, usage_for(pack)):
        # The battle/person renderer can also use the original portrait path.
        _placeholder({**slot, "path": row["portrait"]}, work)
        slot["search_note"] = "Immagine esclusa: licenza non compatibile con l’uso scelto."
    target = work / slot["path"]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True)
    shutil.copy2(source, target)
    meta = source.with_suffix(".metadata.json")
    if meta.is_file():
        shutil.copy2(meta, target.with_suffix(".metadata.json"))
    return target


def _placeholder(slot, work):
    """Create an original neutral card when an active reference has no image."""
    from PIL import Image, ImageDraw
    background = slot.get("source_type") == "scene_background"
    width, height = ((1280, 720) if background else (900, 650))
    image = Image.new("RGB", (width, height), (18, 45, 53));draw = ImageDraw.Draw(image, "RGBA")
    for index in range(9):
        x = round(width * index / 8);draw.line((x, 0, x, height), fill=(210, 181, 118, 24), width=1)
    for index in range(7):
        y = round(height * index / 6);draw.line((0, y, width, y), fill=(210, 181, 118, 20), width=1)
    radius = min(width, height) // 5;cx, cy = width // 2, height // 2
    draw.ellipse((cx-radius, cy-radius, cx+radius, cy+radius), outline=(210, 181, 118, 100), width=max(2,width//300))
    draw.line((cx-radius*2, cy, cx+radius*2, cy), fill=(210, 181, 118, 80), width=max(2,width//360))
    draw.line((cx, cy-radius*2, cx, cy+radius*2), fill=(210, 181, 118, 80), width=max(2,width//360))
    target = Path(work) / slot["path"];target.parent.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True);image.save(target, quality=91)
    store.write_json(target.with_suffix(".metadata.json"), {
        "descriptionurl": "generato localmente", "h3_placeholder": True,
        "extmetadata": {"ObjectName": {"value": "Riquadro generico per " + slot["label"]},
            "Artist": {"value": "H3-documentary"}, "LicenseShortName": {"value": "CC0-1.0"}},
    })
    return target


def materialize(pack, work, records=None, replacements_only=False):
    """Attach automatic cards or user replacements to the exact spoken cues."""
    work = Path(work)
    slots = prepare(pack)
    usage = usage_for(pack)
    records = [item for item in (records or []) if manual_allowed(item, usage)]
    old_entries = {x.get("id"): x for x in pack.get("user_media", []) if isinstance(x, dict)}
    manual_entries = [dict(x) for x in pack.get("user_media", []) if not str(x.get("id", "")).startswith("visual-") and manual_allowed(x, usage)]
    changed_scenes = set(pack.pop("_pending_visual_layout_scenes", []))
    superseded_manual_ids = set()
    disabled_manual_ids = {x["id"] for x in pack.get("user_media", []) if not str(x.get("id", "")).startswith("visual-") and not manual_allowed(x, usage)}
    disabled_asset_ids = set()
    automatic = []
    for slot in slots:
        enabled = bool(slot.get("enabled", not slot.get("optional")))
        if not enabled:
            if old_entries.get(slot["id"]):
                changed_scenes.update(use["scene_id"] for use in slot["uses"])
            if slot.get("source_type") == "visual_asset":
                disabled_asset_ids.add(slot["subject_id"])
                if slot["subject_id"] not in pack.get("disabled_visual_asset_ids", []):
                    changed_scenes.update(use["scene_id"] for use in slot["uses"])
            if slot.get("source_type") == "manual_media":
                disabled_manual_ids.add(slot.get("existing_media_id"))
                changed_scenes.update(use["scene_id"] for use in slot["uses"])
            continue
        current_manual=next((x for x in manual_entries if _binding_match(x,slot)),None) if slot.get('source_type') in ('person','place') else None
        current_ids={slot.get("existing_media_id"),slot.get('replacement_media_id'),current_manual.get('id') if current_manual else None}
        replacement = next((x for x in records if x.get("enabled") and x.get("id") not in current_ids and _binding_match(x, slot)), None)
        if current_manual and not replacement:
            continue
        if slot.get("source_type") == "visual_asset":
            asset = next(x for x in pack.get("visual_assets", []) if x["id"] == slot["subject_id"])
            was_placeholder = bool(asset.get("placeholder"))
            if slot["subject_id"] in pack.get("disabled_visual_asset_ids", []):
                changed_scenes.update(use["scene_id"] for use in slot["uses"])
            if replacement:
                source = media.folder(replacement["id"]) / "image.png"; target = work / slot["source_path"]
                previous_sha = hashlib.sha256(target.read_bytes()).hexdigest() if target.is_file() else ""
                target.unlink(missing_ok=True); target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, target)
                metadata = target.with_suffix(".metadata.json"); metadata.unlink(missing_ok=True)
                store.write_json(metadata, {"descriptionurl": replacement.get("source") or "caricamento locale", "h3_user_replacement": True,
                    "extmetadata": {"ObjectName": {"value": replacement["title"]}, "Artist": {"value": replacement.get("credit") or "attribuzione non indicata"},
                    "LicenseShortName": {"value": replacement.get("rights") or "diritti dichiarati dall’utente"},
                    "LicenseUrl": {"value": replacement.get("license_url", "")}}})
                current_sha = hashlib.sha256(target.read_bytes()).hexdigest()
                if current_sha != previous_sha: changed_scenes.update(use["scene_id"] for use in slot["uses"])
                asset.update(title=replacement["title"], creator=replacement.get("credit", ""), source=replacement.get("source") or "caricamento locale",
                             license=replacement.get("rights") or "diritti dichiarati dall’utente", license_url=replacement.get("license_url", ""))
                slot["replacement_media_id"] = replacement["id"]
            elif not _usable_image(work / slot["source_path"], usage, asset):
                previous_sha = hashlib.sha256((work / slot["source_path"]).read_bytes()).hexdigest() if (work / slot["source_path"]).is_file() else ""
                _placeholder(slot, work)
                if previous_sha != hashlib.sha256((work / slot["source_path"]).read_bytes()).hexdigest():
                    changed_scenes.update(use["scene_id"] for use in slot["uses"])
                slot["search_note"] = "Immagine esclusa: licenza non compatibile con l’uso scelto."
            image_state, image_info = _metadata_state(work / slot["source_path"])
            if image_info:
                credit = _credit(image_info, slot["label"], image_state)
                asset.update(creator=credit["credit"], source=credit["source"], license=credit["rights"], license_url=credit["license_url"])
                asset["placeholder"] = image_state == "blank"
                if was_placeholder or asset["placeholder"]:
                    asset["title"] = credit["title"]
            continue
        if slot.get("source_type") == "manual_media":
            if replacement:
                entry = next((x for x in manual_entries if x.get("id") == slot["existing_media_id"]), None)
                if entry:
                    target = work / entry["path"]; previous_sha = entry.get("image_sha256", "")
                    target.unlink(missing_ok=True); shutil.copy2(media.folder(replacement["id"]) / "image.png", target)
                    entry.update(title=replacement["title"], filename=replacement["filename"], image_sha256=replacement["image_sha256"], sha256=replacement["sha256"],
                                 credit=replacement.get("credit", ""), source=replacement.get("source", ""), rights=replacement.get("rights", ""), license_url=replacement.get("license_url", ""), origin="user_replacement")
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
            if previous and _usable_image(work / previous["path"], usage):
                automatic.append(previous)
                continue
            if not slot.get("required") and slot.get("source_type") != "scene_background":
                continue
            target = work / slot["path"]
            if slot["kind"] == "person":
                _person_source(pack, slot, work)
            if not target.is_file():
                _placeholder(slot, work)
            state, info = _metadata_state(target)
            origin = "automatic"
        else:
            if current_manual:
                continue
            target = work / slot["path"]
            if slot["kind"] == "person":
                _person_source(pack, slot, work)
            if not target.is_file() and (slot.get("required") or slot.get("source_type") == "scene_background"):
                _placeholder(slot, work)
            state, info = _metadata_state(target)
            origin = "automatic"
        if not target.is_file():
            continue
        if not _usable_image(target, usage):
            _placeholder(slot, work)
            state, info = _metadata_state(target)
            slot["search_note"] = "Immagine esclusa: licenza non compatibile con l’uso scelto."
        current_sha = hashlib.sha256(target.read_bytes()).hexdigest()
        previous_sha = old_entries.get(slot["id"], {}).get("image_sha256")
        if current_sha != previous_sha and (replacement or replacements_only):
            changed_scenes.update(use["scene_id"] for use in slot["uses"])
        credit = _credit(info, slot["label"], state)
        entry = {
            "id": slot["id"], "asset_id": slot["id"], "filename": target.name,
            "path": slot["path"], "image_sha256": current_sha, "sha256": current_sha,
            "origin": origin, "subject_kind": slot["kind"], "subject_id": slot["subject_id"],
            "bindings": [{"kind": slot["kind"], "label": slot["label"], "aliases": []}],
            "layout": {"x": .71, "y": .21, "width": .25, "fit": "cover" if slot.get("source_type") == "scene_background" else "contain"},
            "visual_state": state, **credit,
        }
        automatic.append(entry)
    pack["disabled_visual_asset_ids"] = sorted(disabled_asset_ids)
    pack["user_media"] = manual_entries + automatic
    by_scene = {scene["id"]: scene for scene in pack.get("scenes", [])}
    managed_manual_ids = {slot.get("existing_media_id") for slot in slots if slot.get("source_type") == "manual_media"}
    for scene in by_scene.values():
        if any(x.get("asset_id") in disabled_manual_ids for x in scene.get("image_insets", [])):
            changed_scenes.add(scene["id"])
        if str(scene.get("background_asset_id", "")).startswith("visual-background-"):
            scene.pop("background_asset_id", None)
        scene["image_insets"] = [x for x in scene.get("image_insets", []) if not str(x.get("asset_id", "")).startswith("visual-") and x.get('asset_id') not in (superseded_manual_ids | disabled_manual_ids | managed_manual_ids)]
    available = {x["id"] for x in automatic}
    for slot in slots:
        if not slot.get("enabled", not slot.get("optional")):
            continue
        if slot.get("source_type") == "manual_media":
            entry = next((x for x in manual_entries if x.get("id") == slot.get("existing_media_id")), None)
            if entry:
                for use in slot["uses"]:
                    scene = by_scene.get(use["scene_id"])
                    if scene is not None:
                        scene.setdefault("image_insets", []).append({"asset_id": entry["id"], "cue": use["cue"], "slot": 0, "slots": 1,
                            "title": entry["title"], "layout": entry["layout"], "sha256": entry["image_sha256"]})
            continue
        if slot["id"] not in available:
            continue
        entry = next(x for x in automatic if x["id"] == slot["id"])
        if slot.get("source_type") == "scene_background":
            scene = by_scene.get(slot["subject_id"])
            if scene is not None:
                scene["background_asset_id"] = slot["id"]
            continue
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
    if automatic:
        media.detach_blanket_license(pack)
    return sorted(changed_scenes)


def sync_timeline(pack, work):
    path = work / "build" / pack["slug"] / "timeline.json"
    if not path.is_file():
        raise ValueError("La voce e la timeline non sono ancora complete: riprendi prima la produzione normale.")
    timeline = store.read_json(path)
    for key in ("user_media","visual_slots","visual_assets","persons","disabled_visual_asset_ids"):
        if key in pack:timeline[key]=pack[key]
    for key in ("video_license", "base_video_license"):
        if key in pack:timeline[key]=pack[key]
        else:timeline.pop(key, None)
    if "asset_usage" in pack:timeline["asset_usage"]=pack["asset_usage"]
    authored = {s["id"]: s for s in pack["scenes"]}
    for scene in timeline["scenes"]:
        scene["image_insets"] = authored[scene["id"]].get("image_insets", [])
        if authored[scene["id"]].get("background_asset_id"):
            scene["background_asset_id"] = authored[scene["id"]]["background_asset_id"]
        else:
            scene.pop("background_asset_id", None)
    store.write_json(path, timeline)
    store.write_json(work / "timeline.json", timeline)
    return timeline


def status(pid):
    p = store.project(pid)
    try:
        packpath = project_pack(pid)
    except ValueError:
        return {"ready": False, "completed": False, "awaiting_review": False, "slots": [], "available_count": 0, "user_count": 0, "blank_count": 0, "empty_background_count": 0, "replacement_count": 0, "change_count": 0, "required_count": 0, "suggested_count": 0}
    pack = store.read_json(packpath)
    slots = derive(pack)
    selected = options(pid)
    layout_choices = layout_options(pid)
    entries = {x.get("id"): x for x in pack.get("user_media", []) if isinstance(x, dict)}
    records = [item for item in media.catalog() if manual_allowed(item, usage_for(pack))]
    result = []
    for slot in slots:
        saved_enabled = bool(slot.get("enabled", not slot.get("optional")))
        enabled = selected.get(slot["id"], saved_enabled)
        entry = entries.get(slot["id"], {})
        path = packpath.parents[2] / entry.get("path", slot["path"])
        if not path.is_file() and slot.get("source_path"):
            path = packpath.parents[2] / slot["source_path"]
        state, info = _metadata_state(path)
        if slot.get("source_type") == "scene_background" and state == "missing":
            state = "empty"
        current_manual=next((x for x in pack.get('user_media',[]) if not str(x.get('id','')).startswith('visual-') and _binding_match(x,slot)),None) if slot.get('source_type') in ('person','place') else None
        if entry.get("origin") == "user_replacement" or slot.get('source_type')=='manual_media' or current_manual:
            state = "user"
        current_ids={slot.get('existing_media_id'),slot.get('replacement_media_id'),current_manual.get('id') if current_manual else None}
        replacement = next((x for x in records if enabled and x.get("enabled") and x.get("id") not in current_ids and _binding_match(x, slot)), None)
        if not enabled:state = "disabled"
        elif slot.get("optional") and state in ("missing", "empty"):state = "blank"
        saved_layout=media.Layout.model_validate(entry.get("layout", {})).model_dump()
        layout=layout_choices.get(slot["id"],saved_layout)
        credit=_credit(info,slot["label"],state)
        result.append({**slot, "enabled": enabled, "state": state, "pending_option": enabled != saved_enabled,
                       "pending_layout": layout != saved_layout, "layout": layout, **credit,
                       "replacement_ready": bool(replacement), "has_preview": path.is_file(),
                       "replacement_title": replacement.get("title", "") if replacement else "",
                       "scene_ids": sorted({u["scene_id"] for u in slot["uses"]})})
    return {
        "ready": bool(result), "completed": p["status"] == "completed", "awaiting_review": p["status"] == "review" and bool(p.get("review_visuals")), "slots": result,
        "visual_warnings": [{**{k:w[k] for k in ('scene_index','scene_id','scene_title','element','reason','placeholder') if k in w},
                              'slot_id': 'visual-background-'+_safe(str(w.get('scene_id') or f"{w.get('scene_index',0)+1:02}")) if w.get('placeholder') else ''}
                             for w in pack.get('metadata',{}).get('visual_warnings',[])],
        "available_count": sum(x["state"] == "available" for x in result),
        "user_count": sum(x["state"] == "user" for x in result),
        "blank_count": sum(x["state"] in ("blank", "missing") for x in result),
        "empty_background_count": sum(x["source_type"] == "scene_background" and not x["enabled"] for x in result),
        "replacement_count": sum(x["replacement_ready"] for x in result),
        "change_count": sum(x["replacement_ready"] or x["pending_option"] or x["pending_layout"] for x in result),
        "required_count": sum(bool(x.get("required")) for x in result),
        "suggested_count": sum(bool(x.get("optional")) for x in result),
        "active_suggested_count": sum(bool(x.get("optional")) and x["enabled"] for x in result),
        "disabled_count": sum(not x["enabled"] for x in result),
    }


def slot_file(pid, slot_id):
    packpath=project_pack(pid);pack=store.read_json(packpath);work=packpath.parents[2]
    slot=next((x for x in derive(pack) if x['id']==slot_id),None)
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
