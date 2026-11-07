"""Build the reference test data from the rules in docs/rules.md.

Run this after changing a rule, then check what changed in reference.json:

    python tests/data/generate_reference.py

This file is a separate calculation of the rules, so it must not import from
codecompass. The tests compare the app's results with the values it writes.
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).parent
TODAY = "2026-11-10"

LEVELS = ["easy", "medium", "hard", "very hard"]
OUTCOME_VALUE = {"alone": 1.0, "hints": 0.5, "solution": 0.2, "not": 0.0}
RATE_UP = {"narrow": 0.4, "normal": 0.3, "broad": 0.2}
FIRST_INTERVAL = {"alone": 14, "hints": 10, "solution": 7, "not": 7}


def d(text):
    return date.fromisoformat(text)


def days_before(n):
    return str(d(TODAY) - timedelta(days=n))


# --- Mastery (R-09, R-10) ---

def expected_level(score):
    if score < 40:
        return 0
    if score < 70:
        return 1
    if score < 90:
        return 2
    return 3


def mastery(attempts, tier, today=TODAY):
    score, previous = 0.0, None
    for day, difficulty, outcome in attempts:
        if previous is not None:
            score *= 0.5 ** ((d(day) - d(previous)).days / 60)
        stretch = max(0, LEVELS.index(difficulty) - expected_level(score))
        target = 100 * OUTCOME_VALUE[outcome]
        if target >= score:
            rate = min(RATE_UP[tier] + 0.1 * stretch, 0.5)
        else:
            rate = 0.1 if stretch else 0.2
        score += rate * (target - score)
        previous = day
    if previous is None:
        return 0.0
    return round(score * 0.5 ** ((d(today) - d(previous)).days / 60), 2)


def spaced(ages, difficulty, outcomes):
    return [[days_before(a), difficulty, o] for a, o in zip(ages, outcomes)]


WORKED = [
    ["2026-10-01", "easy", "alone"],
    ["2026-10-11", "easy", "not"],
    ["2026-10-21", "medium", "alone"],
    ["2026-10-31", "hard", "alone"],
]

MASTERY_CASES = [
    ("new_user", "normal", spaced([7, 4, 1], "easy", ["alone"] * 3)),
    ("many_hints", "normal", spaced([30, 26, 22, 18, 14, 10, 6, 2], "medium", ["hints"] * 8)),
    ("long_gap", "normal", spaced([118, 114, 110, 106, 102, 98, 94, 90], "medium", ["alone"] * 8)),
    ("mostly_alone", "normal", spaced([40, 36, 32, 28, 24, 20, 16, 12, 8, 2], "medium",
                                      ["not", "hints"] + ["alone"] * 8)),
    ("mixed", "normal", [
        [days_before(30), "easy", "alone"],
        [days_before(25), "medium", "not"],
        [days_before(20), "medium", "hints"],
        [days_before(15), "hard", "solution"],
        [days_before(10), "easy", "alone"],
        [days_before(5), "medium", "hints"],
    ]),
    ("improving", "normal", spaced([30, 25, 20, 15, 10, 5, 1], "easy",
                                   ["not", "not", "solution", "hints", "alone", "alone", "alone"])),
    ("declining", "normal", spaced([30, 25, 20, 15, 10, 5, 1], "easy",
                                   ["alone", "alone", "alone", "hints", "solution", "not", "not"])),
    ("gap_between_attempts", "normal", [
        [days_before(120), "medium", "alone"],
        [days_before(115), "medium", "alone"],
        [days_before(110), "medium", "alone"],
        [days_before(0), "medium", "alone"],
    ]),
    ("worked_example_normal", "normal", WORKED),
    ("worked_example_narrow", "narrow", WORKED),
    ("worked_example_broad", "broad", WORKED),
    ("rate_cap_narrow_very_hard", "narrow", spaced([3, 2, 1], "very hard", ["alone"] * 3)),
    ("softer_decline_very_hard_miss", "normal", spaced([3, 2, 1], "very hard", ["alone", "alone", "not"])),
    ("sparse_two_attempts", "normal", spaced([5, 1], "medium", ["alone"] * 2)),
    ("no_attempts", "normal", []),
]


def mastery_section():
    out = []
    for name, tier, attempts in MASTERY_CASES:
        enough = len(attempts) >= 3
        out.append({
            "name": name,
            "tier": tier,
            "today": TODAY,
            "attempts": [{"date": a, "difficulty": b, "outcome": c} for a, b, c in attempts],
            "expected_score": mastery(attempts, tier) if enough else None,
            "expected_display": "score" if enough else "not enough data",
        })
    return out


# --- Review intervals (R-12, R-28) ---

def schedule(attempts):
    rows, interval, due = [], None, None
    for att in attempts:
        day, outcome = att["date"], att["outcome"]
        if interval is None:
            kind, new = "first", FIRST_INTERVAL[outcome]
        elif d(day) < d(due):
            kind, new = "early", FIRST_INTERVAL[outcome]
        else:
            kind = "review"
            new = interval * 2 if outcome == "alone" else FIRST_INTERVAL[outcome]
        interval, due = new, str(d(day) + timedelta(days=new))
        rows.append({**att, "expected_kind": kind, "expected_interval": new, "expected_due": due})
    return rows


def att(day, outcome, sibling=False):
    row = {"date": day, "outcome": outcome}
    if sibling:
        row["sibling"] = True
    return row


INTERVAL_CASES = [
    ("worked_example", [att("2026-09-01", "alone"), att("2026-09-15", "alone"),
                        att("2026-10-13", "hints"), att("2026-10-18", "not"),
                        att("2026-10-25", "alone"), att("2026-11-08", "not"),
                        att("2026-11-20", "alone")]),
    ("repeated_doubling", [att("2026-01-01", "alone"), att("2026-01-15", "alone"),
                           att("2026-02-12", "alone"), att("2026-04-09", "alone")]),
    ("resets_by_outcome", [att("2026-03-01", "hints"), att("2026-03-11", "alone"),
                           att("2026-03-31", "solution"), att("2026-04-07", "not"),
                           att("2026-04-14", "hints")]),
    ("month_and_year_boundary", [att("2026-12-20", "alone"), att("2027-01-03", "hints"),
                                 att("2027-01-13", "not")]),
    ("sibling_sets_original", [att("2026-05-01", "alone"), att("2026-05-15", "alone", True),
                               att("2026-06-12", "hints", True)]),
    ("late_review_no_bonus", [att("2026-07-01", "alone"), att("2026-08-30", "alone")]),
    ("early_attempt_restarts", [att("2026-08-01", "alone"), att("2026-08-05", "alone"),
                                att("2026-08-19", "alone")]),
]


def interval_section():
    return [{"name": n, "attempts": schedule(a)} for n, a in INTERVAL_CASES]


# --- Review streak (R-30) ---

def streak(days, today):
    count = 0
    for row in sorted(days, key=lambda r: r["date"], reverse=True):
        if row["completed"]:
            count += 1
        elif row["due"] and row["date"] != today:
            break
    return count


def day(day_, due, completed):
    return {"date": day_, "due": due, "completed": completed}


STREAK_CASES = [
    ("three_days_ending_today", "2026-11-10",
     [day("2026-11-08", True, True), day("2026-11-09", True, True), day("2026-11-10", True, True)]),
    ("today_not_done_yet", "2026-11-10",
     [day("2026-11-08", True, True), day("2026-11-09", True, True), day("2026-11-10", True, False)]),
    ("missed_day_breaks", "2026-11-10",
     [day("2026-11-07", True, True), day("2026-11-08", True, False),
      day("2026-11-09", True, True), day("2026-11-10", True, True)]),
    ("yesterday_missed_today_not_done", "2026-11-10",
     [day("2026-11-08", True, True), day("2026-11-09", True, False), day("2026-11-10", True, False)]),
    ("new_problems_only_breaks", "2026-11-10",
     [day("2026-11-08", True, True), day("2026-11-09", True, False), day("2026-11-10", True, True)]),
    ("nothing_due_neither_adds_nor_breaks", "2026-11-10",
     [day("2026-11-07", True, True), day("2026-11-08", False, False),
      day("2026-11-09", False, False), day("2026-11-10", True, True)]),
    ("month_boundary", "2026-12-01",
     [day("2026-11-29", True, True), day("2026-11-30", True, True), day("2026-12-01", True, True)]),
    ("no_reviews_ever", "2026-11-10", []),
]


def streak_section():
    return [{"name": n, "today": t, "days": x, "expected_streak": streak(x, t)}
            for n, t, x in STREAK_CASES]


# --- Current difficulty level (R-13) ---

def current_level(attempts, starting, very_hard_on=False):
    if not attempts:
        return starting
    recent = [a["difficulty"] for a in attempts[-10:]]
    counts = {lv: recent.count(lv) for lv in LEVELS}
    top = max(counts.values())
    tied = [lv for lv in LEVELS if counts[lv] == top]
    level = tied[-1]  # a tie goes to the harder level
    at_level = [a["outcome"] for a in attempts if a["difficulty"] == level][-5:]
    index = LEVELS.index(level)
    if at_level.count("alone") >= 3:
        index = min(index + 1, 3)
    elif at_level.count("not") >= 3:
        index = max(index - 1, 0)
    if not very_hard_on:
        index = min(index, 2)
    return LEVELS[index]


def lv(difficulty, outcome):
    return {"difficulty": difficulty, "outcome": outcome}


LEVEL_CASES = [
    ("no_attempts_uses_starting", "medium", False, []),
    ("stays_at_level", "easy", False, [lv("medium", "hints")] * 5),
    ("moves_up", "easy", False, [lv("medium", "alone")] * 3 + [lv("medium", "hints")] * 2),
    ("moves_down", "easy", False, [lv("medium", "not")] * 3 + [lv("medium", "hints")] * 2),
    ("cannot_go_below_easy", "easy", False, [lv("easy", "not")] * 5),
    ("tie_uses_harder_level", "easy", False, [lv("easy", "hints")] * 5 + [lv("medium", "hints")] * 5),
    ("stops_at_hard_with_setting_off", "easy", False, [lv("hard", "alone")] * 5),
    ("reaches_very_hard_with_setting_on", "easy", True, [lv("hard", "alone")] * 5),
]


def level_section():
    return [{"name": n, "starting": s, "very_hard_on": v, "attempts": a,
             "expected_level": current_level(a, s, v)} for n, s, v, a in LEVEL_CASES]


# --- Sibling selection (R-28) ---

TT, DP, GR, FFT = "Tree Traversal", "1-D Dynamic Programming", "Greedy", "FFT and NTT"


def sibling(case):
    due = case["due"]
    due_pats = set(due["patterns"])
    due_index = LEVELS.index(due["difficulty"])
    inactive = set(case.get("inactive", []))
    candidates = []
    for p in case["candidates"]:
        pats = set(p["patterns"])
        gap = LEVELS.index(p["difficulty"]) - due_index
        if p.get("custom") or p.get("attempted") or p.get("reserved") or p.get("dismissed") or p.get("not_now"):
            continue
        if not pats & due_pats or (pats & inactive) - due_pats or gap not in (0, -1, 1):
            continue
        if p["difficulty"] == "very hard" and not (case.get("very_hard_on") or due["difficulty"] == "very hard"):
            continue
        rank = {0: 0, -1: 1, 1: 2}[gap]
        candidates.append((rank, -len(pats & due_pats), len(pats - due_pats), p["position"]))
    return min(candidates)[3] if candidates else "original"


def cand(position, difficulty, patterns, **flags):
    return {"position": position, "difficulty": difficulty, "patterns": patterns, **flags}


MEDIUM_DUE = {"difficulty": "medium", "patterns": [TT, DP]}
SIBLING_CASES = [
    {"name": "worked_example", "due": MEDIUM_DUE, "inactive": [FFT], "candidates": [
        cand(5, "easy", [TT, DP]), cand(6, "hard", [TT, DP]), cand(10, "medium", [TT, DP], attempted=True),
        cand(12, "medium", [TT, DP], reserved=True), cand(15, "medium", [TT, GR]),
        cand(20, "medium", [DP, FFT]), cand(25, "medium", [GR]), cand(40, "medium", [TT]),
        cand(80, "medium", [TT, DP, GR]), cand(120, "medium", [TT, DP])]},
    {"name": "dismissed_moves_to_next", "due": MEDIUM_DUE, "candidates": [
        cand(80, "medium", [TT, DP, GR]), cand(120, "medium", [TT, DP], dismissed=True)]},
    {"name": "easier_before_harder", "due": MEDIUM_DUE, "candidates": [
        cand(5, "easy", [TT]), cand(6, "hard", [TT, DP])]},
    {"name": "harder_when_no_easier", "due": MEDIUM_DUE, "candidates": [cand(6, "hard", [TT])]},
    {"name": "two_levels_away_falls_back", "due": MEDIUM_DUE, "candidates": [cand(6, "very hard", [TT])]},
    {"name": "custom_problem_never_sibling", "due": MEDIUM_DUE, "candidates": [
        cand(7, "medium", [TT], custom=True)]},
    {"name": "very_hard_blocked_with_setting_off", "due": {"difficulty": "hard", "patterns": [FFT]},
     "candidates": [cand(9, "very hard", [FFT])]},
    {"name": "very_hard_allowed_with_setting_on", "due": {"difficulty": "hard", "patterns": [FFT]},
     "very_hard_on": True, "candidates": [cand(9, "very hard", [FFT])]},
    {"name": "very_hard_allowed_for_very_hard_due", "due": {"difficulty": "very hard", "patterns": [FFT]},
     "candidates": [cand(9, "very hard", [FFT])]},
]


def sibling_section():
    return [{**c, "expected_sibling": sibling(c)} for c in SIBLING_CASES]


# --- Recommendations (R-13, R-14, R-15, R-29, R-32) ---

CORE = ["Arrays and Hashing", "Prefix Sums", "Stack", "Linked List", "Binary Search", "Sorting",
        "Intervals", "Heap", "Trie", "Greedy"]
ADVANCED = [FFT, "2-SAT"]
PATTERNS = CORE + ADVANCED


def base_catalog():
    catalog, position = [], 0
    for name in CORE:
        for difficulty in ("easy", "medium", "hard"):
            position += 1
            catalog.append({"id": f"{name}/{difficulty}", "position": position,
                            "difficulty": difficulty, "patterns": [name]})
    position += 1
    catalog.append({"id": f"{FFT}/very hard", "position": position, "difficulty": "very hard", "patterns": [FFT]})
    position += 1
    catalog.append({"id": "Greedy+2-SAT/hard", "position": 0, "difficulty": "hard", "patterns": ["Greedy", "2-SAT"]})
    return catalog


def recommend(s):
    catalog = base_catalog()
    targets = set(s.get("targets", []))
    mastered = set(s.get("mastered", []))
    scores = s.get("scores", {})
    attempts = s.get("unscored_attempts", {})
    advanced_on = s.get("advanced_on", False)
    very_hard_on = s.get("very_hard_on", False)
    level = LEVELS.index(s["level"])

    def active(p):
        return p in CORE or advanced_on or p in targets

    def order(p):
        return PATTERNS.index(p)

    def scored_key(p):
        return (p in mastered, scores[p]["score"], scores[p]["last"], order(p))

    def unscored_key(p):
        return (p in mastered, -attempts.get(p, 0), order(p))

    scored = sorted((p for p in scores if active(p)), key=scored_key)
    unscored = sorted((p for p in PATTERNS if active(p) and p not in scores), key=unscored_key)
    target_list = [p for p in unscored if p in targets] + [p for p in scored if p in targets]

    reviews = list(s.get("due", []))
    focus = s.get("interview_within_14_days", False) and bool(scored)

    def weakness(r):
        return scores.get(r["pattern"], {"score": -1})["score"]

    if focus:
        reviews.sort(key=lambda r: (weakness(r), r["due"], r["position"]))
    else:
        reviews.sort(key=lambda r: (r["due"], weakness(r), r["position"]))

    chosen = [f"review:{r['problem']}" for r in reviews[:3]]
    picked_ids = set()
    excluded = set(s.get("attempted", [])) | set(s.get("not_now", [])) | set(s.get("reserved", []))

    def pick(pattern, is_target):
        def distance_rank(problem):
            gap = LEVELS.index(problem["difficulty"]) - level
            return (abs(gap), gap > 0)

        options = []
        for problem in catalog:
            if pattern not in problem["patterns"] or problem["id"] in excluded or problem["id"] in picked_ids:
                continue
            if any(not active(p) for p in problem["patterns"]):
                continue
            gap = LEVELS.index(problem["difficulty"]) - level
            if not is_target and abs(gap) > 1:
                continue
            options.append(problem)
        allowed = [p for p in options if very_hard_on or p["difficulty"] != "very hard"]
        if is_target and not allowed:
            allowed = options
        if not allowed:
            return None
        return min(allowed, key=lambda p: (distance_rank(p), len(p["patterns"]) - 1, p["position"]))

    supplied = set()

    def fill(group, count, is_target=False):
        added = 0
        reset_done = False
        while added < count:
            progress = False
            for pattern in group:
                if added == count:
                    break
                if pattern in supplied:
                    continue
                problem = pick(pattern, is_target)
                if problem:
                    picked_ids.add(problem["id"])
                    chosen.append(f"new:{problem['id']}")
                    supplied.add(pattern)
                    added += 1
                    progress = True
            if added == count:
                break
            if not progress:
                if reset_done:
                    break
                supplied.difference_update(group)
                reset_done = True
            else:
                reset_done = False
        return added

    fill(target_list, min(2, 5 - len(chosen)), is_target=True)
    if not scored:
        fill(unscored, 5 - len(chosen))
    else:
        if not focus:
            fill(unscored, min(1, 5 - len(chosen)))
        new_group = scored[:2] if focus else scored
        fill(new_group, 5 - len(chosen))
    for r in reviews[3:]:
        if len(chosen) < 5:
            chosen.append(f"review:{r['problem']}")
    return chosen


def due(problem, pattern, due_date, position):
    return {"problem": problem, "pattern": pattern, "due": due_date, "position": position}


def score(value, last):
    return {"score": value, "last": last}


WORKED_SCORES = {
    "Intervals": score(30.0, "2026-11-03"),
    "Greedy": score(40.0, "2026-10-20"),
    "Stack": score(40.0, "2026-11-05"),
    "Heap": score(55.0, "2026-11-01"),
    "Sorting": score(70.0, "2026-11-02"),
}

RECOMMENDATION_CASES = [
    {"name": "new_user", "level": "easy"},
    {"name": "worked_example", "level": "medium", "scores": WORKED_SCORES, "mastered": ["Intervals"],
     "unscored_attempts": {"Linked List": 2, "Prefix Sums": 1},
     "due": [due("Heap/old", "Heap", "2026-11-01", 300), due("Stack/old", "Stack", "2026-11-01", 410)]},
    {"name": "review_backlog_with_targets", "level": "medium",
     "scores": {**WORKED_SCORES, "Binary Search": score(45.0, "2026-11-04")},
     "targets": ["Binary Search", "Trie"], "unscored_attempts": {"Trie": 1},
     "due": [due("Sorting/old", "Sorting", "2026-10-30", 100), due("Heap/old", "Heap", "2026-11-01", 300),
             due("Stack/old", "Stack", "2026-11-01", 410), due("Greedy/old", "Greedy", "2026-11-05", 500)]},
    {"name": "interview_within_14_days", "level": "medium", "scores": WORKED_SCORES,
     "mastered": ["Intervals"], "interview_within_14_days": True,
     "unscored_attempts": {"Linked List": 2},
     "due": [due("Heap/old", "Heap", "2026-11-01", 300), due("Stack/old", "Stack", "2026-11-03", 410)]},
    {"name": "exclusions", "level": "hard", "scores": WORKED_SCORES, "mastered": ["Intervals"],
     "attempted": ["Heap/hard"], "not_now": ["Greedy/hard"], "reserved": ["Stack/hard"],
     "unscored_attempts": {"Linked List": 2}},
    {"name": "advanced_target_with_settings_off", "level": "easy", "scores": WORKED_SCORES,
     "targets": [FFT], "unscored_attempts": {"Linked List": 2}},
    {"name": "single_target_fills_both_slots", "level": "medium", "scores": WORKED_SCORES,
     "targets": ["Trie"], "unscored_attempts": {"Linked List": 2}},
    {"name": "advanced_and_very_hard_on", "level": "hard", "scores": WORKED_SCORES,
     "advanced_on": True, "very_hard_on": True, "unscored_attempts": {"Linked List": 2}},
]


def recommendation_section():
    return [{**c, "patterns": PATTERNS, "advanced": ADVANCED, "catalog": base_catalog(),
             "expected_list": recommend(c)} for c in RECOMMENDATION_CASES]


# --- Build ---

def check(condition, message):
    if not condition:
        sys.exit("Does not match docs/rules.md: " + message)


def main():
    data = {
        "note": "Generated by generate_reference.py. Times and today are fixed.",
        "mastery": mastery_section(),
        "intervals": interval_section(),
        "streak": streak_section(),
        "difficulty_level": level_section(),
        "sibling": sibling_section(),
        "recommendations": recommendation_section(),
    }

    # The worked examples must agree with docs/rules.md.
    by_name = {c["name"]: c for c in data["mastery"]}
    check(by_name["worked_example_normal"]["expected_score"] == 60.13, "mastery normal")
    check(by_name["worked_example_narrow"]["expected_score"] == 69.43, "mastery narrow")
    check(by_name["worked_example_broad"]["expected_score"] == 54.16, "mastery broad")
    worked_interval = data["intervals"][0]["attempts"]
    check([a["expected_due"] for a in worked_interval] == [
        "2026-09-15", "2026-10-13", "2026-10-23", "2026-10-25", "2026-11-08", "2026-11-15", "2026-12-04",
    ], "review interval example")
    check(data["sibling"][0]["expected_sibling"] == 120, "sibling example")
    worked_list = [c for c in data["recommendations"] if c["name"] == "worked_example"][0]["expected_list"]
    check(worked_list == ["review:Stack/old", "review:Heap/old", "new:Linked List/medium",
                          "new:Greedy/medium", "new:Stack/medium"], "recommendation example")

    path = HERE / "reference.json"
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {path.name}")
    for section in ("mastery", "streak", "difficulty_level", "sibling"):
        print(f"\n{section}:")
        for c in data[section]:
            value = c.get("expected_score", c.get("expected_streak", c.get("expected_level", c.get("expected_sibling"))))
            print(f"  {c['name']}: {value}")
    print("\nintervals:")
    for c in data["intervals"]:
        print(f"  {c['name']}: " + ", ".join(
            f"{a['expected_kind']}->{a['expected_interval']}d" for a in c["attempts"]))
    print("\nrecommendations:")
    for c in data["recommendations"]:
        print(f"  {c['name']}:")
        for item in c["expected_list"]:
            print(f"    {item}")


if __name__ == "__main__":
    main()
