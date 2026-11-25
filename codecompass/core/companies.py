"""Company pattern presets (R-60): the share rule, LeetCode's topics, and finding a preset.

`company_shares` works out one company's pattern shares from its all-time list in the
snapshot, by the rule in docs/rules.md, and `build_rows` turns every company into the rows
of data/companies.csv (the build-companies command); a company with too short a list is
written with no shares. `parse_companies` checks that file when the app starts, `general`
averages the shares into the most common patterns, which a company with no shares of its own
fills in, and `preset` and `find` pick a company's patterns and look it up by name.
"""
from datetime import date
from fractions import Fraction
import math

from . import constants as c
from .catalog_rows import DataFileError

HEADER = ["company", "problems", "counted", "catalog_share", "snapshot", "pattern", "share"]

# LeetCode topics that mean one pattern. A problem with any of these counts only by them.
SPECIFIC = {
    "Two Pointers": "Two Pointers",
    "Sliding Window": "Sliding Window",
    "Prefix Sum": "Prefix Sums",
    "Stack": "Stack",
    "Monotonic Stack": "Monotonic Stack and Queue",
    "Monotonic Queue": "Monotonic Stack and Queue",
    "Linked List": "Linked List",
    "Doubly-Linked List": "Linked List",
    "Binary Search": "Binary Search",
    "Sweep Line": "Intervals",
    "Heap (Priority Queue)": "Heap",
    "Heap": "Heap",
    "Tree": "Tree Traversal",
    "Binary Tree": "Tree Traversal",
    "Binary Search Tree": "Binary Search Trees",
    "Trie": "Trie",
    "Backtracking": "Backtracking and Brute Force",
    "Brute-Force Search": "Backtracking and Brute Force",
    "Algorithm X": "Backtracking and Brute Force",
    "Dancing Links": "Backtracking and Brute Force",
    "Bidirectional Search": "Graph Traversal",
    "Topological Sort": "Topological Sort",
    "Union-Find": "Union-Find",
    "Shortest Path": "Shortest Paths",
    "Dijkstra's Algorithm": "Shortest Paths",
    "Bellman–Ford Algorithm": "Shortest Paths",
    "Floyd–Warshall Algorithm": "Shortest Paths",
    "0-1 BFS": "Shortest Paths",
    "A* Search": "Shortest Paths",
    "K Shortest Path": "Shortest Paths",
    "Minimum Spanning Tree": "Minimum Spanning Tree",
    "Prim's Algorithm": "Minimum Spanning Tree",
    "Kruskal's Algorithm": "Minimum Spanning Tree",
    "Borůvka's Algorithm": "Minimum Spanning Tree",
    "Longest Increasing Subsequence": "1-D Dynamic Programming",
    "Longest Common Subsequence": "2-D Dynamic Programming",
    "Greedy": "Greedy",
    "Bit Manipulation": "Bit Manipulation",
    "Simulation": "Simulation and Implementation",
    "Design": "Data Structure Design",
    # Advanced patterns: counted in the shares, but never filled in by a preset.
    "Number Theory": "Number Theory",
    "Greatest Common Divisor": "Number Theory",
    "Euclidean Algorithm": "Number Theory",
    "Extended Euclidean Algorithm": "Number Theory",
    "Least Common Multiple": "Number Theory",
    "Bézout's Lemma": "Number Theory",
    "Sieve Theory": "Number Theory",
    "Prime Number Sieve": "Number Theory",
    "Primality Test": "Number Theory",
    "Prime Factorization": "Number Theory",
    "Fermat's Little Theorem": "Number Theory",
    "Euler's Totient Function": "Number Theory",
    "Euler's Theorem": "Number Theory",
    "Combinatorics": "Combinatorics",
    "Inclusion-Exclusion Principle": "Combinatorics",
    "Probability and Statistics": "Probability and Expected Value",
    "Reservoir Sampling": "Probability and Expected Value",
    "Rejection Sampling": "Probability and Expected Value",
    "Game Theory": "Game Theory",
    "Minimax": "Game Theory",
    "Zero-Sum Game": "Game Theory",
    "Impartial Game": "Game Theory",
    "Nim Game": "Game Theory",
    "Sprague–Grundy Theorem": "Game Theory",
    "Geometry": "Geometry",
    "Polygons": "Geometry",
    "Convex Hull": "Geometry",
    "Triangulation": "Geometry",
    "Minimum Enclosing Circle": "Geometry",
    "Nearest Pair of Points": "Geometry",
    "Divide and Conquer": "Divide and Conquer",
    "Meet in the Middle": "Meet in the Middle",
    "Ternary Search": "Ternary Search",
    "Segment Tree": "Segment Tree and Fenwick Tree",
    "Binary Indexed Tree": "Segment Tree and Fenwick Tree",
    "DP on Trees": "Tree DP",
    "Binary Lifting": "Lowest Common Ancestor and Tree Queries",
    "Rolling Hash": "String Hashing",
    "String Matching": "String Matching",
    "Knuth–Morris–Pratt Algorithm": "String Matching",
    "Z Algorithm": "String Matching",
    "Boyer–Moore String-Search Algorithm": "String Matching",
    "Aho–Corasick Algorithm": "String Matching",
    "Manacher": "String Matching",
    "Suffix Array": "Suffix Structures",
    "Suffix Tree": "Suffix Structures",
    "Suffix Automaton": "Suffix Structures",
    "Strongly Connected Component": "Strongly Connected Components and Bridges",
    "Kosaraju's Algorithm": "Strongly Connected Components and Bridges",
    "Tarjan's SCC Algorithm": "Strongly Connected Components and Bridges",
    "Biconnected Component": "Strongly Connected Components and Bridges",
    "Bridge (Graph)": "Strongly Connected Components and Bridges",
    "Articulation Point": "Strongly Connected Components and Bridges",
    "Flow Network": "Max Flow and Min Cut",
    "Maximum Flow": "Max Flow and Min Cut",
    "Minimum Cut": "Max Flow and Min Cut",
    "Minimum-Cost Flow": "Max Flow and Min Cut",
    "Successive Shortest Path Algorithm": "Max Flow and Min Cut",
    "Edmonds–Karp Algorithm": "Max Flow and Min Cut",
    "Dinic's Algorithm": "Max Flow and Min Cut",
    "MPM Algorithm": "Max Flow and Min Cut",
    "Push-Relabel Algorithm": "Max Flow and Min Cut",
    "Matching (Graph)": "Bipartite Matching",
    "Maximum Matching": "Bipartite Matching",
    "Perfect Matching": "Bipartite Matching",
    "Hungarian Algorithm": "Bipartite Matching",
    "Interactive": "Interactive Problems",
}

