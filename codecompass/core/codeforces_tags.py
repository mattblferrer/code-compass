"""Map Codeforces tags to patterns without a person (docs/patterns.md, docs/rules.md).

Used for the unreviewed reserve (R-37). Tags on the "too broad" list in
docs/patterns.md map to nothing on their own, and a tag listed for more than one
pattern maps only to the first, except through the tag pairs.
"""

# Tags too broad to map on their own (docs/patterns.md).
BROAD = frozenset({
    "data structures", "graphs", "dfs and similar", "math", "trees", "strings", "dp", "two pointers",
})

# Format tags that describe the contest, not a technique.
IGNORED = frozenset({"*special", "communication"})

# A tag that maps to one pattern by itself.
DIRECT = {
    "binary search": "Binary Search",
    "sortings": "Sorting",
    "brute force": "Backtracking and Brute Force",
    "dsu": "Union-Find",
    "shortest paths": "Shortest Paths",
    "greedy": "Greedy",
    "bitmasks": "Bit Manipulation",
    "implementation": "Simulation and Implementation",
    "schedules": "Simulation and Implementation",
    "number theory": "Number Theory",
    "chinese remainder theorem": "Chinese Remainder Theorem",
    "combinatorics": "Combinatorics",
    "probabilities": "Probability and Expected Value",
    "games": "Game Theory",
    "geometry": "Geometry",
    "matrices": "Matrices and Matrix Exponentiation",
    "fft": "FFT and NTT",
    "constructive algorithms": "Constructive Algorithms",
    "divide and conquer": "Divide and Conquer",
    "meet-in-the-middle": "Meet in the Middle",
    "ternary search": "Ternary Search",
    "hashing": "String Hashing",
    "string suffix structures": "Suffix Structures",
    "flows": "Max Flow and Min Cut",
    "graph matchings": "Bipartite Matching",
    "2-sat": "2-SAT",
    "interactive": "Interactive Problems",
    "expression parsing": "Expression Parsing",
}

# Two tags that together map to a pattern.
PAIRS = {
    frozenset({"trees", "dp"}): "Tree DP",
    frozenset({"bitmasks", "dp"}): "Bitmask DP",
    frozenset({"graphs", "dsu"}): "Minimum Spanning Tree",
}


def patterns_for(tags, order):
    """Pattern names for a problem's tags, in pattern-list order.

    `order` lists every pattern name in pattern-list order.
    """
    tags = set(tags) - IGNORED
    found = {DIRECT[t] for t in tags if t in DIRECT}
    found |= {name for pair, name in PAIRS.items() if pair <= tags}
    return [name for name in order if name in found]
