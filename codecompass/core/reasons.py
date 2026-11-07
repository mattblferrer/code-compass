"""Hint eligibility (R-27) and recommendation reasons (R-16)."""
from . import constants as c
from .dates import days_between
from .recommend import INTERVIEW, REVIEW, TARGET, UNSCORED, WEAK


def hint_eligible(problem_patterns, attempt_counts):
    """True when any of the problem's patterns has too few attempts for a score."""
    return any(attempt_counts.get(p, 0) < c.MIN_ATTEMPTS for p in problem_patterns)


def reason(item, hint, scores, today, original_title=None, interview=None):
    """The stated reason for one recommendation. Never names a pattern when `hint` is True.

    Whether a hint is available and a review's due date are shown separately.
    """
    group, pattern = item["group"], item["pattern"]
    if group == REVIEW:
        return f"Review of {original_title}" if original_title else "Due for another try"
    if hint:
        if group == TARGET:
            return "Target pattern, new to you"
        if group == INTERVIEW and interview:
            return f"Practice for {', '.join(interview['companies'])} on {interview['date']}"
        return "New pattern for you"
    if group == TARGET:
        return f"Target pattern: {pattern}"
    if group == INTERVIEW and interview:
        return f"Practice for {', '.join(interview['companies'])} on {interview['date']}: {pattern}"
    if group == UNSCORED:
        return f"{pattern}: not enough data yet"
    if group == WEAK and pattern in scores:
        info = scores[pattern]
        days = days_between(info["last"], today)
        ago = "today" if days == 0 else "1 day ago" if days == 1 else f"{days} days ago"
        return f"{pattern}: score {info['score']:.0f}, last practiced {ago}"
    return pattern or ""