# Topics that count only when a problem has no specific topic: a sliding-window problem
# tagged Hash Table and String counts only as Sliding Window.
GENERIC = {
    "Hash Table": "Arrays and Hashing",
    "Counting": "Arrays and Hashing",
    "String": "Strings",
    "Math": "Math",
    "Sorting": "Sorting",
    "Sort": "Sorting",
    "Merge Sort": "Sorting",
    "Quicksort": "Sorting",
    "Bucket Sort": "Sorting",
    "Counting Sort": "Sorting",
    "Radix Sort": "Sorting",
    "Bubble Sort": "Sorting",
    "Tournament Sort": "Sorting",
    "Timsort": "Sorting",
}

# Graph Traversal, unless the problem is on a tree, where these mean Tree Traversal (which the
# tree topic gives). Otherwise they count as specific topics.
TRAVERSAL = {"Depth-First Search", "Breadth-First Search"}
TREE_TOPICS = {"Tree", "Binary Tree", "Binary Search Tree"}

# Other names people use, ignoring case, for a company as the snapshot spells it.
ALIASES = {
    "facebook": "Meta",
    "alphabet": "Google",
    "walmart": "Walmart Labs",
    "walmart global tech": "Walmart Labs",
    "twitter": "X",
    "tata consultancy services": "tcs",
    "d. e. shaw": "DE Shaw",
    "d.e. shaw": "DE Shaw",
}

