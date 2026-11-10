#!/usr/bin/env python3
"""Match catalog maps to Rumsey records and enable high-resolution Allmaps tiles.

The LUNA IIIF service exposes the original scan at full resolution. When an
Allmaps georeference exists for that scan, the application can use its XYZ
tiles directly and request appropriate source pixels at every map zoom.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlencode
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import hashlib
import json
import re
import ssl
import time


ROOT = Path(__file__).resolve().parent
CATALOG = ROOT / "rumsey-maps.js"
CACHE = ROOT / ".rumsey-source-cache.json"
LUNA_SEARCH = "https://www.davidrumsey.com/luna/servlet/as/search"
USER_AGENT = "4x4 Interactive Rumsey source resolver"
SSL_CONTEXT = ssl._create_unverified_context()
WORKERS = 4
STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "by", "for", "from", "in",
    "is", "it", "map", "maps", "of", "on", "or", "that", "the", "this",
    "to", "was", "were", "with",
}


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


def fetch_json(url):
    last_error = None
    for attempt in range(4):
        request = Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urlopen(request, timeout=35, context=SSL_CONTEXT) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            # Missing Allmaps annotations are an expected result. Retrying a
            # definitive 4xx response only makes a catalog refresh take many
            # minutes.
            if 400 <= error.code < 500:
                raise
            last_error = error
            time.sleep(1.5 * (attempt + 1))
        except Exception as error:
            last_error = error
            time.sleep(1.5 * (attempt + 1))
    raise last_error


def tokens(text):
    return {
        token
        for token in re.findall(r"[a-z0-9]+", (text or "").lower())
        if token not in STOP_WORDS and len(token) > 1
    }


def field_text(result):
    values = []
    for field in result.get("fieldValues", []):
        for field_values in field.values():
            values.extend(str(value) for value in field_values)
    return " ".join(values)


def candidate_score(entry, result):
    display_name = result.get("displayName", "")
    candidate_text = display_name + " " + field_text(result)
    candidate_tokens = tokens(candidate_text)
    title_tokens = tokens(display_name)
    summary_tokens = tokens(entry.get("summary", ""))
    name_tokens = tokens(re.sub(r"\b\d{3,4}(?:[–-]\d{2,4})?\b", "", entry["name"]))
    summary_coverage = len(summary_tokens & candidate_tokens) / max(1, len(summary_tokens))
    name_coverage = len(name_tokens & candidate_tokens) / max(1, len(name_tokens))
    title_coverage = len(name_tokens & title_tokens) / max(1, len(name_tokens))
    year = re.search(r"\d{4}", str(entry.get("date", "")))
    date_match = bool(year and year.group() in candidate_text)
    title = result.get("displayName", "").lower()
    composite_bonus = 0.22 if "composite" in title else 0
    globe_bonus = 0.15 if "globe" in entry["name"].lower() and "interactive globe" in title else 0
    index_penalty = 0.12 if "index" in title and "index" not in entry["name"].lower() else 0
    score = summary_coverage + name_coverage * 0.35 + date_match * 0.2
    score += title_coverage * 0.3 + composite_bonus + globe_bonus - index_penalty
    return score, summary_coverage, name_coverage, title_coverage, date_match


def search_queries(entry):
    summary_words = [
        word
        for word in re.findall(r"[A-Za-z0-9']+", entry.get("summary", ""))
        if word.lower() not in STOP_WORDS and len(word) > 2
    ]
    queries = []
    if summary_words:
        queries.append(" ".join(summary_words[:8]))
    name_without_year = re.sub(r"\b\d{3,4}(?:[–-]\d{2,4})?\b", "", entry["name"])
    queries.append(name_without_year.replace("_", " ").strip())
    return list(dict.fromkeys(query for query in queries if query))


def search_luna(query):
    url = LUNA_SEARCH + "?" + urlencode(
        {
            "q": query,
            "lc": "RUMSEY~8~1",
            "os": 0,
            "bs": 50,
            "fullData": "true",
        }
    )
    _, payload = fetch_json(url)
    return payload.get("results", [])


def resolve_entry(entry):
    existing = re.search(
        r"(RUMSEY~8~1~\d+~\d+)", entry.get("sourceUrl", "")
    )
    if existing:
        return existing.group(1), "existing", 10

    candidates = {}
    for query in search_queries(entry):
        try:
            for result in search_luna(query):
                candidates[result["id"]] = result
        except Exception:
            continue
        if candidates:
            break
    ranked = sorted(
        (
            candidate_score(entry, result),
            result.get("id", ""),
            result,
        )
        for result in candidates.values()
    )
    if not ranked:
        return None, "no results", 0
    metrics, _, result = ranked[-1]
    runner_up = ranked[-2][0][0] if len(ranked) > 1 else 0
    score, summary_coverage, name_coverage, title_coverage, date_match = metrics
    margin = score - runner_up
    entry_has_year = bool(re.search(r"\d{4}", str(entry.get("date", ""))))
    confident = (
        (summary_coverage >= 0.55 and (margin >= 0.04 or title_coverage >= 0.7))
        or (summary_coverage >= 0.42 and date_match and margin >= 0.08)
        or (not entry.get("summary") and title_coverage >= 0.8 and date_match)
    )
    if entry_has_year and not date_match:
        confident = False
    reason = (
        f"score={score:.2f}, summary={summary_coverage:.2f}, "
        f"name={name_coverage:.2f}, title={title_coverage:.2f}, "
        f"date={'yes' if date_match else 'no'}, margin={margin:.2f}"
    )
    return (result["id"] if confident else None), reason, score


def allmaps_details(media_id):
    manifest = (
        "https://www.davidrumsey.com/luna/servlet/iiif/m/"
        + media_id
        + "/manifest"
    )
    manifest_id = hashlib.sha1(manifest.encode()).hexdigest()[:16]
    annotation_url = f"https://annotations.allmaps.org/manifests/{manifest_id}"
    try:
        status, annotation = fetch_json(annotation_url)
        if status == 200 and annotation.get("items"):
            return manifest, manifest_id
    except Exception:
        pass
    return manifest, None


def main():
    entries = read_catalog()
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    to_resolve = [entry for entry in entries if entry["id"] not in cache]
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(resolve_entry, entry): entry for entry in to_resolve}
        for number, future in enumerate(as_completed(futures), 1):
            entry = futures[future]
            try:
                media_id, reason, score = future.result()
            except Exception as error:
                media_id, reason, score = None, str(error), 0
            cache[entry["id"]] = {
                "mediaId": media_id,
                "reason": reason,
                "score": score,
            }
            print(
                f"Matched {number}/{len(to_resolve)}: {entry['id']} -> "
                f"{media_id or 'review needed'} ({reason})",
                flush=True,
            )
    CACHE.write_text(json.dumps(cache, indent=2, ensure_ascii=False) + "\n")

    matched = [
        (entry, cache.get(entry["id"], {}).get("mediaId"))
        for entry in entries
        if cache.get(entry["id"], {}).get("mediaId")
    ]
    allmaps = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            pool.submit(allmaps_details, media_id): (entry, media_id)
            for entry, media_id in matched
        }
        for number, future in enumerate(as_completed(futures), 1):
            entry, media_id = futures[future]
            manifest, manifest_id = future.result()
            allmaps[entry["id"]] = (manifest, manifest_id)
            print(
                f"Checked tiles {number}/{len(matched)}: {entry['id']} "
                + ("available" if manifest_id else "fallback"),
                flush=True,
            )

    official_tiles = 0
    for entry, media_id in matched:
        manifest, manifest_id = allmaps[entry["id"]]
        entry["sourceUrl"] = (
            "https://www.davidrumsey.com/luna/servlet/detail/" + media_id
        )
        entry["iiifManifest"] = manifest
        entry["imageUrl"] = (
            "https://www.davidrumsey.com/luna/servlet/iiif/"
            + media_id
            + "/full/!1600,1600/0/default.jpg"
        )
        if manifest_id:
            entry["georeferencerTiles"] = (
                f"https://allmaps.xyz/manifests/{manifest_id}/"
                "{z}/{x}/{y}@2x.png"
            )
            entry["georeferencerUrl"] = (
                "https://viewer.allmaps.org/?url=" + manifest
            )
            entry["georeferencerMinZoom"] = 0
            # Allmaps requests the needed regions from the Rumsey IIIF master
            # at each zoom. Keep the retina tile endpoint available through
            # close inspection instead of stretching a low-resolution image.
            entry["georeferencerMaxZoom"] = 22
            official_tiles += 1
    write_catalog(entries)
    print(
        f"Updated {len(matched)}/{len(entries)} catalog records; "
        f"official high-resolution tiles available for {official_tiles}."
    )


if __name__ == "__main__":
    main()
