#!/usr/bin/env python3
"""Build lazy, high-resolution manifests from Rumsey KML superoverlays."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import argparse
import json

from upgrade_rumsey_resolution import crawl_tile_tree, read_catalog, write_catalog


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "rumsey-details"


def build(entry, max_tiles):
    order, overlays = crawl_tile_tree(entry["kml"], max_tiles)
    payload = {
        "id": entry["id"],
        "resolutionLevel": int(order),
        "overlays": [
            {"url": overlay["remote"], "coordinates": overlay["coordinates"]}
            for overlay in overlays
        ],
    }
    return entry["id"], payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ids", nargs="*")
    parser.add_argument("--max-tiles", type=int, default=320)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    entries = read_catalog()
    requested = set(args.ids)
    candidates = [
        entry
        for entry in entries
        if not entry.get("georeferencerTiles")
        and (not requested or entry["id"] in requested)
    ]
    missing = requested - {entry["id"] for entry in entries}
    if missing:
        raise SystemExit("Unknown IDs: " + ", ".join(sorted(missing)))

    OUTPUT.mkdir(exist_ok=True)
    completed = {}
    failures = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(build, entry, args.max_tiles): entry for entry in candidates
        }
        for number, future in enumerate(as_completed(futures), 1):
            entry = futures[future]
            try:
                map_id, payload = future.result()
                path = OUTPUT / f"{map_id}.json"
                path.write_text(
                    json.dumps(payload, separators=(",", ":")) + "\n"
                )
                completed[map_id] = payload
                print(
                    f"[{number}/{len(candidates)}] {map_id}: "
                    f"level {payload['resolutionLevel']}, "
                    f"{len(payload['overlays'])} tiles",
                    flush=True,
                )
            except Exception as error:
                failures.append((entry["id"], str(error)))
                print(
                    f"[{number}/{len(candidates)}] {entry['id']}: {error}",
                    flush=True,
                )

    for entry in entries:
        if entry["id"] in completed:
            entry["detailManifest"] = f"rumsey-details/{entry['id']}.json"
            entry["detailResolutionLevel"] = completed[entry["id"]][
                "resolutionLevel"
            ]
            # The remote manifest supersedes older downloaded detail mosaics.
            entry.pop("detailOverlays", None)
            entry.pop("detailTiles", None)
            entry.pop("detailMinZoom", None)
            entry.pop("detailMosaicScale", None)
    write_catalog(entries)
    print(f"Built {len(completed)}/{len(candidates)} lazy detail manifests.")
    if failures:
        print("Failures:")
        for map_id, error in failures:
            print(f"  {map_id}: {error}")


if __name__ == "__main__":
    main()