# Names the snapshot writes differently from the company, by the name ignoring case, as they are shown.
DISPLAY = {
    "tcs": "TCS",
    "josh technology": "Josh Technology",
    "blinkit": "Blinkit",
    "carwale": "CarWale",
    "ciena": "Ciena",
    "cvent": "Cvent",
    "docusign": "DocuSign",
    "dp world": "DP World",
    "fourkites": "FourKites",
    "freshworks": "Freshworks",
    "geico": "GEICO",
    "hubspot": "HubSpot",
    "instabase": "Instabase",
    "jio": "Jio",
    "microstrategy": "MicroStrategy",
    "moengage": "MoEngage",
    "netsuite": "NetSuite",
    "opentext": "OpenText",
    "oyo": "OYO",
    "peak6": "PEAK6",
    "persistent systems": "Persistent Systems",
    "pwc": "PwC",
    "razorpay": "Razorpay",
    "redbus": "redBus",
    "smartnews": "SmartNews",
    "thoughtspot": "ThoughtSpot",
    "warnermedia": "WarnerMedia",
    "zeta suite": "Zeta Suite",
    "zscaler": "Zscaler",
}


def link_key(link):
    """A problem's link for matching: ignoring case, "www.", and a trailing slash."""
    return link.strip().lower().replace("://www.", "://").rstrip("/")


def topic_patterns(topics, order):
    """Pattern names for a problem's LeetCode topics, in pattern-list order (docs/rules.md)."""
    topics = {t.strip() for t in topics if t.strip()}
    found = {SPECIFIC[t] for t in topics if t in SPECIFIC}
    if topics & TRAVERSAL and not topics & TREE_TOPICS:
        found.add("Graph Traversal")
    if not found:
        found = {GENERIC[t] for t in topics if t in GENERIC}
    return [name for name in order if name in found]


def _percent(part, whole):
    """part / whole as a percentage, rounded half up to one decimal."""
    return math.floor(part * 1000 / whole + Fraction(1, 2)) / 10


def company_shares(rows, catalog, order):
    """One company's shares from its all-time list, or None if the list is too short.

    `rows` are the list's rows as dicts ("Link", "Topics", "Frequency"); `catalog` maps
    `link_key(link)` to a catalog problem's pattern names; `order` lists every pattern name
    in pattern-list order. Returns {"problems", "counted", "catalog_share", "shares"}, where
    shares is [(pattern, percent)] highest first, ties in pattern-list order. Raises
    ValueError naming any row whose frequency is not a number.
    """
    if len(rows) < c.COMPANY_MIN_PROBLEMS:
        return None
    totals, counted, total, from_catalog = {}, 0, Fraction(0), Fraction(0)
    for number, row in enumerate(rows, start=2):
        try:
            frequency = Fraction((row.get("Frequency") or "").strip())
        except (ValueError, ZeroDivisionError):
            raise ValueError(f"row {number}: frequency {row.get('Frequency')!r} is not a number") from None
        matched = catalog.get(link_key(row.get("Link") or ""))
        patterns = matched or topic_patterns((row.get("Topics") or "").split(","), order)
        if not patterns:
            continue
        counted += 1
        total += frequency
        if matched:
            from_catalog += frequency
        for name in patterns:
            totals[name] = totals.get(name, 0) + frequency / len(patterns)
    position = {name: i for i, name in enumerate(order)}
    shares = sorted(((name, _percent(part, total)) for name, part in totals.items()),
                    key=lambda item: (-item[1], position[item[0]]))
    return {
        "problems": len(rows),
        "counted": counted,
        "catalog_share": _percent(from_catalog, total) if total else 0.0,
        "shares": [(name, share) for name, share in shares if share > 0],
    }


