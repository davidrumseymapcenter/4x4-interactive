#!/usr/bin/env python3
"""Fetch Stairwell Map metadata from the official David Rumsey LUNA API."""

import json
import ssl
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "stairwell-maps.js"
COLLECTION = "RUMSEY~8~1"
API = "https://www.davidrumsey.com/luna/servlet/as/search"
SSL_CONTEXT = ssl._create_unverified_context()
RECORDS = {
    "stairwell-grand-canon": "1314~90145",
    "stairwell-south-america": "240074~90115526",
    "stairwell-afrique-spheroidale": "22016~700048",
    "stairwell-nova-granada": "285936~90058454",
    "stairwell-utah-basin": "1943~140018",
    "stairwell-mountains-rivers": "1963~150001",
    "stairwell-nanzenbushu": "34362~1171565",
    "stairwell-celestial": "231321~5508809",
    "stairwell-new-york": "263156~5524103",
    "stairwell-dai-toa": "289702~90133892",
}


def fetch_record(record_suffix):
    luna_id = f"{COLLECTION}~{record_suffix}"
    url = API + "?" + urlencode({"mid": luna_id})
    request = Request(url, headers={"User-Agent": "4x4 Interactive metadata importer"})
    with urlopen(request, context=SSL_CONTEXT, timeout=30) as response:
        result = json.load(response)["results"][0]

    fields = []
    lookup = {}
    for field_value in result.get("fieldValues", []):
        for label, values in field_value.items():
            clean_values = [str(value).strip() for value in values if str(value).strip()]
            if clean_values:
                fields.append({"label": label, "values": clean_values})
                lookup[label] = clean_values

    def first(label, default=""):
        return lookup.get(label, [default])[0]

    authors = lookup.get("Authors") or lookup.get("Author") or []
    subjects = lookup.get("Subject", [])
    geographic = []
    for label in ("World Area", "Country", "State/Province", "Region", "City"):
        geographic.extend(lookup.get(label, []))
    note = first("Note") or first("Pub Note") or first("Full Title")
    iiif_service = (
        f"https://www.davidrumsey.com/luna/servlet/iiif/{luna_id}"
    )

    return {
        "title": first("Short Title", result.get("displayName", "")),
        "date": first("Date", first("Pub Date")),
        "creator": "; ".join(authors),
        "subject": "; ".join(subjects or geographic),
        "summary": note,
        "sourceUrl": (
            "https://www.davidrumsey.com/luna/servlet/detail/" + luna_id
        ),
        "imageUrl": iiif_service + "/full/!1400,1400/0/default.jpg",
        "catalogId": first("List No"),
        "fullMetadata": fields,
    }


def main():
    metadata = {
        entry_id: fetch_record(record_suffix)
        for entry_id, record_suffix in RECORDS.items()
    }
    OUTPUT.write_text(
        "// Generated from the official David Rumsey LUNA catalog API.\n"
        + "window.STAIRWELL_MAP_METADATA = "
        + json.dumps(metadata, ensure_ascii=False, separators=(",", ":"))
        + ";\n"
    )
    print(f"Wrote official metadata for {len(metadata)} Stairwell Maps")


if __name__ == "__main__":
    main()
