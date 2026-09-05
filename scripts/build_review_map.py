"""Build the small, offline orientation map from an existing Natural Earth land file.

Development utility, using only the Python standard library. It never modifies
the source geography shared with documentary workspaces. No project data or
historical boundaries are included in the output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def simplify_line(points: list, tolerance: float) -> list:
    """Douglas–Peucker: retain original vertices within a fixed angular tolerance."""
    if len(points) <= 2:
        return points
    keep = {0, len(points) - 1}
    pending = [(0, len(points) - 1)]
    limit = tolerance * tolerance
    while pending:
        start, end = pending.pop()
        ax, ay = points[start][:2]
        bx, by = points[end][:2]
        dx, dy = bx - ax, by - ay
        length = dx * dx + dy * dy
        largest, selected = limit, None
        for index in range(start + 1, end):
            px, py = points[index][:2]
            t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / length)) if length else 0
            distance = (px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2
            if distance > largest:
                largest, selected = distance, index
        if selected is not None:
            keep.add(selected)
            pending.extend(((start, selected), (selected, end)))
    return [points[index] for index in sorted(keep)]


def simplify_ring(raw: list, tolerance: float) -> list:
    points = [point[:2] for point in raw]
    if points and points[-1] == points[0]:
        points = points[:-1]
    if len(points) < 3:
        raise ValueError("Natural Earth contains an invalid polygon ring")
    split = max(range(1, len(points)), key=lambda i: math.dist(points[0], points[i]))
    simplified = simplify_line(points[:split + 1], tolerance)[:-1]
    simplified += simplify_line(points[split:] + points[:1], tolerance)[:-1]
    if len(simplified) < 3:
        # Keep at least three original, non-collinear vertices for tiny islands.
        # Their angular extent is below the overview's simplification tolerance.
        ax, ay = points[0]
        bx, by = points[split]
        third = max((i for i in range(len(points)) if i not in (0, split)),
                    key=lambda i: abs((bx - ax) * (points[i][1] - ay) - (by - ay) * (points[i][0] - ax)))
        simplified = [points[i] for i in sorted((0, split, third))]
    result = []
    for x, y in simplified:
        point = [round(x, 4), round(y, 4)]
        if not result or point != result[-1]:
            result.append(point)
    if len({tuple(point) for point in result}) < 3:
        result = points  # Preserve genuine sub-rounding islands unchanged.
    if result[0] != result[-1]:
        result.append(result[0])
    return result


def build(source: Path, output: Path, tolerance: float = 0.1) -> dict:
    source_bytes = source.read_bytes()
    source_data = json.loads(source_bytes)
    features = []
    for feature in source_data["features"]:
        geometry = feature["geometry"]
        kind = geometry["type"]
        if kind not in {"Polygon", "MultiPolygon"}:
            raise ValueError(f"Unexpected geometry: {kind}")
        polygons = geometry["coordinates"] if kind == "MultiPolygon" else [geometry["coordinates"]]
        coordinates = [[simplify_ring(ring, tolerance) for ring in polygon] for polygon in polygons]
        features.append({"type": "Feature", "properties": {}, "geometry": {
            "type": kind, "coordinates": coordinates if kind == "MultiPolygon" else coordinates[0],
        }})
    data = {"type": "FeatureCollection", "name": "Natural Earth land — orientation only",
            "bbox": [-180, -90, 180, 90], "features": features}
    encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(encoded)
    return {"source_sha256": hashlib.sha256(source_bytes).hexdigest(),
            "output_sha256": hashlib.sha256(encoded).hexdigest(), "bytes": len(encoded),
            "features": len(features), "tolerance_degrees": tolerance, "coordinate_decimal_places": 4}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "pipeline/assets/geography/land.geojson")
    parser.add_argument("--output", type=Path, default=ROOT / "static/maps/world-land.geojson")
    parser.add_argument("--tolerance", type=float, default=0.1)
    args = parser.parse_args()
    if not math.isfinite(args.tolerance) or args.tolerance <= 0:
        parser.error("--tolerance must be a positive finite number")
    if args.source.resolve() == args.output.resolve():
        parser.error("The source is immutable; choose a separate output")
    print(json.dumps(build(args.source, args.output, args.tolerance), indent=2))


if __name__ == "__main__":
    main()
