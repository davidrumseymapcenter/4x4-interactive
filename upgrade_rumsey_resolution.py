#!/usr/bin/env python3
"""Download a denser georeferenced tile level for selected Rumsey maps."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin
import argparse
import json
import re
import shutil
import tempfile

from import_rumsey_previews import fetch, parse_overlays


ROOT = Path(__file__).resolve().parent
CATALOG = ROOT / "rumsey-maps.js"
DEFAULT_MAX_TILES = 320
MAX_TREE_DEPTH = 6
WORKERS = 20


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


def crawl_tile_tree(start_url, max_tiles):
    frontier = [start_url]
    visited = set()
    overlays_by_order = {}

    for depth in range(MAX_TREE_DEPTH):
        batch = [url for url in frontier if url not in visited]
        if not batch:
            break
        visited.update(batch)

        def read_document(url):
            try:
                data, _, final_url = fetch(url)
                overlays, links = parse_overlays(data)
                for overlay in overlays:
                    overlay["remote"] = urljoin(final_url, overlay.pop("href"))
                return overlays, [urljoin(final_url, link) for link in links]
            except Exception:
                return [], []

        frontier = []
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            for overlays, links in pool.map(read_document, batch):
                frontier.extend(links)
                for overlay in overlays:
                    level = overlays_by_order.setdefault(overlay["drawOrder"], {})
                    level[overlay["remote"]] = overlay

        counts = ", ".join(
            f"{int(order)}:{len(items)}"
            for order, items in sorted(overlays_by_order.items())
        )
        print(f"  depth {depth}: {len(batch)} documents; levels {counts}", flush=True)

    usable_levels = [
        (order, list(items.values()))
        for order, items in overlays_by_order.items()
        if 4 <= len(items) <= max_tiles
    ]
    if not usable_levels:
        raise RuntimeError("No complete high-resolution level was found")
    return max(usable_levels, key=lambda item: item[0])


def upgrade_entry(entry, max_tiles, detail):
    print(f"Inspecting {entry['id']}: {entry['name']}", flush=True)
    order, overlays = crawl_tile_tree(entry["kml"], max_tiles)
    print(f"  downloading level {int(order)} with {len(overlays)} tiles", flush=True)

    with tempfile.TemporaryDirectory(dir=ROOT) as temporary_directory:
        temporary = Path(temporary_directory)

        def download(item):
            index, overlay = item
            data, content_type, _ = fetch(overlay["remote"])
            suffix = ".jpg" if "jpeg" in content_type else ".png"
            level_label = f"-detail-l{int(order)}" if detail else ""
            filename = f"{entry['id']}{level_label}-{index + 1}{suffix}"
            (temporary / filename).write_bytes(data)
            return index, {
                "url": f"rumsey-previews/{filename}",
                "coordinates": overlay["coordinates"],
            }

        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            downloaded = list(pool.map(download, enumerate(overlays)))

        if not detail:
            old_files = list((ROOT / "rumsey-previews").glob(f"{entry['id']}-*"))
            for old_file in old_files:
                old_file.unlink()
        for source in temporary.iterdir():
            shutil.move(source, ROOT / "rumsey-previews" / source.name)

    if detail:
        entry["detailTiles"] = [item for _, item in sorted(downloaded)]
        entry["detailResolutionLevel"] = int(order)
    else:
        entry["overlays"] = [item for _, item in sorted(downloaded)]
        entry["resolutionLevel"] = int(order)
    entry.pop("overlayError", None)
    print(f"  saved {len(downloaded)} high-resolution tiles", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ids", nargs="+", help="Catalog IDs such as rumsey-1")
    parser.add_argument("--max-tiles", type=int, default=DEFAULT_MAX_TILES)
    parser.add_argument("--detail", action="store_true")
    args = parser.parse_args()
    requested = set(args.ids)
    entries = read_catalog()
    matches = [entry for entry in entries if entry["id"] in requested]
    missing = requested - {entry["id"] for entry in matches}
    if missing:
        raise SystemExit("Unknown IDs: " + ", ".join(sorted(missing)))
    for entry in matches:
        upgrade_entry(entry, args.max_tiles, args.detail)
    write_catalog(entries)


if __name__ == "__main__":
    main()
