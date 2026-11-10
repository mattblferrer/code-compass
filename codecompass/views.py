import csv
import io
from datetime import date

from flask import Blueprint, Response, abort, flash, jsonify, redirect, render_template, request, url_for

from . import picker, queries
from .core.problem_refs import ID_HINTS, SITES
from .core.exchange import COLUMNS, export_rows, plan_import
from .core.recommend import active_interview
from .core.reviews import ics
from .core.sites import FILTER_SITES, KINDS
from .state import DEFAULT_SETTINGS, Snapshot
from .core import constants as c
from .core.validation import (
    OUTCOME_DEFINITIONS,
    OUTCOME_LABELS,
    format_clock,
    format_minutes,
    validate_attempt,
    validate_interview,
    validate_problem,
    validate_settings,
)
from .db import get_db

bp = Blueprint("main", __name__)


def today():
    """The user's local date. Only routes read the clock."""
    return date.today().isoformat()


@bp.app_template_filter("clock")
def clock_filter(seconds):
    return format_clock(seconds)


@bp.app_template_filter("outcome")
def outcome_filter(outcome):
    return OUTCOME_LABELS.get(outcome, outcome)


def attempt_form(template, form, errors, picked=None, **extra):
    return render_template(
        template,
        form=form,
        errors=errors,
        picked=picked,
        sites=SITES,
        id_hints=ID_HINTS,
        outcomes=c.OUTCOMES,
        outcome_labels=OUTCOME_LABELS,
        outcome_definitions=OUTCOME_DEFINITIONS,
        today=today(),
        **extra,
    ), (400 if errors else 200)


def checked_attempt(conn, form, hint_check=True):
    """Resolve the problem and validate the attempt. Returns (values, errors, picker error)."""
    problem_id, picked = picker.resolve(conn, form)
    hint = hint_check and problem_id is not None and queries.unused_hint(conn, problem_id)
    values, errors = validate_attempt(form, today(), problem_id, hint)
    if picked:
        errors["problem"] = picked["message"]
    return values, errors, picked


@bp.route("/problems/search")
def search_problems():
    """Title search for the problem picker (R-38). Reads only the local database."""
    return jsonify(picker.search(get_db(), request.args.get("q", "")))


@bp.route("/problems/find")
def find_problem():
    """Site and ID lookup for the problem picker (R-38). Reads only the local database."""
    conn = get_db()
    site = request.args.get("site", "")
    found = picker.find_by_ref(conn, site, request.args.get("ref", ""))
    show_custom = site == picker.OTHER or found["link"] is not None
    return jsonify({
        "problem": picker.as_result(found["row"]) if found["row"] else None,
        "message": found["message"],
        "custom_url": picker.custom_url_for(found) if show_custom and not found["row"] else None,
    })


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
    if request.method == "GET":
        form = {"date": today()}
        chosen = request.args.get("problem", type=int)
        if chosen and queries.get_problem(conn, chosen):
            form["problem"] = picker.label_for(conn, chosen)
            form["problem_id"] = str(chosen)
        return attempt_form("log.html", form, {})

    form = request.form.to_dict()
    values, errors, picked = checked_attempt(conn, form)
    if errors:
        return attempt_form("log.html", form, errors, picked)
    problem_id = values["problem_id"]
    values["review_of_problem_id"] = Snapshot(conn, today()).review_of(problem_id, values["date"])
    queries.add_attempt(conn, values)
    flash("Attempt saved.")
    return redirect(url_for("main.problem", problem_id=problem_id))


@bp.route("/attempts/<int:attempt_id>/edit", methods=["GET", "POST"])
def edit_attempt(attempt_id):
    conn = get_db()
    attempt = queries.get_attempt(conn, attempt_id) or abort(404)
    if request.method == "GET":
        form = {
            "problem": picker.label_for(conn, attempt["problem_id"]),
            "problem_id": str(attempt["problem_id"]),
            "date": attempt["date"],
            "outcome": attempt["outcome"],
            "time_minutes": format_minutes(attempt["time_seconds"]),
            "time_seconds": attempt["time_seconds"] or "",
            "notes": attempt["notes"] or "",
        }
        return attempt_form("log.html", form, {}, attempt=attempt)

    form = request.form.to_dict()
    values, errors, picked = checked_attempt(conn, form, hint_check=False)
    if errors:
        return attempt_form("log.html", form, errors, picked, attempt=attempt)
    problem_id = values["problem_id"]
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
    item_id = queries.delete_attempt(conn, attempt_id, today())
    # The category carries what Undo needs; base.html shows it as a toast.
    flash("Attempt deleted.", f"undo-delete:{item_id}")
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
        form = {"link": request.args.get("link", ""), "title": request.args.get("title", "")}
        if request.args.get("difficulty") in c.LEVELS:
            form["difficulty"] = request.args["difficulty"]
        return render_template("problem_new.html", form=form, chosen=[], errors={}, patterns=patterns, levels=c.LEVELS)

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


