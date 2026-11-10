#!/usr/bin/env python3
"""Download a denser georeferenced tile level for selected Rumsey maps."""

from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin
import argparse
import json
import re
import shutil
import tempfile

from PIL import Image

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
        existing_usable = [
            (order, items)
            for order, items in overlays_by_order.items()
            if 1 <= len(items) <= max_tiles
        ]
        if len(batch) > max_tiles and existing_usable:
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

        # Once a complete level is larger than the requested budget, every
        # descendant level will be larger still. Stop before crawling a much
        # larger branch merely to reject it.
        level_sizes = sorted(
            (order, len(items)) for order, items in overlays_by_order.items()
        )
        if (
            level_sizes
            and level_sizes[-1][1] > max_tiles
            and any(1 <= size <= max_tiles for _, size in level_sizes[:-1])
        ):
            break

    usable_levels = [
        (order, list(items.values()))
        for order, items in overlays_by_order.items()
        if 1 <= len(items) <= max_tiles
    ]
    if not usable_levels:
        raise RuntimeError("No complete high-resolution level was found")
    # Edge slivers can carry a higher drawOrder than the complete map level.
    # Prefer the densest usable level, then use drawOrder as the tie-breaker.
    return max(usable_levels, key=lambda item: (len(item[1]), item[0]))


def upgrade_entry(entry, max_tiles, detail):
    print(f"Inspecting {entry['id']}: {entry['name']}", flush=True)
    order, overlays = crawl_tile_tree(entry["kml"], max_tiles)
    print(f"  downloading level {int(order)} with {len(overlays)} tiles", flush=True)

    with tempfile.TemporaryDirectory(dir=ROOT) as temporary_directory:
        temporary = Path(temporary_directory)

        def download(item):
            index, overlay = item
            try:
                data, content_type, _ = fetch(overlay["remote"])
            except Exception as error:
                # Superoverlays commonly include empty edge cells whose image
                # URL returns 404. They are transparent space, not a reason to
                # discard the complete high-resolution level.
                print(
                    f"  skipping empty tile {index + 1}: {error}",
                    flush=True,
                )
                return index, None
            suffix = ".jpg" if "jpeg" in content_type else ".webp"
            level_label = f"-detail-l{int(order)}" if detail else ""
            filename = f"{entry['id']}{level_label}-{index + 1}{suffix}"
            if suffix == ".jpg":
                (temporary / filename).write_bytes(data)
            else:
                with Image.open(BytesIO(data)) as image:
                    image.save(
                        temporary / filename,
                        "WEBP",
                        lossless=True,
                        method=6,
                        exact=True,
                    )
            return index, {
                "url": f"rumsey-previews/{filename}",
                "coordinates": overlay["coordinates"],
            }

        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            attempted = list(pool.map(download, enumerate(overlays)))
        downloaded = [item for item in attempted if item[1] is not None]
        if not downloaded:
            raise RuntimeError("The selected level contained no downloadable tiles")

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
