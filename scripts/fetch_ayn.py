#!/usr/bin/env python3
"""
fetch_ayn.py
Fetches AYN's shipment dashboard and writes the latest data to data/official.json

Page format:
  Date headings like: 2026/3/19
  Entries like:       AYN Thor Rainbow Max: 1571xx--1612xx
                      AYN Thor White Max: 1571xx--1578xx

We grab the LATEST entry for each variant (last one on the page wins).
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

DASHBOARD_URL = "https://www.ayntec.com/pages/shipment-dashboard"
OUTPUT_PATH = Path(__file__).parent.parent / "data" / "official.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; AYNThorTracker/1.0; "
        "+https://github.com/willow-source/thortracking.github.io)"
    )
}

# Map AYN page text → our display names (emoji included)
VARIANT_MAP = {
    "white max":        "Thor ⚪ Max",
    "white pro":        "Thor ⚪ Pro",
    "rainbow max":      "Thor 🌈 Max",
    "rainbow pro":      "Thor 🌈 Pro",
    "clear purple max": "Thor 🟣 Max",
    "clear purple pro": "Thor 🟣 Pro",
    "black max":        "Thor ⚫ Max",
    "black pro":        "Thor ⚫ Pro",
    "black lite":       "Thor ⚫ Lite",
    "black base":       "Thor ⚫ Base",
}

# Regex to match a shipping entry line
# e.g. "AYN Thor Black Max: 1506xx--1537xx"
# e.g. "AYN Thor White Pro: 1376xx--1465xx"
ENTRY_RE = re.compile(
    r"AYN\s+Thor\s+(.+?):\s*([\d]+xx)\s*[-–—]+\s*([\d]+xx)",
    re.IGNORECASE
)

# Regex for date headings like 2026/3/19 or 2026/3/3
DATE_RE = re.compile(r"^\d{4}/\d{1,2}/\d{1,2}$")


def fetch_page(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


def parse_dashboard(html: str) -> dict:
    """
    Returns a dict of display_name -> {range, batch_date}
    The last occurrence of each variant on the page wins (newest batch).
    """
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(separator="\n")
    lines = [l.strip() for l in text.splitlines()]

    results = {}       # display_name -> entry dict
    current_date = None

    for line in lines:
        # Track current date heading
        if DATE_RE.match(line):
            current_date = line
            continue

        m = ENTRY_RE.search(line)
        if not m:
            continue

        raw_variant = m.group(1).strip().lower()
        range_from  = m.group(2)
        range_to    = m.group(3)
        order_range = f"{range_from} – {range_to}"

        # Match to our known variants
        display_name = None
        for key, name in VARIANT_MAP.items():
            if key in raw_variant:
                display_name = name
                break

        if not display_name:
            # Unknown variant — store it as-is with title case
            display_name = "Thor " + m.group(1).strip().title()

        results[display_name] = {
            "name":       display_name,
            "range":      order_range,
            "batch_date": current_date or "Unknown",
        }

    return results


def main():
    print(f"Fetching: {DASHBOARD_URL}")
    try:
        html = fetch_page(DASHBOARD_URL)
    except Exception as e:
        print(f"ERROR: Could not fetch AYN dashboard: {e}", file=sys.stderr)
        sys.exit(0)

    results = parse_dashboard(html)
    print(f"Parsed {len(results)} variant entries:")
    for name, entry in results.items():
        print(f"  {name}: {entry['range']} (batch {entry['batch_date']})")

    # Output in the same order as the community section
    canonical_order = [
        "Thor ⚪ Pro", "Thor ⚪ Max",
        "Thor 🌈 Pro", "Thor 🌈 Max",
        "Thor 🟣 Pro", "Thor 🟣 Max",
        "Thor ⚫ Pro", "Thor ⚫ Max",
        "Thor ⚫ Lite", "Thor ⚫ Base",
    ]
    ordered = [results[n] for n in canonical_order if n in results]
    # Append any unrecognised variants at the end
    known = set(canonical_order)
    ordered += [v for n, v in results.items() if n not in known]

    output = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source":     DASHBOARD_URL,
        "variants":   ordered,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"Written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
