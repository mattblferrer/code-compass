"""Review streak (R-30)."""
from .dates import add_days


def review_streak(days, today):
    """Count consecutive days with a completed due review, ending today or yesterday.

    `days` are dicts with "date" and "completed" (at least one due review was completed
    that day); other keys are ignored. Any day without a completed review ends the
    streak, even one with nothing due. Today cannot end it, since it is not over yet.
    """
    completed = {d["date"] for d in days if d["completed"] and d["date"] <= today}
    day = today if today in completed else add_days(today, -1)
    count = 0
    while day in completed:
        count += 1
        day = add_days(day, -1)
    return count