def build_rows(companies, catalog, order, snapshot):
    """The companies.csv rows for {company name: its rows}, companies by name ignoring case.

    A company with too short a list, or with nothing counted, gets one row with only its name,
    problems, and snapshot, so it is listed with the most common patterns instead. A company
    with no problems is left out.
    """
    rows = []
    for name in sorted(companies, key=str.casefold):
        if not companies[name]:
            continue
        result = company_shares(companies[name], catalog, order)
        if not result or not result["shares"]:
            rows.append({"company": name, "problems": len(companies[name]), "counted": "", "catalog_share": "",
                         "snapshot": snapshot, "pattern": "", "share": ""})
            continue
        for pattern, share in result["shares"]:
            rows.append({"company": name, "problems": result["problems"], "counted": result["counted"],
                         "catalog_share": f"{result['catalog_share']:.1f}", "snapshot": snapshot,
                         "pattern": pattern, "share": f"{share:.1f}"})
    return rows


def _number(text, kind):
    try:
        value = kind(text)
    except ValueError:
        return None
    return value if math.isfinite(value) and value >= 0 else None


def parse_companies(rows, categories, filename="companies.csv"):
    """Return {key: company} for the rows of companies.csv, where key is the name as `find`
    looks it up. Each company is a dict with "company" (its name as shown), "problems",
    "counted", "catalog_share", "snapshot", and "shares", [(pattern, percent)] in file order.
    A company's one row with no pattern lists it with no shares, and counted and catalog_share
    None.

    `categories` maps each pattern name to "core" or "advanced". Raises DataFileError with
    every problem found.
    """
    companies, errors, last = {}, [], None
    for number, row in enumerate(rows, start=2):
        values = {key: (row.get(key) or "").strip() for key in HEADER}
        found = []
        name = values["company"]
        if not name:
            found.append("company is missing")
        problems = _number(values["problems"], int)
        listed_only = not values["pattern"]  # Too few problems for shares of its own.
        if listed_only:
            counted = catalog_share = share = None
            if problems is None:
                found.append("problems must be a whole number")
            if values["counted"] or values["catalog_share"] or values["share"]:
                found.append("a row with no pattern has no counted, catalog_share, or share")
        else:
            counted = _number(values["counted"], int)
            if problems is None or counted is None or counted > problems:
                found.append("problems and counted must be whole numbers, with counted no more than problems")
            catalog_share, share = _number(values["catalog_share"], float), _number(values["share"], float)
            if catalog_share is None or catalog_share > 100:
                found.append("catalog_share must be a percentage from 0 to 100")
            if share is None or not 0 < share <= 100:
                found.append("share must be a percentage above 0, up to 100")
        try:
            if date.fromisoformat(values["snapshot"]).isoformat() != values["snapshot"]:
                raise ValueError
        except ValueError:
            found.append("snapshot must be a date as YYYY-MM-DD")
        if not listed_only and values["pattern"] not in categories:
            found.append(f"unknown pattern {values['pattern']!r}")
        key = name.casefold()
        entry = companies.get(key)
        if entry and last != key:
            found.append(f"{name}'s rows are not next to each other")
        elif entry and not found and (listed_only or not entry["shares"]):
            found.append(f"{name} has a row with no pattern and other rows")
        elif entry and not found:
            if (entry["problems"], entry["counted"], entry["catalog_share"], entry["snapshot"]) != (
                    problems, counted, catalog_share, values["snapshot"]):
                found.append(f"{name}'s problems, counted, catalog_share, and snapshot differ between its rows")
            if any(p == values["pattern"] for p, _ in entry["shares"]):
                found.append(f"{values['pattern']} appears more than once for {name}")
        last = key
        if found:
            errors.append(f"row {number}: " + "; ".join(found))
            continue
        if not entry:
            entry = companies[key] = {"company": DISPLAY.get(key, name), "problems": problems, "counted": counted,
                                      "catalog_share": catalog_share, "snapshot": values["snapshot"], "shares": []}
        if not listed_only:
            entry["shares"].append((values["pattern"], share))
    if errors:
        raise DataFileError(filename, errors)
    return companies


