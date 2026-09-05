"""Manual map edits keep the same detailed battle terrain planning as compilation."""
import copy
import json
from pathlib import Path

from app.compiler import compile_pack

FIXTURE = Path(__file__).parent / "fixtures/review-battle-geography.json"


def battle():
    outline = {
        "title": "Battaglia di prova", "short_title": "Prova", "description": "Fixture tecnica.",
        "display_date": "18 giugno 1815", "factions": ["A", "B"], "commanders": [],
        "places": [{"id": "waterloo", "name": "Waterloo", "pos": [4.412, 50.68]},
                   {"id": "ferme", "name": "Fattoria", "pos": [4.416, 50.677]},
                   {"id": "ligny", "name": "Ligny", "pos": [4.87, 50.52]}],
        "scenes": [{"title": "Contesto", "date": "1815", "event": "Contesto della fixture.",
                    "focus": ["waterloo", "ferme", "ligny"], "source_ids": ["S1"], "routes": []},
                   {"title": "Dettaglio", "date": "1815", "event": "Dettaglio della fixture.",
                    "focus": ["waterloo", "ferme"], "source_ids": ["S1"], "routes": []},
                   {"title": "Conclusione", "date": "1815", "event": "Esito della fixture.",
                    "focus": ["waterloo", "ligny"], "source_ids": ["S1"], "routes": []}],
    }
    narration = [{"index": i, "lines": ["Testo " * 57, "Narrato " * 57], "fact": "Fixture", "kicker": "Prova"} for i in range(3)]
    sources = [{"id": "S1", "title": "Fonte tecnica", "url": "https://example.test", "retrieved": "2026-09-05"}]
    pack, geo = compile_pack(outline, narration, sources, {"id": "qa-geography", "minutes": 2}, {"fps": 24})
    return pack, geo, outline, narration


def test_extracted_terrain_helper_keeps_previous_compiler_geography_exactly():
    from app.compiler import geography_for_views
    pack, geo, _, _ = battle()
    # Captured from the unmodified 1.14.0 compiler before extracting its helper.
    assert geo == json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert geography_for_views(pack["atlas_locator"], [s["camera_end"] for s in pack["scenes"]]) == geo
    assert max(spec["zoom"] for spec in geo["patches"].values()) >= 14


def test_corrected_battle_pin_keeps_tactical_terrain_resolution():
    from app.review_changes import transform
    pack, geo, outline, narration = battle()
    before = copy.deepcopy(geo)
    _, updated, _, _, _ = transform(pack, geo, outline, narration,
                                   {"revision": "b" * 64, "scenes": [], "places": [{"id": "ferme", "pos": [4.421, 50.674]}]})
    assert geo == before
    assert updated["output"] == geo["output"]
    assert all(isinstance(spec, dict) and {"bounds", "zoom"} <= set(spec) for spec in updated["patches"].values())
    assert max(spec["zoom"] for spec in updated["patches"].values()) >= 14
    assert updated["bounds"][0] < 4.421 < updated["bounds"][2]
