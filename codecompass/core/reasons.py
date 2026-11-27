"""Hint eligibility (R-27), hidden problem details (R-61), and recommendation reasons (R-16)."""
from . import constants as c
from .dates import days_between
from .recommend import INTERVIEW, REVIEW, TARGET, UNSCORED, WEAK


def hint_eligible(problem_patterns, attempt_counts):
    """True when any of the problem's patterns has too few attempts for a score."""
    return any(attempt_counts.get(p, 0) < c.MIN_ATTEMPTS for p in problem_patterns)


def is_solved(outcomes):
    """Whether any of a problem's attempt outcomes solved it: alone, with hints, or after the solution."""
    return any(o != c.NOT_SOLVED for o in outcomes)


def details_hidden(hide_on, solved, revealed):
    """Whether a problem's patterns, difficulty, and review link stay hidden (R-61).

    With the setting on, they stay hidden until the problem is solved in any way
    (`is_solved`), except while the user has revealed them and not yet logged an attempt
    (`revealed`: a revealed hint, R-27, which makes that attempt count as help).
    """
    return bool(hide_on and not revealed and not solved)


def reason(item, hint, scores, today, original_title=None, interview=None, hidden=False):
    """The stated reason for one recommendation. Never names a pattern when `hint` is True,
    and when `hidden` (R-61) names neither a pattern nor the problem a review stands in for.

    Whether a hint is available and a review's due date are shown separately.
    """
    group, pattern = item["group"], item["pattern"]
    if group == REVIEW:
        if hidden:
            return "Due for review"
        return f"Review of {original_title}" if original_title else "Due for another try"
    if hidden:
        if group == TARGET:
            return "One of your target patterns"
        if group == INTERVIEW and interview:
            return f"Practice for {', '.join(interview['companies'])} on {interview['date']}"
        if group == WEAK:
            return "One of your weaker patterns"
        if group == UNSCORED:
            return "A pattern without enough data yet"
        return "Next problem for you"
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
