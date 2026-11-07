from datetime import date

from flask import Blueprint, Response, abort, flash, redirect, render_template, request, url_for

from . import queries
from .core.reviews import ics
from .state import Snapshot
from .core import constants as c
from .core.validation import (
    OUTCOME_DEFINITIONS,
    OUTCOME_LABELS,
    format_minutes,
    validate_attempt,
    validate_problem,
)
from .db import get_db

bp = Blueprint("main", __name__)


def today():
    """The user's local date. Only routes read the clock."""
    return date.today().isoformat()


@bp.app_template_filter("minutes")
def minutes_filter(seconds):
    return format_minutes(seconds)


@bp.app_template_filter("outcome")
def outcome_filter(outcome):
    return OUTCOME_LABELS.get(outcome, outcome)


def problem_labels(conn):
    """Map each label shown in the problem picker to its problem id."""
    rows = queries.problem_choices(conn)
    counts = {}
    for row in rows:
        base = f"{row['title']} ({row['source']})"
        counts[base] = counts.get(base, 0) + 1
    labels = {}
    for row in rows:
        base = f"{row['title']} ({row['source']})"
        labels[base if counts[base] == 1 else f"{base} #{row['id']}"] = row["id"]
    return labels


def label_for(labels, problem_id):
    for label, pid in labels.items():
        if pid == problem_id:
            return label
    return ""


def attempt_form(template, form, errors, labels, **extra):
    return render_template(
        template,
        form=form,
        errors=errors,
        labels=labels,
        outcomes=c.OUTCOMES,
        outcome_labels=OUTCOME_LABELS,
        outcome_definitions=OUTCOME_DEFINITIONS,
        today=today(),
        **extra,
    ), (400 if errors else 200)


@bp.route("/")
def dashboard():
    snap = Snapshot(get_db(), today())
    return render_template(
        "dashboard.html",
        due_count=len(snap.due_now),
        streak=snap.streak(),
        recommendations=snap.recommendations(),
        patterns=snap.pattern_rows(),
        interview=snap.interview,
        level=snap.level(),
        activity=snap.activity(),
    )


@bp.route("/patterns/<name>")
def pattern(name):
    snap = Snapshot(get_db(), today())
    info = snap.pattern_info.get(name) or abort(404)
    return render_template(
        "pattern.html",
        pattern=info,
        score=snap.scores.get(name, {}).get("score"),
        rows=snap.by_pattern[name],
        min_attempts=c.MIN_ATTEMPTS,
        chart=history_chart(snap.score_history(name)),
    )


def history_chart(points, width=640, height=180, pad=28):
    """Positions for the score history line on a pattern's page."""
    scored = [(i, p) for i, p in enumerate(points) if p["score"] is not None]
    if len(scored) < 2:
        return None
    span = max(len(points) - 1, 1)

    def x(i):
        return round(pad + (width - 2 * pad) * i / span, 1)

    def y(score):
        return round(height - pad - (height - 2 * pad) * score / 100, 1)

    dots = [{"x": x(i), "y": y(p["score"]), "date": p["date"], "score": p["score"]} for i, p in scored]
    return {
        "width": width,
        "height": height,
        "line": " ".join(f"{d['x']},{d['y']}" for d in dots),
        "dots": dots,
        "guides": [{"value": v, "y": y(v)} for v in (0, 40, 70, 100)],
        "left": pad,
        "right": width - pad,
        "first": points[0]["date"],
        "last": points[-1]["date"],
    }


@bp.post("/problems/<int:problem_id>/hint")
def reveal_hint(problem_id):
    conn = get_db()
    queries.get_problem(conn, problem_id) or abort(404)
    if not queries.unused_hint(conn, problem_id):
        with conn:
            conn.execute("INSERT INTO hint_reveals (problem_id, date) VALUES (?, ?)", (problem_id, today()))
    target = request.form.get("next", "")
    if not target.startswith("/") or target.startswith("//"):
        target = url_for("main.dashboard")
    return redirect(target)


@bp.post("/problems/<int:problem_id>/not-now")
def not_now(problem_id):
    conn = get_db()
    queries.get_problem(conn, problem_id) or abort(404)
    review_of = request.form.get("review_of", type=int)
    suggestion_id = ""
    with conn:
        not_now_id = conn.execute(
            "INSERT INTO not_now (problem_id, date) VALUES (?, ?)", (problem_id, today())
        ).lastrowid
        if review_of:
            row = conn.execute(
                """SELECT id FROM sibling_suggestions
                   WHERE due_problem_id = ? AND sibling_problem_id = ? AND status = 'active'
                   ORDER BY id DESC LIMIT 1""",
                (review_of, problem_id),
            ).fetchone()
            if row:
                suggestion_id = row["id"]
                conn.execute(
                    "UPDATE sibling_suggestions SET status = 'dismissed', date = ? WHERE id = ?",
                    (today(), suggestion_id),
                )
    # The category carries what Undo needs to reverse this.
    flash("Hidden from recommendations for 7 days.", f"undo:{not_now_id}:{suggestion_id}")
    return redirect(url_for("main.dashboard"))


