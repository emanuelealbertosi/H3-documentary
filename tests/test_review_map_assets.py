"""The coordinate editor is self-contained and uses public geographic input."""
import base64
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_leaflet_local_distribution_matches_official_stable_integrity():
    directory = ROOT / "static/vendor/leaflet"
    hashes = {
        "leaflet.js": "20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=",
        "leaflet.css": "p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=",
    }
    for filename, expected in hashes.items():
        assert base64.b64encode(hashlib.sha256((directory / filename).read_bytes()).digest()).decode() == expected
    for filename in ("layers.png", "layers-2x.png", "marker-icon.png", "marker-icon-2x.png", "marker-shadow.png"):
        assert (directory / "images" / filename).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert "BSD 2-Clause License" in (directory / "LICENSE").read_text(encoding="utf-8")


def test_offline_map_has_valid_closed_wgs84_rings_and_no_project_attributes():
    path = ROOT / "static/maps/world-land.geojson"
    assert path.stat().st_size < 1_000_000
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["type"] == "FeatureCollection"
    assert data["bbox"] == [-180, -90, 180, 90]
    assert data["features"]
    polygons = 0
    for feature in data["features"]:
        assert feature["properties"] == {}
        geometry = feature["geometry"]
        assert geometry["type"] in {"Polygon", "MultiPolygon"}
        coordinates = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
        for polygon in coordinates:
            polygons += 1
            for ring in polygon:
                assert len(ring) >= 4
                assert ring[0] == ring[-1]
                assert len({tuple(point) for point in ring}) >= 3
                for longitude, latitude in ring:
                    assert math.isfinite(longitude) and -180 <= longitude <= 180
                    assert math.isfinite(latitude) and -90 <= latitude <= 90
    assert polygons > 1000  # The overview retains islands rather than one schematic continent.


def test_map_builder_is_deterministic_and_preserves_immutable_source(tmp_path):
    from scripts.build_review_map import build
    source = tmp_path / "original.geojson"
    source.write_text(json.dumps({"type": "FeatureCollection", "features": [{
        "properties": {"discarded": "not exported"}, "geometry": {"type": "Polygon", "coordinates": [
            [[0, 0], [0, 1], [0.0001, 1.001], [1, 1], [1, 0], [0, 0]],
        ]},
    }]}))
    original = source.read_bytes()
    first, second = tmp_path / "first.geojson", tmp_path / "second.geojson"
    report = build(source, first)
    assert report == build(source, second)
    assert first.read_bytes() == second.read_bytes()
    assert source.read_bytes() == original
    assert json.loads(first.read_text(encoding="utf-8"))["features"][0]["properties"] == {}