def general(companies, order):
    """The most common patterns across companies (docs/rules.md): each pattern's share averaged
    over every company with shares of its own, each company counting once, rounded half up to
    one decimal. Returns a dict like a company's, with "companies" (how many were averaged),
    "snapshot", and "shares" highest first, ties in pattern-list order; None if no company
    has shares."""
    averaged = [company for company in companies.values() if company["shares"]]
    if not averaged:
        return None
    totals = {}
    for company in averaged:
        for name, share in company["shares"]:
            totals[name] = totals.get(name, 0) + Fraction(str(share))
    position = {name: i for i, name in enumerate(order)}
    shares = sorted(((name, _percent(total / 100, len(averaged))) for name, total in totals.items()),
                    key=lambda item: (-item[1], position.get(item[0], len(position))))
    return {"companies": len(averaged), "snapshot": averaged[0]["snapshot"],
            "shares": [(name, share) for name, share in shares if share > 0]}


def preset(company, categories, order):
    """The patterns a company's preset (or `general`) fills in, as [(pattern, percent)]: its core patterns with
    at least COMPANY_PRESET_MIN_SHARE, highest first, ties in pattern-list order, at most
    COMPANY_PRESET_MAX."""
    position = {name: i for i, name in enumerate(order)}
    chosen = [(name, share) for name, share in company["shares"]
              if categories.get(name) == "core" and share >= c.COMPANY_PRESET_MIN_SHARE]
    chosen.sort(key=lambda item: (-item[1], position[item[0]]))
    return chosen[:c.COMPANY_PRESET_MAX]


def find(companies, name):
    """The company `parse_companies` read under this name, ignoring case and surrounding spaces,
    or under one of its aliases; None if there is none."""
    key = (name or "").strip().casefold()
    if key in companies:
        return companies[key]
    alias = ALIASES.get(key)
    return companies.get(alias.casefold()) if alias else None


def whole(share):
    """A share as a whole number, rounded half up, as the form shows it."""
    return math.floor(share + 0.5)


def preset_view(company, categories, order):
    """What the interview form shows for a company's preset (D11): its name, the patterns it fills
    in with whole-number shares, the problems it rests on, and the snapshot's date, such as
    "20 Oct 2026". None if the preset fills in no patterns."""
    chosen = preset(company, categories, order)
    if not chosen:
        return None
    return {
        "company": company["company"],
        "patterns": [[name, whole(share)] for name, share in chosen],
        "problems": company["problems"],
        "snapshot": _day(company["snapshot"]),
    }


def general_view(most_common, categories, order):
    """What the form shows for the most common patterns (`general`): the patterns filled in with
    whole-number shares, how many companies they come from, and the snapshot's date. None if
    there are none."""
    chosen = preset(most_common, categories, order) if most_common else []
    if not chosen:
        return None
    return {"patterns": [[name, whole(share)] for name, share in chosen], "companies": most_common["companies"],
            "snapshot": _day(most_common["snapshot"])}


def fallback_view(company):
    """What the form shows for a company with no shares of its own, which fills in the most
    common patterns: its name and how many problems it has."""
    return {"company": company["company"], "problems": company["problems"], "general": True}


def _day(snapshot):
    day = date.fromisoformat(snapshot)
    return f"{day.day} {_MONTHS[day.month - 1]} {day.year}"


_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def lookup_names(companies):
    """{name or alias, casefolded: key in `companies`} for every way a company can be found."""
    names = {key: key for key in companies}
    for alias, target in ALIASES.items():
        if target.casefold() in companies and alias not in names:
            names[alias] = target.casefold()
    return names