@bp.post("/not-now/undo")
def undo_not_now():
    """Reverse a "not now" (R-29): show the problem again, and restore a dismissed sibling."""
    conn = get_db()
    not_now_id = request.form.get("not_now_id", type=int)
    suggestion_id = request.form.get("suggestion_id", type=int)
    with conn:
        if not_now_id:
            conn.execute("DELETE FROM not_now WHERE id = ?", (not_now_id,))
        if suggestion_id:
            row = conn.execute(
                "SELECT due_problem_id FROM sibling_suggestions WHERE id = ? AND status = 'dismissed'",
                (suggestion_id,),
            ).fetchone()
            if row:
                # Drop any sibling chosen in its place, then bring the original back.
                conn.execute(
                    "DELETE FROM sibling_suggestions WHERE due_problem_id = ? AND id > ? AND status = 'active'",
                    (row["due_problem_id"], suggestion_id),
                )
                conn.execute("UPDATE sibling_suggestions SET status = 'active' WHERE id = ?", (suggestion_id,))
    flash("Recommendation restored.")
    return redirect(url_for("main.dashboard"))


@bp.route("/reviews.ics")
def reviews_calendar():
    snap = Snapshot(get_db(), today())
    body = ics(snap.calendar_events(), today())
    return Response(body, mimetype="text/calendar",
                    headers={"Content-Disposition": "attachment; filename=codecompass-reviews.ics"})


@bp.route("/log", methods=["GET", "POST"])
def log_attempt():
    conn = get_db()
    labels = problem_labels(conn)
    if request.method == "GET":
        form = {"date": today()}
        chosen = request.args.get("problem", type=int)
        if chosen:
            form["problem"] = label_for(labels, chosen)
        return attempt_form("log.html", form, {}, labels)

    form = request.form.to_dict()
    problem_id = labels.get((form.get("problem") or "").strip())
    hint = problem_id is not None and queries.unused_hint(conn, problem_id)
    values, errors = validate_attempt(form, today(), problem_id, hint)
    if errors:
        return attempt_form("log.html", form, errors, labels)
    values["review_of_problem_id"] = Snapshot(conn, today()).review_of(problem_id, values["date"])
    queries.add_attempt(conn, values)
    flash("Attempt saved.")
    return redirect(url_for("main.problem", problem_id=problem_id))


@bp.route("/attempts/<int:attempt_id>/edit", methods=["GET", "POST"])
def edit_attempt(attempt_id):
    conn = get_db()
    attempt = queries.get_attempt(conn, attempt_id) or abort(404)
    labels = problem_labels(conn)
    if request.method == "GET":
        form = {
            "problem": label_for(labels, attempt["problem_id"]),
            "date": attempt["date"],
            "outcome": attempt["outcome"],
            "time_minutes": format_minutes(attempt["time_seconds"]),
            "time_seconds": attempt["time_seconds"] or "",
            "notes": attempt["notes"] or "",
        }
        return attempt_form("log.html", form, {}, labels, attempt=attempt)

    form = request.form.to_dict()
    problem_id = labels.get((form.get("problem") or "").strip())
    values, errors = validate_attempt(form, today(), problem_id)
    if errors:
        return attempt_form("log.html", form, errors, labels, attempt=attempt)
    # A sibling attempt moved to another problem no longer completes that review.
    same = problem_id == attempt["problem_id"]
    values["review_of_problem_id"] = attempt["review_of_problem_id"] if same else None
    queries.update_attempt(conn, attempt_id, values)
    flash("Attempt updated.")
    return redirect(url_for("main.problem", problem_id=problem_id))


@bp.post("/attempts/<int:attempt_id>/delete")
def delete_attempt(attempt_id):
    conn = get_db()
    attempt = queries.get_attempt(conn, attempt_id) or abort(404)
    queries.delete_attempt(conn, attempt_id)
    flash("Attempt deleted.")
    return redirect(url_for("main.problem", problem_id=attempt["problem_id"]))


@bp.route("/history")
def history():
    return render_template("history.html", attempts=queries.recent_attempts(get_db(), limit=200))


@bp.route("/problems/<int:problem_id>")
def problem(problem_id):
    conn = get_db()
    row = queries.get_problem(conn, problem_id) or abort(404)
    snap = Snapshot(conn, today())
    return render_template(
        "problem.html",
        problem=row,
        patterns=queries.problem_patterns(conn, problem_id),
        attempts=queries.attempts_for_problem(conn, problem_id),
        due=snap.due.get(problem_id),
        hint_eligible=snap.hint_eligible(problem_id),
        hint=snap.hint(problem_id),
    )


@bp.route("/problems/new", methods=["GET", "POST"])
def new_problem():
    conn = get_db()
    patterns = queries.patterns(conn)
    if request.method == "GET":
        return render_template("problem_new.html", form={}, chosen=[], errors={}, patterns=patterns, levels=c.LEVELS)

    form = request.form.to_dict()
    chosen = request.form.getlist("patterns")
    values, errors = validate_problem(form, chosen, {p["name"] for p in patterns})
    existing = values["link"] and queries.problem_by_link(conn, values["link"])
    if existing:
        flash("That problem already exists, so you can log it here.")
        return redirect(url_for("main.log_attempt", problem=existing["id"]))
    if errors:
        return render_template(
            "problem_new.html", form=form, chosen=chosen, errors=errors, patterns=patterns, levels=c.LEVELS
        ), 400
    problem_id = queries.add_custom_problem(conn, values)
    flash("Problem added. Log your attempt below.")
    return redirect(url_for("main.log_attempt", problem=problem_id))
