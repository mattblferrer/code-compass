"""Sibling selection (R-28). See docs/rules.md."""
from . import constants as c

# Rank of a level gap: same level, one easier, then one harder.
GAP_RANK = {0: 0, -1: 1, 1: 2}


def choose_sibling(due, candidates, inactive=(), very_hard_on=False):
    """Return the chosen candidate, or None to suggest the original problem.

    `due` has "difficulty" and "patterns". Each candidate has "position",
    "difficulty", and "patterns", plus optional true flags "custom",
    "attempted", "reserved", "dismissed", and "not_now".
    """
    due_patterns = set(due["patterns"])
    due_level = c.LEVELS.index(due["difficulty"])
    inactive = set(inactive)
    best, best_key = None, None
    for problem in candidates:
        if any(problem.get(flag) for flag in ("custom", "attempted", "reserved", "dismissed", "not_now")):
            continue
        patterns = set(problem["patterns"])
        gap = c.LEVELS.index(problem["difficulty"]) - due_level
        if not patterns & due_patterns or gap not in GAP_RANK:
            continue
        if (patterns & inactive) - due_patterns:
            continue
        if problem["difficulty"] == c.VERY_HARD and not (very_hard_on or due["difficulty"] == c.VERY_HARD):
            continue
        key = (GAP_RANK[gap], -len(patterns & due_patterns), len(patterns - due_patterns), problem["position"])
        if best_key is None or key < best_key:
            best, best_key = problem, key
    return best
