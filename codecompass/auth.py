"""Hosted mode's accounts and request safety (R-51, R-53, R-56).

People sign in with GitHub. CodeCompass keeps only the GitHub account's ID and names, never
a password. The browser holds a random session token in the signed session cookie, and the
database holds only its hash, so signing out ends that session everywhere it was copied.

This module is the only code that contacts GitHub, and only while someone signs in. In
local mode none of it runs: the app has one user and no sign-in.
"""
import hashlib
import hmac

import click
import secrets
import time
from datetime import date, timedelta
from urllib.parse import urlparse

from flask.cli import with_appcontext
from flask import (Blueprint, abort, current_app, flash, g, jsonify, redirect, render_template, request, session,
                   url_for)
from markupsafe import Markup

from . import db, limits
from .core import constants as c
from .core.validation import local_path

bp = Blueprint("auth", __name__)

SESSION_DAYS = 30  # A session ends after this many days without use (R-51), provisional.
TOUCH_SECONDS = 3600  # How often a session's last use is written down.
# Pages anyone may open without signing in.
PUBLIC = {"auth.sign_in", "auth.github", "auth.github_callback", "auth.privacy", "static"}

_oauth = None


def init_app(app):
    """Set up sign-in and the request checks. Does nothing in local mode."""
    app.jinja_env.globals["csrf_field"] = csrf_field
    app.jinja_env.globals["csrf_token"] = csrf_token
    app.context_processor(_account)
    app.register_blueprint(bp)
    app.cli.add_command(accounts_command)
    if not db.hosted(app.config):
        return
    from werkzeug.middleware.proxy_fix import ProxyFix

    # The host passes on the original scheme and address, so sign-in links say https.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    app.config.setdefault("FORCE_HTTPS", True)
    app.config.setdefault("CSRF_CHECK", True)
    app.config.update(SESSION_COOKIE_SECURE=app.config["FORCE_HTTPS"], SESSION_COOKIE_HTTPONLY=True,
                      SESSION_COOKIE_SAMESITE="Lax", PERMANENT_SESSION_LIFETIME=timedelta(days=SESSION_DAYS))
    app.before_request(_https_only)
    app.before_request(_signed_in)
    app.before_request(_check_csrf)
    app.after_request(_security_headers)

    global _oauth
    from authlib.integrations.flask_client import OAuth

    _oauth = OAuth(app)
    _oauth.register(
        "github",
        client_id=app.config.get("GITHUB_CLIENT_ID"),
        client_secret=app.config.get("GITHUB_CLIENT_SECRET"),
        access_token_url="https://github.com/login/oauth/access_token",
        authorize_url="https://github.com/login/oauth/authorize",
        api_base_url="https://api.github.com/",
        client_kwargs={"scope": ""},  # The public profile only: no email, no repositories.
    )


def _account():
    """For every page: whether to show the app's navigation, and the signed-in account in hosted mode."""
    if not db.hosted():
        return {"signed_in": True, "account": None, "hosted_mode": False}
    return {"signed_in": g.get("user_id") is not None, "account": g.get("user"), "hosted_mode": True}


# --- Request checks ---

def _https_only():
    if current_app.config["FORCE_HTTPS"] and request.scheme != "https":
        return redirect(request.url.replace("http://", "https://", 1), code=301)


def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def _signed_in():
    """Find the signed-in account, or send the visitor to sign in."""
    g.user_id = g.user = None
    token = session.get("token")
    if token:
        conn = db.open_db(current_app.config)
        try:
            row = conn.execute(
                """SELECT u.id, u.login, u.name, s.last_used FROM sessions s JOIN users u ON u.id = s.user_id
                   WHERE s.token_hash = ?""", (_hash(token),)).fetchone()
            now = time.time()
            if row and now - row["last_used"] > SESSION_DAYS * 86400:
                with conn:
                    conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_hash(token),))
                row = None
            if row:
                if now - row["last_used"] > TOUCH_SECONDS:
                    with conn:
                        conn.execute("UPDATE sessions SET last_used = ? WHERE token_hash = ?", (now, _hash(token)))
                g.user_id, g.user = row["id"], {"login": row["login"], "name": row["name"]}
        finally:
            conn.close()
        if g.user_id is None:
            session.pop("token", None)
    if g.user_id is None and current_app.testing and current_app.config.get("TESTING_USER_ID"):
        g.user_id = current_app.config["TESTING_USER_ID"]  # Tests of other features run signed in.
        g.user = {"login": "tester", "name": None}
    if g.user_id is None and request.endpoint not in PUBLIC:
        if request.method == "GET" and not _wants_json():
            return redirect(url_for("auth.sign_in", next=request.full_path.rstrip("?")))
        return jsonify({"error": "signed_out"}), 401


