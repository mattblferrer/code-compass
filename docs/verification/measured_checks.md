# Measured checks (R-08, R-18, R-21, R-23, R-24)

This page records the checks that need a measurement, a device, or testers rather than unit tests. Parts marked **Done** were run on 2026-11-11; parts marked **To do** need the author, testers, a browser, or a phone, and have a script and sheet below.

| Requirement | Status | Result |
| --- | --- | --- |
| R-21 load time | **Done** | Pass: dashboard in 0.13 s or less over 10 runs with 500 attempts (limit 2 s) |
| R-24 offline | **Done** (automated), **to do** (network off) | Pass with outside connections blocked; the demo run with Wi-Fi off is still to do |
| R-23 browsers and phone | **Done** (Chrome desktop, 375 px), **to do** (Firefox, phone) | Chrome passes at desktop width and at 375 px after two layout fixes |
| R-08 logging time | **To do** | Needs at least 3 first-time users |
| R-18 weakest patterns | **To do** | Needs 3 to 5 testers |

## R-21: load time with 500 attempts (Done)

- **Machine:** the target laptop (AMD Ryzen AI 9 HX 370, 32 GB RAM, RTX 4070 Laptop GPU), Windows 11, Python 3.14.7, Flask 3.1.3.
- **Data:** a new database with the full catalog and reserve (13,467 problems) and 500 attempts: 5 a day for 100 days ending on the test date, due reviews first as siblings, then new problems. It is built by `scripts/r21_load_time.py`, so the check can be rerun.
- **Server timing:** the script serves the app on 127.0.0.1 and times 10 full requests to the dashboard, which computes the scores, due reviews, and recommendations.

  | Run | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
  | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
  | Seconds | 0.131 | 0.125 | 0.108 | 0.111 | 0.112 | 0.111 | 0.098 | 0.130 | 0.118 | 0.116 |

  Median 0.114 s, slowest 0.131 s. App start, including loading the catalog and reserve into the new database: 0.24 s.
- **Browser timing:** in Chrome, the same database's dashboard loaded 10 times in a page frame, including the stylesheet, scripts, and layout: median 0.268 s, slowest 0.303 s. The first visit of the day took 0.84 s, because it chooses and saves the review siblings.
- **Result:** pass. Every run is under 2 seconds.

To rerun: `.venv\Scripts\python scripts\r21_load_time.py` (add `--keep copy.sqlite` to keep the database for a browser check).

## R-24: offline use

**Done (automated).** `tests/test_offline.py` blocks every connection to anything but this machine, as with the network off, and runs the reference flow: logging an attempt, the dashboard with a due review served as a sibling, logging the sibling to complete the review, recommendations and "not now", and every other page (history, pattern, problem, interviews, settings, sync, profile, import, custom problem, the .ics and CSV exports). Nothing tries to reach the network, and every page works. A second test confirms that a lookup and a sync, the only features that contact other sites, show "Could not reach ..." offline and leave the app working.

**Done (browser).** In Chrome, every request made while opening the dashboard, log, history, pattern, profile, and settings pages went to 127.0.0.1. The only other requests came from a browser extension, not the app. The code review (`docs/verification/code_review.md`) found no CDN or other outside links in the pages.

**To do: network off.**

1. Start the demo: `set CODECOMPASS_DEMO=1`, then `flask --app codecompass run`.
2. Turn off Wi-Fi and unplug any cable.
3. In the browser, run the reference flow: open the dashboard, log the first recommended problem, open its review sibling from a due review, log it, press "not now" on another recommendation, and open a pattern page and the history.
4. Record below whether each step worked. Opening a problem's link on its site is expected to fail.

| Step | Worked? | Notes |
| --- | --- | --- |
| Dashboard | | |
| Log a recommended problem | | |
| Log a review sibling | | |
| Not now | | |
| Pattern page and history | | |

## R-23: browsers and phone width

**Done: Chrome desktop and 375 px.** In Chrome (Windows 11), the dashboard, log, history, pattern, interviews, sync, profile, settings, import, and custom-problem pages were each loaded in a 375 by 812 px frame and checked for content wider than the screen. Two problems were found and fixed:

- The history page scrolled sideways: a hidden "Edit" column label escaped the table's scroll box. The table box now contains it.
- The header took three rows on a phone, with the light and dark button on its own row. The button now sits beside the name.

After the fixes no page scrolls sideways at 375 px. Wide tables (history, contest history) scroll inside their own box, so every column can still be reached.

**To do: Firefox and a phone.** Firefox is not installed on the laptop.

1. Firefox: install it, open the app, and run the main flows: log an attempt, read the dashboard, and open a recommendation.
2. Phone on the same Wi-Fi: start the app with `flask --app codecompass run --host 0.0.0.0`, allow it through the Windows firewall for private networks only, find the laptop's address with `ipconfig`, and open `http://<that address>:5000` on the phone. Run the same flows. Afterwards, start the app normally again, since `--host 0.0.0.0` lets other devices on the network reach it.

| Browser or device | Log | Dashboard | Recommendations | Content cut off? |
| --- | --- | --- | --- | --- |
| Chrome, desktop | yes | yes | yes | no |
| Chrome, 375 px frame | yes | yes | yes | no |
| Firefox, desktop | | | | |
| Phone over Wi-Fi (model, browser) | | | | |

## R-08: logging time (To do)

**Goal:** the median time to log 5 attempts is 30 seconds or less across at least 3 first-time users.

**Setup:** a fresh demo database (`set CODECOMPASS_DEMO=1`, `flask --app codecompass demo`), Chrome, and a stopwatch. Each tester has not used CodeCompass before. Explain only that the app records practice problems; do not show the log form first.

**Cards** (one at a time, in this order; each says what happened, as a tester would remember it):

1. Two Sum: solved alone, about 10 minutes.
2. Valid Parentheses: needed a hint from a friend.
3. Codeforces problem 1520A: solved alone.
4. Climbing Stairs: read the solution.
5. Merge Intervals: did not solve it; wrote a note "sorting by start".

**Timing:** start when the tester is on the dashboard and has read the card; stop when the "Attempt saved" message appears. Note any error message or hesitation.

| Tester | Card 1 | Card 2 | Card 3 | Card 4 | Card 5 | Median | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | | | | | | | |
| 2 | | | | | | | |
| 3 | | | | | | | |

**Result:** the median of all 15 times or more; pass if 30 seconds or less.

## R-18: weakest patterns and next problem (To do)

**Goal:** at least 80% of task attempts are correct across 3 to 5 testers, each within 2 minutes.

**Setup:** a fresh demo database, opened on the dashboard. The demo history is the same relative to any date, so the answers below hold on any day (checked for the build date, 3 days later, and 10 days later).

**Task script** (read aloud, then start the timer): "This is someone's practice record. Using this page, tell me the two patterns they are weakest at, and the one problem they should do next." Stop the timer when the tester gives all three answers, or at 2 minutes.

**Answers:**

- Weakest patterns: Backtracking and Brute Force and Greedy (both score 37; the next lowest is 53).
- Next problem: Binary Search Tree Iterator, the first problem under "Practice next".

| Tester | Weakest 1 correct? | Weakest 2 correct? | Next problem correct? | Time | Notes |
| --- | --- | --- | --- | --- | --- |
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

**Result:** count each tester's task as correct only if all three answers are right within 2 minutes; pass if at least 80% are correct.
