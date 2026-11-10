"""Download a small, varied set of Chronicling America pages for development.

Run from the project root with the venv active:

    python scripts/download_chronam.py --pages-per-title 2     # quick trial
    python scripts/download_chronam.py                         # ~21 pages

Page images go to scans/en_dev/ (git-ignored). A manifest CSV with title,
LCCN, date, page number, URL and download date goes to data/en_dev_sources.csv
(small, safe to commit), so every scan stays traceable.

Standard library only; no new dependencies.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

BASE = "https://www.loc.gov/collections/chronicling-america/"
USER_AGENT = "newspaper-ner-student-project/0.1 (dev data download)"

# Three titles that appear in the Library of Congress's own API examples:
# Evening Star (Washington), Laramie Republican (Wyoming),
# Ogden Standard-Examiner (Utah). Pass --lccn to use other titles.
DEFAULT_LCCNS = ["sn83045462", "sn92066979", "sn85058393"]


def get_json(url: str, retries: int = 4) -> dict:
    """GET a URL and parse JSON, backing off politely on rate limits."""
    for attempt in range(retries):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            retryable = error.code in (429, 500, 502, 503, 504)
            if retryable and attempt < retries - 1:
                wait = 10 * (attempt + 1)
                print(f"  server returned {error.code}; waiting {wait}s", flush=True)
                time.sleep(wait)
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt < retries - 1:
                time.sleep(5 * (attempt + 1))
                continue
            raise
    raise RuntimeError("unreachable")


def with_json(url: str) -> str:
    """Return the URL over https with fo=json set exactly once."""
    parts = urllib.parse.urlsplit(url)
    query = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query) if k != "fo"]
    query.append(("fo", "json"))
    return urllib.parse.urlunsplit(
        parts._replace(scheme="https", query=urllib.parse.urlencode(query))
    )


def search_pages(lccn: str, start: str, end: str, max_candidates: int, delay: float) -> list[str]:
    """Return page-record URLs for one newspaper title in a date range."""
    params = {
        "dl": "page",
        "fa": f"number_lccn:{lccn}",
        "start_date": start,
        "end_date": end,
        "c": 100,
        "at": "results,pagination",
        "fo": "json",
    }
    url: str | None = BASE + "?" + urllib.parse.urlencode(params, safe=":,")
    ids: list[str] = []
    while url and len(ids) < max_candidates:
        data = get_json(url)
        for result in data.get("results", []):
            record_id = result.get("id", "")
            if "/resource/" in record_id or "/item/" in record_id:
                ids.append(record_id)
        next_url = (data.get("pagination") or {}).get("next")
        url = with_json(next_url) if next_url else None
        if url:
            time.sleep(delay)
    return sorted(set(ids))


def pick_spread(items: list[str], n: int) -> list[str]:
    """Pick n items evenly spaced across the list, so dates and pages vary."""
    if n <= 0 or not items:
        return []
    if len(items) <= n:
        return items
    if n == 1:
        return [items[0]]
    step = (len(items) - 1) / (n - 1)
    return [items[round(i * step)] for i in range(n)]


def first(value) -> str:
    """LoC metadata fields are often single-item lists; return a plain string."""
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value) if value else ""


def page_info(record_id: str, extension: str) -> dict | None:
    """Look up a page record and find its file URL for the chosen format."""
    data = get_json(with_json(record_id))
    file_url = next(
        (
            p["url"]
            for p in data.get("page", [])
            if isinstance(p, dict) and p.get("url", "").lower().endswith("." + extension)
        ),
        None,
    )
    if not file_url:
        return None
    item = data.get("item", {})
    return {
        "title": first(item.get("newspaper_title")),
        "lccn": first(item.get("number_lccn")),
        "issue_date": first(item.get("date")),
        "page": first((data.get("pagination") or {}).get("current")),
        "file_url": file_url,
    }


def download(url: str, destination: Path) -> None:
    """Download to a .part file first so an interrupted run never leaves a bad file."""
    temp = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response, open(temp, "wb") as out:
        shutil.copyfileobj(response, out)
    temp.replace(destination)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--lccn", nargs="+", default=DEFAULT_LCCNS, help="newspaper title IDs")
    parser.add_argument("--start-date", default="1922-12-01")
    parser.add_argument("--end-date", default="1922-12-31")
    parser.add_argument("--pages-per-title", type=int, default=7)
    parser.add_argument("--format", choices=["jp2", "pdf"], default="jp2",
                        help="jp2 is an image Pillow can usually open; pdf needs conversion for OCR")
    parser.add_argument("--out", type=Path, default=Path("scans/en_dev"))
    parser.add_argument("--manifest", type=Path, default=Path("data/en_dev_sources.csv"))
    parser.add_argument("--max-candidates", type=int, default=300,
                        help="how many pages to consider per title before sampling")
    parser.add_argument("--delay", type=float, default=3.0, help="seconds between requests")
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    new_manifest = not args.manifest.exists()
    saved = 0

    with open(args.manifest, "a", newline="", encoding="utf-8") as manifest_file:
        writer = csv.writer(manifest_file)
        if new_manifest:
            writer.writerow(
                ["file", "title", "lccn", "issue_date", "page", "source_url", "downloaded_on"]
            )

        for lccn in args.lccn:
            print(f"Searching {lccn} ({args.start_date} to {args.end_date})...", flush=True)
            try:
                candidates = search_pages(
                    lccn, args.start_date, args.end_date, args.max_candidates, args.delay
                )
            except Exception as error:  # keep going with the other titles
                print(f"  search failed: {error}")
                continue
            chosen = pick_spread(candidates, args.pages_per_title)
            print(f"  {len(candidates)} pages found; downloading {len(chosen)}")

            for record_id in chosen:
                time.sleep(args.delay)
                try:
                    info = page_info(record_id, args.format)
                    if info is None:
                        print(f"  no .{args.format} file listed for {record_id}; skipped")
                        continue
                    name = re.sub(
                        r"[^\w.-]", "_",
                        f"{lccn}_{info['issue_date']}_p{info['page']}.{args.format}",
                    )
                    destination = args.out / name
                    if destination.exists():
                        print(f"  already have {name}")
                        continue
                    download(info["file_url"], destination)
                    writer.writerow([
                        str(destination), info["title"], info["lccn"], info["issue_date"],
                        info["page"], info["file_url"], date.today().isoformat(),
                    ])
                    manifest_file.flush()
                    saved += 1
                    print(f"  saved {name}", flush=True)
                except Exception as error:
                    print(f"  failed on {record_id}: {error}")

    print(f"Done. {saved} new file(s) in {args.out}; manifest at {args.manifest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