def _wants_json():
    return request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html


def csrf_token():
    """This session's token for forms and scripts; empty in local mode."""
    if not db.hosted():
        return ""
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def csrf_field():
    token = csrf_token()
    return Markup(f'<input type="hidden" name="csrf_token" value="{token}">') if token else ""


def _check_csrf():
    """Refuse a form post or script request made from another site (R-53)."""
    if request.method != "POST" or not current_app.config["CSRF_CHECK"]:
        return
    sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token") or ""
    expected = session.get("csrf", "")
    # Compared as bytes: compare_digest refuses text with non-ASCII characters.
    if not expected or not hmac.compare_digest(sent.encode(), expected.encode()):
        if _wants_json():
            return jsonify({"error": "expired"}), 400
        return render_template("form_expired.html"), 400


# Only this site's own scripts run; styles may sit in attributes (charts and score tiles use
# them); forms post only here, or to GitHub when signing in; and no site may frame the pages.
CONTENT_POLICY = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                  "connect-src 'self'; form-action 'self' https://github.com; frame-ancestors 'none'; "
                  "base-uri 'none'; object-src 'none'")


def _security_headers(response):
    response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("Content-Security-Policy", CONTENT_POLICY)
    if request.endpoint != "static":
        # Pages show one account's data, so no browser or shared cache keeps a copy.
        response.headers["Cache-Control"] = "no-store"
    return response


# --- Signing in ---

def _safe_next(target):
    """Only a path on this site, so signing in never sends anyone elsewhere."""
    if local_path(target) and not urlparse(target).netloc:
        return target
    return url_for("main.dashboard")


@bp.route("/signin")
def sign_in():
    if g.get("user_id") and session.get("token"):
        return redirect(_safe_next(request.args.get("next")))
    return render_template("signin.html", next=_safe_next(request.args.get("next")))


@bp.post("/signin/github")
def github():
    """Send the visitor to GitHub to sign in. Posted, so another site cannot start it."""
    conn = db.open_db(current_app.config)
    try:
        if not limits.allow(conn, f"signin:{request.remote_addr}", c.SIGNIN_LIMIT, c.LIMIT_WINDOW_SECONDS):
            flash("Too many sign-in attempts. Wait a few minutes and try again.")
            return redirect(url_for("auth.sign_in"))
    finally:
        conn.close()
    session["next"] = _safe_next(request.form.get("next"))
    return _oauth.github.authorize_redirect(url_for("auth.github_callback", _external=True))


def github_profile():
    """The signed-in GitHub account's public profile, after GitHub sends the visitor back.
    Replaced in tests, which never contact GitHub."""
    token = _oauth.github.authorize_access_token()
    return _oauth.github.get("user", token=token).json()


@bp.route("/signin/github/callback")
def github_callback():
    try:
        profile = github_profile()
    except Exception:  # Declined on GitHub, an expired link, or GitHub could not be reached.
        flash("Signing in with GitHub did not finish. Try again.")
        return redirect(url_for("auth.sign_in"))
    if not isinstance(profile, dict) or not isinstance(profile.get("id"), int) or not profile.get("login"):
        flash("GitHub did not say who you are. Try again.")
        return redirect(url_for("auth.sign_in"))
    conn = db.open_db(current_app.config)
    try:
        user_id = account_for(conn, profile)
        if user_id is None:
            flash("CodeCompass is full for now: it has reached its limit of accounts. "
                  "Existing accounts can still sign in.")
            return redirect(url_for("auth.sign_in"))
        start_session(conn, user_id)
    finally:
        conn.close()
    return redirect(_safe_next(session.pop("next", None)))


def account_for(conn, profile):
    """The account for a GitHub profile, made if new and there is room (R-51). None when full."""
    with conn:
        conn.execute("SELECT pg_advisory_xact_lock(726356)")  # One sign-up at a time, so the cap holds.
        row = conn.execute("SELECT id FROM users WHERE github_id = ?", (profile["id"],)).fetchone()
        if row:
            conn.execute("UPDATE users SET login = ?, name = ? WHERE id = ?",
                         (profile["login"], profile.get("name"), row["id"]))
            return row["id"]
        if conn.execute("SELECT count(*) FROM users").fetchone()[0] >= c.MAX_ACCOUNTS:
            return None
        user_id = conn.execute("INSERT INTO users (github_id, login, name, created) VALUES (?, ?, ?, ?)",
                               (profile["id"], profile["login"], profile.get("name"), date.today().isoformat())
                               ).lastrowid
    from . import pg

    pg.ensure_user_schema(conn, user_id)
    return user_id


