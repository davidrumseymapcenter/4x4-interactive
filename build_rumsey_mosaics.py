#!/usr/bin/env python3
"""Combine many small Rumsey tiles into a few browser-friendly image layers."""

from pathlib import Path
import argparse
import json
import re

from PIL import Image


ROOT = Path(__file__).resolve().parent
CATALOG = ROOT / "rumsey-maps.js"
OUTPUT = ROOT / "rumsey-mosaics"
TILE_PIXELS = 256
CHUNK_COLUMNS = 6
CHUNK_ROWS = 13


def read_catalog():
    text = CATALOG.read_text()
    match = re.search(r"window\.RUMSEY_KML_MAPS = (\[.*\]);", text)
    if not match:
        raise RuntimeError("Could not read rumsey-maps.js")
    return json.loads(match.group(1))


def write_catalog(entries):
    CATALOG.write_text(
        "// Generated from rumsey_collection.kmz. The three hand-configured maps remain in index.html.\n"
        + "window.RUMSEY_KML_MAPS = "
        + json.dumps(entries, ensure_ascii=False, separators=(",", ":"))
        + ";\n"
    )


def rounded(value):
    return round(value, 11)


def build_entry(entry, detail=False):
    source_key = "detailTiles" if detail else "overlays"
    overlays = entry.get(source_key, [])
    if not overlays:
        raise RuntimeError(f"{entry['id']} has no source tiles")

    longitudes = sorted(
        {rounded(point[0]) for overlay in overlays for point in overlay["coordinates"]}
    )
    latitudes = sorted(
        {rounded(point[1]) for overlay in overlays for point in overlay["coordinates"]},
        reverse=True,
    )
    longitude_index = {value: index for index, value in enumerate(longitudes)}
    latitude_index = {value: index for index, value in enumerate(latitudes)}

    placed = []
    for overlay in overlays:
        west = rounded(min(point[0] for point in overlay["coordinates"]))
        north = rounded(max(point[1] for point in overlay["coordinates"]))
        placed.append(
            {
                "path": ROOT / overlay["url"],
                "column": longitude_index[west],
                "row": latitude_index[north],
            }
        )

    OUTPUT.mkdir(exist_ok=True)
    output_prefix = f"{entry['id']}-detail" if detail else entry["id"]
    for old_file in OUTPUT.glob(f"{output_prefix}-*.png"):
        old_file.unlink()

    mosaic_overlays = []
    chunk_number = 0
    column_count = len(longitudes) - 1
    row_count = len(latitudes) - 1
    for first_row in range(0, row_count, CHUNK_ROWS):
        for first_column in range(0, column_count, CHUNK_COLUMNS):
            chunk_tiles = [
                tile
                for tile in placed
                if first_column <= tile["column"] < first_column + CHUNK_COLUMNS
                and first_row <= tile["row"] < first_row + CHUNK_ROWS
            ]
            if not chunk_tiles:
                continue
            columns = min(CHUNK_COLUMNS, column_count - first_column)
            rows = min(CHUNK_ROWS, row_count - first_row)
            mosaic = Image.new(
                "RGBA", (columns * TILE_PIXELS, rows * TILE_PIXELS), (0, 0, 0, 0)
            )
            for tile in chunk_tiles:
                with Image.open(tile["path"]) as source:
                    source = source.convert("RGBA")
                    source.thumbnail((TILE_PIXELS, TILE_PIXELS), Image.Resampling.LANCZOS)
                    x = (tile["column"] - first_column) * TILE_PIXELS
                    y = (tile["row"] - first_row) * TILE_PIXELS
                    mosaic.alpha_composite(source, (x, y))

            chunk_number += 1
            relative = Path("rumsey-mosaics") / f"{output_prefix}-{chunk_number}.png"
            mosaic.save(ROOT / relative, optimize=True)
            west = longitudes[first_column]
            east = longitudes[first_column + columns]
            north = latitudes[first_row]
            south = latitudes[first_row + rows]
            mosaic_overlays.append(
                {
                    "url": relative.as_posix(),
                    "coordinates": [
                        [west, north],
                        [east, north],
                        [east, south],
                        [west, south],
                    ],
                }
            )

    if detail:
        entry["detailOverlays"] = mosaic_overlays
        entry["detailMinZoom"] = 7.5
        entry["detailMosaicScale"] = TILE_PIXELS / 64
        entry.pop("detailTiles", None)
    else:
        preview_source = max(placed, key=lambda tile: tile["path"].stat().st_size)["path"]
        with Image.open(preview_source) as preview:
            preview = preview.convert("RGB")
            preview.thumbnail((240, 160), Image.Resampling.LANCZOS)
            preview_path = Path("rumsey-previews") / f"{entry['id']}-preview.jpg"
            preview.save(ROOT / preview_path, quality=88, optimize=True)
        entry["overlays"] = mosaic_overlays
        entry["previewUrl"] = preview_path.as_posix()
        entry["mosaicScale"] = TILE_PIXELS / 128
    print(
        f"{entry['id']}: combined {len(placed)} tiles into {len(mosaic_overlays)} mosaics",
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ids", nargs="+")
    parser.add_argument("--detail", action="store_true")
    args = parser.parse_args()
    entries = read_catalog()
    requested = set(args.ids)
    matches = [entry for entry in entries if entry["id"] in requested]
    if len(matches) != len(requested):
        found = {entry["id"] for entry in matches}
        raise SystemExit("Unknown IDs: " + ", ".join(sorted(requested - found)))
    for entry in matches:
        build_entry(entry, args.detail)
    write_catalog(entries)


if __name__ == "__main__":
    main()
