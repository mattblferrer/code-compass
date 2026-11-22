"""Check the curated pattern guides (R-59) for links that have stopped working.

Run it by hand, now and then, after building data/resources.csv from docs/resources.md:

    .venv\\Scripts\\python scripts\\check_resource_links.py [--delay 1.0]

This is the one place outside the app that requests the guides. The app never fetches
them (R-03, R-59), never imports this script, and no test calls it. Each distinct address
is requested once, a second apart by default, with a plain client name and no sign-in.
Some sites refuse automated requests (Codeforces and LeetCode answer 403); those are listed
separately, to be opened by hand.
"""
import argparse
import csv
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

RESOURCES = Path(__file__).resolve().parent.parent / "codecompass" / "data" / "resources.csv"
USER_AGENT = "CodeCompass link check"
REFUSED = {401, 403, 429}


def status(url, timeout):
    """The final HTTP status for `url` after redirects, or the error's text."""
    for method in ("HEAD", "GET"):  # Some sites refuse HEAD, so a failed HEAD is tried again as GET.
        request = urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.status
        except urllib.error.HTTPError as error:
            if method == "GET" or error.code not in (405, 403, 404):
                return error.code
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            if method == "GET":
                return str(getattr(error, "reason", error))
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
    parser.add_argument("--timeout", type=float, default=15.0, help="seconds to wait for each site")
    args = parser.parse_args()

    with open(RESOURCES, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    by_link = {}
    for row in rows:
        by_link.setdefault(row["link"], []).append(row["pattern"])

    broken, refused = [], []
    for number, (link, patterns) in enumerate(by_link.items(), start=1):
        if number > 1:
            time.sleep(args.delay)
        result = status(link, args.timeout)
        if result in REFUSED:
            refused.append((link, result, patterns))
        elif not (isinstance(result, int) and result < 400):
            broken.append((link, result, patterns))
        print(f"[{number}/{len(by_link)}] {result} {link}", flush=True)

    print(f"\nChecked {len(by_link)} links from {len(rows)} guides.")
    for title, found in (("Broken", broken), ("Refused automated checks; open these by hand", refused)):
        if found:
            print(f"\n{title}:")
            for link, result, patterns in found:
                print(f"  {result} {link}  ({'; '.join(sorted(set(patterns)))})")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
