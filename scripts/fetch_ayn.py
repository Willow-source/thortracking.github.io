#!/usr/bin/env python3
"""
fetch_ayn.py
Fetches AYN's shipment dashboard and writes parsed data to data/official.json

AYN dashboard URL: https://ayntec.com/pages/shipment-dashboard
If AYN changes their page layout, update the SELECTORS section below.
"""

import json
import sys
import re
from datetime import datetime, timezone
from pathlib import Path
import requests
from bs4 import BeautifulSoup

DASHBOARD_URL = "https://ayntec.com/pages/shipment-dashboard"
OUTPUT_PATH = Path(__file__).parent.parent / "data" / "official.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; AYNThorTracker/1.0; "
        "+https://github.com/Tartarsause117/thor-tracker)"
    )
}

# Known AYN Thor variants to look for on the page
KNOWN_VARIANTS = [
    "White Max",
    "Black Pro",
    "White Pro",
    "Black Standard",
]


def fetch_page(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


def parse_dashboard(html: str) -> list[dict]:
    """
    Parse AYN's shipment dashboard HTML.
    AYN's page structure may change — update selectors here if it breaks.
    """
    soup = BeautifulSoup(html, "lxml")
    results = []

    # ── Strategy 1: look for table rows ──
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
            if len(cells) >= 2:
                name_cell = cells[0]
                range_cell = cells[1] if len(cells) > 1 else ""
                for variant in KNOWN_VARIANTS:
                    if variant.lower() in name_cell.lower():
                        results.append({
                            "name": variant,
                            "range": range_cell,
                        })

    if results:
        return results

    # ── Strategy 2: look for any text block containing variant names + order numbers ──
    text = soup.get_text(separator="\n")
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    for i, line in enumerate(lines):
        for variant in KNOWN_VARIANTS:
            if variant.lower() in line.lower():
                # Grab surrounding lines for order number context
                context = " ".join(lines[max(0, i-1):i+3])
                # Look for patterns like "10000-10500", "#10450", or just "10450"
                nums = re.findall(r"#?(\d{4,6})(?:\s*[-–]\s*#?(\d{4,6}))?", context)
                if nums:
                    first = nums[0]
                    order_range = f"{first[0]}–{first[1]}" if first[1] else first[0]
                else:
                    order_range = "See dashboard"
                results.append({
                    "name": variant,
                    "range": order_range,
                })
                break

    return results


def load_existing() -> dict:
    if OUTPUT_PATH.exists():
        with open(OUTPUT_PATH) as f:
            return json.load(f)
    return {"fetched_at": None, "source": DASHBOARD_URL, "variants": []}


def main():
    print(f"Fetching: {DASHBOARD_URL}")
    try:
        html = fetch_page(DASHBOARD_URL)
    except Exception as e:
        print(f"ERROR: Could not fetch AYN dashboard: {e}", file=sys.stderr)
        # Don't overwrite existing data if fetch fails
        sys.exit(0)

    variants = parse_dashboard(html)
    print(f"Parsed {len(variants)} variant entries")
    for v in variants:
        print(f"  {v['name']}: {v['range']}")

    existing = load_existing()

    # Merge — keep any variants we found, fall back to existing for ones we didn't
    existing_map = {v["name"]: v for v in existing.get("variants", [])}
    for v in variants:
        existing_map[v["name"]] = v

    output = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": DASHBOARD_URL,
        "variants": list(existing_map.values()),
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

