"""Due reviews, streak days, and the calendar file (R-12, R-28, R-30, R-31)."""
from datetime import timedelta

from . import constants as c
from .dates import add_days, parse
from .schedule import REVIEW, review_schedule


def schedule_attempts(attempts, problem_id):
    """The attempts in one problem's schedule, oldest first.

    That is its own attempts that were not sibling attempts, plus sibling
    attempts made for its reviews. Each attempt has "problem_id",
    "review_of_problem_id", "date", "outcome", and "id".
    """
    rows = [
        a for a in attempts
        if (a["problem_id"] == problem_id and a["review_of_problem_id"] is None)
        or a["review_of_problem_id"] == problem_id
    ]
    return sorted(rows, key=lambda a: (a["date"], a["id"]))


def schedules(attempts):
    """{problem_id: (schedule attempts, schedule rows)} for every scheduled problem."""
    ids = {a["problem_id"] for a in attempts if a["review_of_problem_id"] is None}
    result = {}
    for problem_id in ids:
        own = schedule_attempts(attempts, problem_id)
        if own:
            result[problem_id] = (own, review_schedule(own))
    return result


def due_dates(all_schedules):
    """{problem_id: next due date}."""
    return {pid: rows[-1]["due"] for pid, (_, rows) in all_schedules.items()}


def review_attempt_ids(all_schedules):
    """Ids of attempts that completed a review, on the problem itself or as its sibling (R-12, R-28)."""
    return {attempt["id"] for own, rows in all_schedules.values()
            for attempt, row in zip(own, rows) if row["kind"] == REVIEW}


def last_attempts(all_schedules):
    """{problem_id: date of the latest attempt in its schedule}, sibling reviews included."""
    return {pid: own[-1]["date"] for pid, (own, _) in all_schedules.items()}


def is_stale(last_attempt, day):
    """Whether a problem last attempted on `last_attempt` is old on `day` (R-12)."""
    return last_attempt < add_days(day, -c.STALE_REVIEW_DAYS)


def served_reviews(due_now, last, today):
    """The due reviews to serve (R-12): those of problems attempted within the last
    c.STALE_REVIEW_DAYS days, or, when none of those is due, every due review.

    `due_now` is {problem_id: due date} for reviews due by today, and `last` the
    latest attempt date of each problem. A review held back keeps its schedule, so
    an attempt on that problem still completes it.
    """
    recent = {pid: day for pid, day in due_now.items() if not is_stale(last[pid], today)}
    return recent or dict(due_now)


def streak_days(all_schedules, today):
    """Day records for review_streak: whether a review was due and whether one was completed."""
    due_days, completed = set(), set()
    end = parse(today)
    for own, rows in all_schedules.values():
        for index, row in enumerate(rows):
            start = parse(row["due"])
            if index + 1 < len(rows):
                next_day = parse(own[index + 1]["date"])
                if next_day < start:
                    continue  # An early attempt came first, so this review never fell due.
                stop = next_day
            else:
                stop = end
            day = start
            while day <= min(stop, end):
                due_days.add(day.isoformat())
                day += timedelta(days=1)
        for attempt, row in zip(own, rows):
            if row["kind"] == REVIEW:
                completed.add(attempt["date"])
    days = due_days | completed
    return [{"date": d, "due": d in due_days, "completed": d in completed} for d in sorted(days)]


def ics(events, stamp):
    """An .ics calendar with one all-day event per scheduled review.

    `events` are dicts with "uid", "date", and "summary". `stamp` is a
    YYYY-MM-DD date used for DTSTAMP.
    """
    def escape(text):
        return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//CodeCompass//Reviews//EN", "CALSCALE:GREGORIAN"]
    stamp_text = stamp.replace("-", "") + "T000000Z"
    for event in events:
        day = parse(event["date"])
        lines += [
            "BEGIN:VEVENT",
            f"UID:{event['uid']}",
            f"DTSTAMP:{stamp_text}",
            f"DTSTART;VALUE=DATE:{day.strftime('%Y%m%d')}",
            f"DTEND;VALUE=DATE:{(day + timedelta(days=1)).strftime('%Y%m%d')}",
            f"SUMMARY:{escape(event['summary'])}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"



REVIEW_DAY = "review"
PRACTICE_DAY = "practice"
MISSED_DAY = "missed"
QUIET_DAY = "quiet"


def activity(day_records, attempt_dates, today, days):
    """One status per day for the last `days` days, oldest first.

    `day_records` come from streak_days. A day is "review" when a due review
    was completed, "missed" when reviews were due but none was completed
    (today is never missed), "practice" when only other attempts were logged,
    and "quiet" otherwise.
    """
    records = {r["date"]: r for r in day_records}
    logged = set(attempt_dates)
    result = []
    for back in range(days - 1, -1, -1):
        day = (parse(today) - timedelta(days=back)).isoformat()
        record = records.get(day, {})
        if record.get("completed"):
            status = REVIEW_DAY
        elif record.get("due") and day != today:
            status = MISSED_DAY
        elif day in logged:
            status = PRACTICE_DAY
        else:
            status = QUIET_DAY
        result.append({"date": day, "status": status})
    return result