@bp.route("/settings", methods=["GET", "POST"])
def settings():
    """Starting difficulty, advanced and very hard switches, pattern targets and
    mastered patterns, and the site filter (R-13, R-32, R-36)."""
    conn = get_db()
    patterns = queries.patterns(conn)
    if request.method == "POST":
        values, errors = validate_settings(request.form, [p["name"] for p in patterns], FILTER_SITES, KINDS)
        if not errors:
            queries.save_settings(conn, values)
            flash("Settings saved.")
            return redirect(url_for("main.settings"))
        current = values
        status = 400
    else:
        saved = queries.read_settings(conn)
        current = {**DEFAULT_SETTINGS, **saved["settings"], "preferences": saved["preferences"],
                   "hidden": saved["hidden"]}
        errors, status = {}, 200
    return render_template(
        "settings.html", current=current, errors=errors, patterns=patterns, levels=c.LEVELS,
        sites=[(site, SITES[site]) for site in FILTER_SITES], kinds=KINDS,
    ), status


def interview_page(conn, form, chosen, errors, editing=None, status=200):
    """The interviews page: the list, with the one in focus marked, and the add or edit form (R-15)."""
    rows = queries.interviews(conn)
    focus = active_interview(
        [{"company": r["company"], "date": r["date"], "patterns": r["patterns"], "difficulty": r["target_difficulty"]}
         for r in rows],
        today(),
    )
    return render_template(
        "interviews.html", interviews=rows, focus_date=focus["date"] if focus else None, today=today(),
        window=c.FOCUS_WINDOW_DAYS, form=form, chosen=chosen, errors=errors, editing=editing,
        patterns=queries.patterns(conn), levels=c.LEVELS,
    ), status


def checked_interview(conn):
    names = [p["name"] for p in queries.patterns(conn)]
    return validate_interview(request.form, request.form.getlist("patterns"), names)


@bp.route("/interviews", methods=["GET", "POST"])
def interviews():
    conn = get_db()
    if request.method == "GET":
        return interview_page(conn, {}, [], {})
    values, errors = checked_interview(conn)
    if errors:
        return interview_page(conn, request.form.to_dict(), request.form.getlist("patterns"), errors, status=400)
    queries.save_interview(conn, values)
    flash(f"Interview with {values['company']} added.")
    return redirect(url_for("main.interviews"))


@bp.route("/interviews/<int:interview_id>/edit", methods=["GET", "POST"])
def edit_interview(interview_id):
    conn = get_db()
    interview = queries.get_interview(conn, interview_id) or abort(404)
    if request.method == "GET":
        form = {"company": interview["company"], "date": interview["date"],
                "target_difficulty": interview["target_difficulty"] or ""}
        return interview_page(conn, form, interview["patterns"], {}, editing=interview)
    values, errors = checked_interview(conn)
    if errors:
        return interview_page(conn, request.form.to_dict(), request.form.getlist("patterns"), errors,
                              editing=interview, status=400)
    queries.save_interview(conn, values, interview_id)
    flash(f"Interview with {values['company']} updated.")
    return redirect(url_for("main.interviews"))


@bp.post("/interviews/<int:interview_id>/delete")
def delete_interview(interview_id):
    conn = get_db()
    interview = queries.get_interview(conn, interview_id) or abort(404)
    item_id = queries.delete_interview(conn, interview_id, today())
    flash(f"Interview with {interview['company']} deleted.", f"undo-delete:{item_id}")
    return redirect(url_for("main.interviews"))


@bp.post("/undo/<int:item_id>")
def undo_delete(item_id):
    """Restore a deleted attempt or interview (R-07, R-15)."""
    restored = queries.restore_deleted(get_db(), item_id)
    if restored is None:
        flash("That can no longer be undone.")
        return redirect(url_for("main.dashboard"))
    kind, row = restored
    if kind == "attempt":
        flash("Attempt restored.")
        return redirect(url_for("main.problem", problem_id=row["problem_id"]))
    flash(f"Interview with {row['company']} restored.")
    return redirect(url_for("main.interviews"))


@bp.route("/attempts.csv")
def export_csv():
    """All attempts as CSV, in logged order (R-19)."""
    conn = get_db()
    attempts = queries.all_attempts(conn)
    problems = queries.problems_by_id(
        conn, {a["problem_id"] for a in attempts} | {a["review_of_problem_id"] for a in attempts if a["review_of_problem_id"]}
    )
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(export_rows(attempts, problems))
    # A byte-order mark lets spreadsheet apps read the file as UTF-8.
    return Response("\ufeff" + out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="codecompass-attempts-{today()}.csv"'})


@bp.route("/import", methods=["GET", "POST"])
def import_csv():
    """Import attempts from a CSV file and report skipped rows (R-19, R-20)."""
    if request.method == "GET":
        return render_template("import.html", result=None, columns=COLUMNS)
    upload = request.files.get("file")
    error = None
    if upload is None or not upload.filename:
        error = "Choose a CSV file to import."
    else:
        try:
            text = upload.read().decode("utf-8-sig")
        except UnicodeDecodeError:
            error = "The file is not UTF-8 text. Save it from your spreadsheet as CSV UTF-8."
    if error:
        return render_template("import.html", result={"error": error}, columns=COLUMNS), 400
    conn = get_db()
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    plan = plan_import(rows, reader.fieldnames, queries.problems_by_id(conn), queries.all_attempts(conn),
                       [p["name"] for p in queries.patterns(conn)], today())
    if plan["error"]:
        return render_template("import.html", result={"error": plan["error"]}, columns=COLUMNS), 400
    queries.apply_import(conn, plan)
    result = {"error": None, "rows": len(rows), "imported": len(plan["attempts"]),
              "created": [p["title"] for p in plan["new_problems"]], "skipped": plan["skipped"]}
    return render_template("import.html", result=result, columns=COLUMNS)