def start_session(conn, user_id):
    token = secrets.token_urlsafe(32)
    now = time.time()
    with conn:
        conn.execute("INSERT INTO sessions (token_hash, user_id, created, last_used) VALUES (?, ?, ?, ?)",
                     (_hash(token), user_id, now, now))
    session.clear()
    session.permanent = True
    session["token"] = token


@bp.post("/signout")
def sign_out():
    token = session.get("token")
    if token:
        conn = db.open_db(current_app.config)
        try:
            with conn:
                conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_hash(token),))
        finally:
            conn.close()
    session.clear()
    flash("You signed out.")
    return redirect(url_for("auth.sign_in"))


@bp.route("/privacy")
def privacy():
    return render_template("privacy.html", max_accounts=c.MAX_ACCOUNTS, session_days=SESSION_DAYS)


# --- Deleting an account (R-56) ---

@bp.route("/account", methods=["GET", "POST"])
def account():
    """The account page, and deleting the account after the user confirms."""
    if not db.hosted():
        abort(404)
    if request.method == "POST":
        if request.form.get("confirm") != g.user["login"]:
            flash("Type your GitHub username to confirm. Nothing was deleted.")
            return render_template("account.html"), 400
        delete_account(db.get_db(), g.user_id)
        session.clear()
        flash("Your account and all its data were deleted.")
        return redirect(url_for("auth.sign_in"))
    return render_template("account.html")


def delete_account(conn, user_id):
    """Remove the account's schema, custom problems, sessions, and the account itself."""
    from . import pg

    with conn:
        pg.drop_user_schema(conn, user_id)
        conn.execute("DELETE FROM public.users WHERE id = ?", (user_id,))


# --- The author's account tool (security review): run from a laptop against the database ---

def _account_rows(conn):
    rows = []
    for user in conn.execute("""SELECT u.id, u.login, u.created, max(s.last_used) AS last_used
                                FROM users u LEFT JOIN sessions s ON s.user_id = u.id
                                GROUP BY u.id, u.login, u.created ORDER BY u.id""").fetchall():
        from . import pg

        schema = pg.schema_name(user["id"])
        has = conn.execute("SELECT 1 FROM information_schema.tables WHERE table_schema = ? AND table_name = 'attempts'",
                           (schema,)).fetchone()
        attempts = conn.execute(f"SELECT count(*) FROM {schema}.attempts").fetchone()[0] if has else 0
        seen = time.strftime("%Y-%m-%d", time.gmtime(user["last_used"])) if user["last_used"] else "-"
        rows.append((user["login"], user["created"], seen, attempts))
    return rows


@click.group("accounts", invoke_without_command=True)
@click.pass_context
@with_appcontext
def accounts_command(ctx):
    """Hosted mode: list the accounts (GitHub username, created, last signed in, attempts)."""
    if not db.hosted(current_app.config):
        raise click.ClickException("Accounts exist only in hosted mode: set CODECOMPASS_MODE=hosted and "
                                   "CODECOMPASS_DATABASE_URL first.")
    if ctx.invoked_subcommand:
        return
    conn = db.open_db(current_app.config)
    try:
        rows = _account_rows(conn)
    finally:
        conn.close()
    click.echo(f"{len(rows)} of {c.MAX_ACCOUNTS} accounts")
    for login, created, seen, attempts in rows:
        click.echo(f"{login:<40} created {created}  last signed in {seen}  {attempts} attempts")


@accounts_command.command("delete")
@click.argument("login")
@click.option("--yes", is_flag=True, help="Do not ask to confirm.")
@with_appcontext
def delete_account_command(login, yes):
    """Delete the account with this GitHub username and all its data. It cannot be undone."""
    conn = db.open_db(current_app.config)
    try:
        row = conn.execute("SELECT id FROM users WHERE login = ?", (login,)).fetchone()
        if row is None:
            raise click.ClickException(f"No account has the GitHub username {login}.")
        if not yes:
            click.confirm(f"Delete {login}'s account and all its data? This cannot be undone.", abort=True)
        delete_account(conn, row["id"])
    finally:
        conn.close()
    click.echo(f"Deleted {login}'s account.")
