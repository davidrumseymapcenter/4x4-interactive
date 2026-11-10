#!/usr/bin/env python3
"""Extract georeferenced preview overlays referenced by rumsey-maps.js."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from zipfile import ZipFile
import json
import re
import ssl
import sys
import xml.etree.ElementTree as ET

from PIL import Image

ROOT = Path(__file__).resolve().parent
CATALOG = ROOT / "rumsey-maps.js"
ASSETS = ROOT / "rumsey-previews"
USER_AGENT = "4x4 Interactive historical map importer"
SSL_CONTEXT = ssl._create_unverified_context()
MAX_PREVIEW_TILES = 64
LOW_RESOLUTION_TILE_COUNT = 8


def local_name(tag):
    return tag.rsplit("}", 1)[-1]


def children(node, name):
    return [child for child in node.iter() if local_name(child.tag) == name]


def child_text(node, name, default=""):
    for child in node.iter():
        if local_name(child.tag) == name and child.text:
            return child.text.strip()
    return default


def fetch(url):
    url = url.replace("http://", "https://", 1)
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=18, context=SSL_CONTEXT) as response:
        return response.read(), response.headers.get_content_type(), response.geturl()


def read_kml(data):
    if data[:2] == b"PK":
        with ZipFile(BytesIO(data)) as archive:
            names = [name for name in archive.namelist() if name.lower().endswith(".kml")]
            preferred = next((name for name in names if name.lower().endswith("doc.kml")), names[0])
            return archive.read(preferred)
    return data


def parse_overlays(data):
    root = ET.fromstring(read_kml(data))
    overlays = []
    for overlay in children(root, "GroundOverlay"):
        href = ""
        for icon in children(overlay, "Icon"):
            href = child_text(icon, "href")
            if href:
                break
        box_nodes = children(overlay, "LatLonBox")
        if not href or not box_nodes:
            continue
        box = box_nodes[0]
        try:
            north = float(child_text(box, "north"))
            south = float(child_text(box, "south"))
            east = float(child_text(box, "east"))
            west = float(child_text(box, "west"))
            draw_order = float(child_text(overlay, "drawOrder", "0"))
        except ValueError:
            continue
        if not (-90 <= south < north <= 90 and -180 <= west <= 180 and -180 <= east <= 180):
            continue
        overlays.append(
            {
                "href": href,
                "drawOrder": draw_order,
                "coordinates": [
                    [west, north],
                    [east, north],
                    [east, south],
                    [west, south],
                ],
            }
        )
    links = []
    for network_link in children(root, "NetworkLink"):
        href = child_text(network_link, "href")
        if href:
            links.append(href)
    return overlays, links


def highest_detail(overlays):
    if not overlays:
        return []
    maximum = max(item["drawOrder"] for item in overlays)
    return [item for item in overlays if item["drawOrder"] == maximum]


def find_overlays(start_url):
    queue = [start_url]
    visited = set()
    for _ in range(12):
        if not queue:
            break
        url = queue.pop(0).replace("http://", "https://", 1)
        if url in visited:
            continue
        visited.add(url)
        data, _, final_url = fetch(url)
        overlays, links = parse_overlays(data)
        if overlays:
            for item in overlays:
                item["remote"] = urljoin(final_url, item.pop("href"))
            current_best = highest_detail(overlays)
            if len(current_best) < 8 and links:
                child_results = []

                def read_child(href):
                    child_url = urljoin(final_url, href)
                    child_data, _, child_final_url = fetch(child_url)
                    child_items, _ = parse_overlays(child_data)
                    best_items = highest_detail(child_items)
                    for item in best_items:
                        item["remote"] = urljoin(
                            child_final_url,
                            item.pop("href"),
                        )
                    return best_items

                child_hrefs = links[:8]
                all_children_loaded = True
                with ThreadPoolExecutor(max_workers=4) as child_pool:
                    child_futures = [
                        child_pool.submit(read_child, href) for href in child_hrefs
                    ]
                    for child_future in as_completed(child_futures):
                        try:
                            items = child_future.result()
                            if not items:
                                all_children_loaded = False
                            child_results.extend(items)
                        except Exception:
                            all_children_loaded = False
                if all_children_loaded and 0 < len(child_results) <= MAX_PREVIEW_TILES:
                    child_rank = max(item["drawOrder"] for item in overlays) + 1
                    for item in child_results:
                        item["drawOrder"] = child_rank
                    overlays.extend(child_results)
            return overlays
        for href in links[:8]:
            queue.append(urljoin(final_url, href))
    return []


def import_entry(entry):
    overlays = find_overlays(entry["kml"])

    def download_overlay(index, overlay):
        data, content_type, _ = fetch(overlay["remote"])
        suffix = ".jpg" if "jpeg" in content_type else ".webp"
        relative = Path("rumsey-previews") / f"{entry['id']}-{index + 1}{suffix}"
        if suffix == ".jpg":
            (ROOT / relative).write_bytes(data)
        else:
            with Image.open(BytesIO(data)) as image:
                image.save(
                    ROOT / relative,
                    "WEBP",
                    lossless=True,
                    method=6,
                    exact=True,
                )
        return index, {
            "url": relative.as_posix(),
            "coordinates": overlay["coordinates"],
        }

    levels = sorted({item["drawOrder"] for item in overlays}, reverse=True)
    for level in levels:
        candidates = [item for item in overlays if item["drawOrder"] == level]
        if not candidates or len(candidates) > MAX_PREVIEW_TILES:
            continue
        saved_with_indexes = []
        with ThreadPoolExecutor(max_workers=8) as image_pool:
            image_futures = [
                image_pool.submit(download_overlay, index, overlay)
                for index, overlay in enumerate(candidates)
            ]
            for image_future in as_completed(image_futures):
                try:
                    saved_with_indexes.append(image_future.result())
                except Exception:
                    continue
        if len(saved_with_indexes) >= max(1, int(len(candidates) * 0.75)):
            saved = [item for _, item in sorted(saved_with_indexes)]
            saved_paths = {ROOT / item["url"] for item in saved}
            for old_file in ASSETS.glob(f"{entry['id']}-*"):
                if old_file not in saved_paths:
                    old_file.unlink()
            return entry["id"], saved
    return entry["id"], []


def main():
    match = re.search(r"window\.RUMSEY_KML_MAPS = (\[.*\]);", CATALOG.read_text())
    entries = json.loads(match.group(1))
    ASSETS.mkdir(exist_ok=True)
    completed = 0
    succeeded = 0
    upgrade_low_resolution = "--upgrade-low-resolution" in sys.argv[1:]
    requested_ids = {
        value.removeprefix("--ids=")
        for value in sys.argv[1:]
        if value.startswith("--ids=")
    }
    selected_entries = [
        entry
        for entry in entries
        if (not requested_ids or entry["id"] in requested_ids)
        and (
            not upgrade_low_resolution
            or len(entry.get("overlays", [])) < LOW_RESOLUTION_TILE_COUNT
        )
    ]
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(import_entry, entry): entry for entry in selected_entries}
        for future in as_completed(futures):
            entry = futures[future]
            completed += 1
            try:
                _, overlays = future.result()
                if overlays or not upgrade_low_resolution:
                    entry["overlays"] = overlays
                if overlays:
                    entry.pop("overlayError", None)
                succeeded += bool(overlays)
            except Exception as error:
                entry["overlays"] = []
                entry["overlayError"] = str(error)[:180]
            if completed % 20 == 0 or completed == len(selected_entries):
                print(
                    f"Processed {completed}/{len(selected_entries)}; previews found for {succeeded}",
                    flush=True,
                )
    CATALOG.write_text(
        "// Generated from rumsey_collection.kmz. The three hand-configured maps remain in index.html.\n"
        + "window.RUMSEY_KML_MAPS = "
        + json.dumps(entries, ensure_ascii=False, separators=(",", ":"))
        + ";\n"
    )
    available = sum(bool(entry.get("overlays")) for entry in entries)
    print(
        f"Finished: {available}/{len(entries)} catalog maps have local georeferenced previews"
    )


if __name__ == "__main__":
    sys.exit(main())
