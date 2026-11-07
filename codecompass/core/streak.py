"""Review streak (R-30)."""


def review_streak(days, today):
    """Count consecutive review days, ending today or yesterday.

    `days` are dicts with "date", "due" (any review was due that day), and
    "completed" (at least one due review was completed). A day with nothing due
    neither adds to nor breaks the streak, and today cannot break it.
    """
    count = 0
    for day in sorted(days, key=lambda d: d["date"], reverse=True):
        if day["date"] > today:
            continue
        if day["completed"]:
            count += 1
        elif day["due"] and day["date"] != today:
            break
    return count
