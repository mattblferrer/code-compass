import csv
import io
import time
from datetime import date, datetime
from urllib.parse import quote

from flask import Blueprint, Response, abort, flash, jsonify, redirect, render_template, request, url_for

from . import picker, queries, remote
from . import sync as syncing
from .core.sync import LEETCODE_NOTICE, PROFILE_URLS, new_problem_details, outcome_choices, rating_changes
from .core.problem_refs import ID_HINTS, SITES, from_id, from_link
from .core.exchange import COLUMNS, export_rows, plan_import, references
from .core.recommend import active_interview
from .core.reviews import ics
from .core.sites import FILTER_SITES, KINDS
from .state import Snapshot
from .core import constants as c
from .core.validation import MESSAGES as VALIDATION_MESSAGES
from .core.validation import (
    OUTCOME_DEFINITIONS,
    OUTCOME_LABELS,
    format_clock,
    format_minutes,
    validate_accounts,
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


def now_seconds():
    return int(time.time())


def local_date(seconds):
    """The user's local date for a Unix time from a synced site."""
    return datetime.fromtimestamp(seconds).date().isoformat()


@bp.app_template_filter("clock")
def clock_filter(seconds):
    return format_clock(seconds)


@bp.app_template_filter("outcome")
def outcome_filter(outcome):
    return OUTCOME_LABELS.get(outcome, outcome)


def attempt_form(template, form, errors, picked=None, **extra):
    """The log or edit page: the form, and beside it the chosen problem and, for a new
    attempt, the recommendations to pick from."""
    conn = get_db()
    snap = Snapshot(conn, today())
    editing = extra.get("attempt") is not None
    chosen = str(form.get("problem_id", ""))
    context = snap.problem_context(int(chosen), editing=editing) if chosen.isdigit() else None
    practice = [] if editing else [
        {**r, "label": picker.label_for(conn, r["problem"]["id"])} for r in snap.recommendations()
    ]
    return render_template(
        template,
        form=form,
        errors=errors,
        picked=picked,
        context=context,
        practice=practice,
        # The server's own messages, so checks made as fields are left say exactly what saving would.
        check_messages={
            "date_format": VALIDATION_MESSAGES["date_format"], "date_future": VALIDATION_MESSAGES["date_future"],
            "time": VALIDATION_MESSAGES["time"], "outcome": VALIDATION_MESSAGES["outcome"],
            "unknown": picker.MESSAGES["unknown"], "ambiguous": picker.MESSAGES["ambiguous"],
        },
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
    conn = get_db()
    snap = Snapshot(conn, today())
    return render_template(
        "dashboard.html",
        sync_pending=len(syncing.pending_items(conn)),
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

    dots, before = [], None
    for i, p in scored:
        shown = round(p["score"])
        dots.append({"x": x(i), "y": y(p["score"]), "date": p["date"], "score": p["score"], "shown": shown,
                     "old": before, "change": None if before is None else shown - before,
                     "attempts": p.get("attempts", 0), "since": p.get("since")})
        before = shown
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


@bp.route("/problems/<int:problem_id>/context")
def problem_context(problem_id):
    """The "This problem" card on the log page, fetched when a problem is picked. Local only."""
    context = Snapshot(get_db(), today()).problem_context(problem_id, editing=bool(request.args.get("editing")))
    if context is None:
        abort(404)
    return render_template("_log_context.html", context=context)


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
        chosen, lookup = [], {"site": request.args.get("site", ""), "ref": request.args.get("ref", "") or form["link"]}
        if request.args.get("lookup"):
            form, chosen, lookup = run_lookup(conn, form, lookup, [p["name"] for p in patterns])
        return render_template("problem_new.html", form=form, chosen=chosen, errors={}, patterns=patterns,
                               levels=c.LEVELS, lookup=lookup)

    form = request.form.to_dict()
    chosen = request.form.getlist("patterns")
    values, errors = validate_problem(form, chosen, {p["name"] for p in patterns})
    existing = values["link"] and queries.problem_by_link(conn, values["link"])
    if existing:
        flash("That problem already exists, so you can log it here.")
        return redirect(url_for("main.log_attempt", problem=existing["id"]))
    if errors:
        return render_template(
            "problem_new.html", form=form, chosen=chosen, errors=errors, patterns=patterns, levels=c.LEVELS,
            lookup={"site": "", "ref": form.get("link", "")},
        ), 400
    problem_id = queries.add_custom_problem(conn, values)
    flash("Problem added. Log your attempt below.")
    return redirect(url_for("main.log_attempt", problem=problem_id))


LOOKUP_SITES = {"codeforces": "Codeforces", "atcoder": "AtCoder"}
LOOKUP_MESSAGES = {
    "unrecognized": "Enter a Codeforces or AtCoder problem ID, such as 1520A or abc300_a, or paste its link.",
    "not_found": "{site} has no problem with that ID. Check it, or enter the details by hand.",
    "refused": "{site} refused the request, so the lookup stopped. Try again later, or enter the details by hand.",
    "failed": "Could not reach {site}. Check your connection, or enter the details by hand.",
}


def run_lookup(conn, form, lookup, pattern_names):
    """Fill the custom-problem form from a Codeforces or AtCoder lookup (R-35). Saves nothing.

    Returns (form, chosen patterns, lookup state with a message and, for a problem
    already in CodeCompass, that problem).
    """
    site, ref = lookup["site"], lookup["ref"].strip()
    link = from_id(site, ref) if site in LOOKUP_SITES else None
    found = from_link(link) if link else None
    if not found or found[0] not in LOOKUP_SITES:
        return form, [], {**lookup, "message": LOOKUP_MESSAGES["unrecognized"]}
    site, link = found
    existing = queries.problem_by_link(conn, link)
    if existing:
        # No request is needed: the problem is already here, so it is shown instead of a duplicate.
        return {**form, "link": link}, [], {**lookup, "site": site, "existing": dict(existing)}
    try:
        details = remote.lookup(site, link, pattern_names)
    except remote.RequestFailed as error:
        message = LOOKUP_MESSAGES[error.kind].format(site=error.site)
        return {**form, "link": link}, [], {**lookup, "site": site, "message": message}
    filled = {"title": details["title"], "link": details["link"], "difficulty": details["difficulty"],
              "rating": "" if details["rating"] is None else str(details["rating"])}
    missing = [name for name, value in (("level", details["difficulty"]), ("patterns", details["patterns"])) if not value]
    note = f"Filled in from {details['site']}. Check the details"
    note += f", choose the {' and '.join(missing)}," if missing else ","
    return filled, details["patterns"], {**lookup, "site": site, "message": note + " then add the problem.", "ok": True}


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
        current = queries.current_settings(conn)
        errors, status = {}, 200
    return settings_page(conn, current, errors, patterns, status)


def settings_page(conn, current, errors, patterns, status=200, usernames=None, account_errors=None):
    if usernames is None:
        usernames = {site: a["username"] for site, a in syncing.accounts(conn).items()}
    return render_template(
        "settings.html", current=current, errors=errors, patterns=patterns, levels=c.LEVELS,
        sites=[(site, SITES[site]) for site in FILTER_SITES], kinds=KINDS,
        sync_sites=[(site, SITES[site]) for site in syncing.SYNC_SITES], usernames=usernames,
        account_errors=account_errors or {}, leetcode_notice=LEETCODE_NOTICE,
    ), status


@bp.post("/settings/accounts")
def link_accounts():
    """Link a public username per site for sync (R-33). Only usernames are asked for (R-03)."""
    conn = get_db()
    values, errors = validate_accounts(request.form, syncing.SYNC_SITES)
    if errors:
        current = queries.current_settings(conn)
        typed = {site: request.form.get(f"username:{site}", "") for site in syncing.SYNC_SITES}
        return settings_page(conn, current, {}, queries.patterns(conn), 400, typed, errors)
    syncing.link_accounts(conn, values)
    flash("Linked accounts saved." if any(values.values()) else "Linked accounts saved. No site is linked.")
    return redirect(url_for("main.settings") + "#accounts")


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
    restored = queries.restore_deleted(get_db(), item_id, today())
    if restored is None:
        flash("That can no longer be undone.")
        return redirect(url_for("main.dashboard"))
    kind, row = restored
    if kind == "missing_problem":
        flash("That attempt can't be restored, because its problem is no longer in CodeCompass.")
        return redirect(url_for("main.history"))
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
    plan = plan_import(rows, reader.fieldnames, queries.problems_matching(conn, *references(rows)),
                       queries.all_attempts(conn), [p["name"] for p in queries.patterns(conn)], today(),
                       hinted=queries.unused_hints(conn))
    if plan["error"]:
        return render_template("import.html", result={"error": plan["error"]}, columns=COLUMNS), 400
    queries.apply_import(conn, plan)
    result = {"error": None, "rows": len(rows), "imported": len(plan["attempts"]),
              "created": [p["title"] for p in plan["new_problems"]], "skipped": plan["skipped"]}
    return render_template("import.html", result=result, columns=COLUMNS)


SYNC_MESSAGES = {
    "no_user": "{label}: no user named {username} was found. Check the username in settings.",
    "refused": "{source} refused the request, so the {label} sync stopped. Try again later.",
    "failed": "Could not reach {source}, so the {label} sync stopped. Check your connection and try again.",
}


@bp.route("/sync")
def sync_page():
    """Synced submissions waiting for an outcome (R-33). Rating history is on the profile page."""
    conn = get_db()
    accounts = syncing.accounts(conn)
    items = syncing.pending_items(conn)
    pattern_names = [p["name"] for p in queries.patterns(conn)]
    for item in items:
        item["choices"] = outcome_choices(item["accepted"])
        item["hint"] = bool(item["problem_id"]) and queries.unused_hint(conn, item["problem_id"])
        if not item["problem_id"]:
            item["details"] = new_problem_details(item["site"], item, pattern_names)
    return render_template(
        "sync.html",
        accounts=[(site, SITES[site], accounts[site]) for site in syncing.SYNC_SITES if site in accounts],
        last_synced={site: synced_label(a["last_synced"]) for site, a in accounts.items()},
        items=items, outcome_labels=OUTCOME_LABELS, outcome_definitions=OUTCOME_DEFINITIONS,
        leetcode_notice=LEETCODE_NOTICE, sites=SITES,
    )


@bp.route("/profile")
def profile():
    """Contest rating over time and contest history for each linked account (R-34).

    Shows only what the last sync stored, so it works offline. Ratings never affect
    scores, review dates, or recommendations.
    """
    conn = get_db()
    accounts = syncing.accounts(conn)
    ratings = syncing.rating_history(conn)
    histories = []
    for site in syncing.SYNC_SITES:
        if site not in accounts:
            continue
        rows = rating_changes(site, ratings.get(site, []))
        username = accounts[site]["username"]
        histories.append({
            "site": site, "label": SITES[site], "username": username,
            "url": PROFILE_URLS[site].format(quote(username, safe="")),
            "synced": synced_label(accounts[site]["last_synced"]), "rows": rows, "chart": rating_chart(rows),
            "current": rows[-1]["rating"] if rows else None,
            "best": max(r["rating"] for r in rows) if rows else None,
        })
    return render_template("profile.html", histories=histories, leetcode_notice=LEETCODE_NOTICE)


def synced_label(stamp):
    """A stored UTC sync time in the user's local time, or None before the first sync."""
    if not stamp:
        return None
    return datetime.fromisoformat(stamp).astimezone().strftime("%Y-%m-%d %H:%M")


@bp.post("/sync")
def run_sync():
    """Run a sync the user started. A refused site stops its own sync and says so (R-03)."""
    conn = get_db()
    accounts = syncing.accounts(conn)
    if not accounts:
        flash("Link a username in settings first.")
        return redirect(url_for("main.settings") + "#accounts")
    for result in syncing.run(conn, now_seconds(), local_date):
        if result["error"]:
            flash(SYNC_MESSAGES[result["error"]].format(
                label=result["label"], source=result.get("source", result["label"]),
                username=accounts[result["site"]]["username"]))
        elif result["added"]:
            plural = "submission" if result["added"] == 1 else "submissions"
            flash(f"{result['label']}: {result['added']} new {plural} to confirm.")
        else:
            flash(f"{result['label']}: no new submissions.")
    return redirect(url_for("main.sync_page"))


def pending_item(conn, item_id):
    item = syncing.get_item(conn, item_id) or abort(404)
    if item["status"] != "pending":
        abort(404)
    return item


@bp.post("/sync/items/<int:item_id>/dismiss")
def dismiss_sync_item(item_id):
    """Dismiss an item without an attempt; it does not come back (R-33)."""
    conn = get_db()
    pending_item(conn, item_id)
    syncing.set_status(conn, item_id, "dismissed")
    flash("Item dismissed.")
    return redirect(url_for("main.sync_page"))


@bp.route("/sync/items/<int:item_id>", methods=["GET", "POST"])
def sync_item(item_id):
    """Confirm a synced item with an outcome, which makes it an attempt (R-33).

    An item whose problem is not in CodeCompass becomes a custom problem (R-02),
    with the site's rating and Codeforces tags mapped and the user supplying
    whatever is missing. Nothing is saved until an outcome is chosen.
    """
    conn = get_db()
    item = pending_item(conn, item_id)
    patterns = queries.patterns(conn)
    names = [p["name"] for p in patterns]
    details = None if item["problem_id"] else new_problem_details(item["site"], item, names)
    hint = bool(item["problem_id"]) and queries.unused_hint(conn, item["problem_id"])
    if request.method == "GET":
        return sync_item_page(item, details, patterns, hint, details["patterns"] if details else [],
                              {"difficulty": details["difficulty"]} if details else {}, {})

    form = request.form.to_dict()
    errors = {}
    if form.get("outcome") not in outcome_choices(item["accepted"]):
        errors["outcome"] = "Choose an outcome."
    problem_values, chosen = None, []
    if details:
        # The details form sends its own fields; a confirm from the list uses the mapped values.
        own = bool(form.get("details"))
        chosen = request.form.getlist("patterns") if own else details["patterns"]
        form["difficulty"] = form.get("difficulty", "") if own else details["difficulty"]
        rating = "" if item["rating"] is None else str(item["rating"])
        problem_values, problem_errors = validate_problem(
            {"title": item["title"], "link": item["problem_link"], "difficulty": form["difficulty"], "rating": rating},
            chosen, set(names))
        errors.update(problem_errors)
    values, attempt_errors = validate_attempt({"date": item["date"], "outcome": form.get("outcome", "")},
                                              today(), item["problem_id"] or 0, hint)
    for field, message in attempt_errors.items():
        errors.setdefault(field, message)
    if errors:
        return sync_item_page(item, details, patterns, hint, chosen, form, errors, 400)

    problem_id = item["problem_id"] or queries.add_custom_problem(conn, problem_values)
    values["problem_id"] = problem_id
    values["review_of_problem_id"] = Snapshot(conn, today()).review_of(problem_id, values["date"])
    queries.add_attempt(conn, values, entry_method="sync")
    syncing.set_status(conn, item_id, "confirmed")
    flash(f"Saved {item['title']} on {item['date']} as {OUTCOME_LABELS[values['outcome']].lower()}.")
    return redirect(url_for("main.sync_page"))


def sync_item_page(item, details, patterns, hint, chosen, form, errors, status=200):
    return render_template(
        "sync_item.html", item=item, details=details, patterns=patterns, hint=hint, chosen=chosen, form=form,
        errors=errors, levels=c.LEVELS, choices=outcome_choices(item["accepted"]), outcome_labels=OUTCOME_LABELS,
        outcome_definitions=OUTCOME_DEFINITIONS, sites=SITES, leetcode_notice=LEETCODE_NOTICE,
    ), status


@bp.app_template_filter("signed")
def signed_filter(change):
    """A rating change with its sign, such as +162 or −87."""
    if change is None:
        return ""
    return f"+{change}" if change > 0 else ("−" + str(-change) if change < 0 else "0")


def rating_change_label(row):
    """How a contest changed the rating, as in 1602 → 1764 (+162)."""
    if row.get("old_rating") is None:
        return str(row["rating"])
    return f"{row['old_rating']} → {row['rating']} ({signed_filter(row['change'])})"


def rating_chart(rows, width=640, height=220, left=48, right=16, top=14, bottom=34):
    """Positions for a site's rating line on a time scale: each contest sits at its date.

    This is the whole history, drawn without JavaScript; js/rating_chart.js redraws it
    from the same rows so the time axis can be zoomed and panned.
    """
    if len(rows) < 2:
        return None
    days = [date.fromisoformat(r["date"]).toordinal() for r in rows]
    pad_days = max((days[-1] - days[0]) * 0.02, 3)
    start, end = days[0] - pad_days, days[-1] + pad_days
    low, high = min(r["rating"] for r in rows), max(r["rating"] for r in rows)
    span = max(high - low, 1)

    def x(day):
        return round(left + (width - left - right) * (day - start) / (end - start), 1)

    def y(rating):
        return round(top + (height - top - bottom) * (1 - (rating - low) / span), 1)

    dots = [{"x": x(d), "y": y(r["rating"]), "date": r["date"], "rating": r["rating"], "contest": r["contest"],
             "change": rating_change_label(r)} for d, r in zip(days, rows)]
    years = range(date.fromordinal(days[0]).year + 1, date.fromordinal(days[-1]).year + 1)
    return {
        "width": width, "height": height, "dots": dots,
        "line": " ".join(f"{d['x']},{d['y']}" for d in dots),
        "guides": [{"value": v, "y": y(v)} for v in sorted({low, high})],
        "ticks": [{"label": str(year), "x": x(date(year, 1, 1).toordinal())} for year in years],
        "left": left, "right": width - right, "axis": height - bottom, "first": rows[0]["date"], "last": rows[-1]["date"],
    }