def to_markdown(companies, categories, order, unmapped):
    """docs/companies.md: what each preset rests on, every company's shares, the most common
    patterns and the companies that fill them in, and the topic table.

    `companies` is what `parse_companies` returns; `unmapped` is {topic: rows} for the topics
    in the snapshot that map to nothing.
    """
    snapshot = next(iter(companies.values()))["snapshot"] if companies else ""
    own = [company for company in companies.values() if company["shares"]]
    others = [company for company in companies.values() if not company["shares"]]
    most_common = general(companies, order)
    lines = [
        "# Company presets",
        "",
        "Written by `flask --app codecompass build-companies`; do not edit by hand. The rule is in "
        "`docs/rules.md` (R-60). Shares come from the all-time lists in a snapshot of "
        "[liquidslr/leetcode-company-wise-problems](https://github.com/liquidslr/leetcode-company-wise-problems), "
        f"a mirror of LeetCode's company tags, dated {snapshot}, for every company with at least "
        f"{c.COMPANY_MIN_PROBLEMS} problems ({len(own)} companies). The other {len(others)} companies "
        "are listed too, and fill in the most common patterns across those with shares of their own.",
        "",
        "## Coverage",
        "",
        "*Counted* is how many of the company's problems added to the shares. *From catalog* is the "
        "percentage of the counted frequency that came from problems in the catalog, so it rests on "
        "reviewed tags; the rest rests on LeetCode's topics. *Preset* is what the form fills in.",
        "",
        "| Company | Problems | Counted | From catalog | Preset |",
        "| --- | --- | --- | --- | --- |",
    ]
    for company in own:
        chosen = ", ".join(f"{name} {whole(share)}%" for name, share in preset(company, categories, order))
        lines.append(f"| {company['company']} | {company['problems']} | {company['counted']} | "
                     f"{company['catalog_share']:.1f}% | {chosen or '(none)'} |")
    lines += ["", "## All shares", "",
              "Every pattern with a share above zero, advanced patterns (in italics) included.", ""]
    for company in own:
        shares = ", ".join((f"*{name}*" if categories.get(name) == "advanced" else name) + f" {share:.1f}"
                           for name, share in company["shares"])
        lines.append(f"- **{company['company']}**: {shares}")
    if most_common:
        chosen = ", ".join(f"{name} {whole(share)}%" for name, share in preset(most_common, categories, order))
        shares = ", ".join((f"*{name}*" if categories.get(name) == "advanced" else name) + f" {share:.1f}"
                           for name, share in most_common["shares"])
        lines += ["", "## The most common patterns", "",
                  f"Each pattern's share averaged over the {most_common['companies']} companies above, each "
                  "company counting once. A company with too few problems for shares of its own fills in "
                  f"these instead: {chosen or '(none)'}.", "", f"All shares: {shares}."]
    if others:
        lines += ["", "## Companies without shares of their own", "",
                  f"Fewer than {c.COMPANY_MIN_PROBLEMS} problems, or none counted, with how many problems each has:", "",
                  ", ".join(f"{company['company']} ({company['problems']})" for company in others)]
    lines += ["", "## LeetCode topics", "",
              "Used only for problems that are not in the catalog.", "",
              "**Specific** topics map to one pattern each:", "",
              "| Topic | Pattern |", "| --- | --- |"]
    lines += [f"| {topic} | {SPECIFIC[topic]} |" for topic in sorted(SPECIFIC, key=lambda t: (order.index(SPECIFIC[t]), t))]
    lines += ["", "**Generic** topics map to their pattern only when none of a problem's topics is specific:", "",
              "| Topic | Pattern |", "| --- | --- |"]
    lines += [f"| {topic} | {GENERIC[topic]} |" for topic in sorted(GENERIC, key=lambda t: (order.index(GENERIC[t]), t))]
    lines += ["", f"{' and '.join(sorted(TRAVERSAL))} map to Graph Traversal only when the problem has none of "
              f"{', '.join(sorted(TREE_TOPICS))}; otherwise they count as specific topics.", "",
              "**Topics that map to nothing**, with how many rows in the snapshot have each:", ""]
    lines.append(", ".join(f"{topic} ({count})" for topic, count in
                           sorted(unmapped.items(), key=lambda item: (-item[1], item[0]))) or "(none)")
    lines += ["", "## Other names", "", "A preset is also found by these names, ignoring case:", ""]
    lines += [f"- {alias} for {DISPLAY.get(target.casefold(), target)}" for alias, target in ALIASES.items()]
    return "\n".join(lines) + "\n"
