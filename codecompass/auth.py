"""Hosted mode's accounts and request safety (R-51, R-53, R-56).

People sign in one of three ways, and each way is its own account: with GitHub, with Google,
or with a username and password made here. For GitHub and Google, CodeCompass keeps only the
account's ID and name. For a password, it keeps a salted scrypt hash (Werkzeug's), never the
password. The browser holds a random session token in the signed session cookie, and the
database holds only its hash, so signing out ends that session everywhere it was copied.

This module is the only code that contacts GitHub and Google, and only while someone signs in
with them. In local mode none of it runs: the app has one user and no sign-in.
"""
import functools
import hashlib
import hmac

import click
import secrets
import time
from datetime import timedelta
from urllib.parse import urlparse

from flask.cli import with_appcontext
from flask import (Blueprint, abort, current_app, flash, g, jsonify, redirect, render_template, request, session,
                   url_for)
from markupsafe import Markup
from werkzeug.security import check_password_hash, generate_password_hash

from . import db, limits
from .core import constants as c
from .core.validation import local_path, validate_new_login, validate_password

bp = Blueprint("auth", __name__)

SESSION_DAYS = 30  # A session ends after this many days without use (R-51), provisional.
TOUCH_SECONDS = 3600  # How often a session's last use is written down.
# Pages anyone may open without signing in.
PUBLIC = {"auth.sign_in", "auth.github", "auth.github_callback", "auth.google", "auth.google_callback",
          "auth.password_sign_in", "auth.sign_up", "auth.privacy", "static"}

# The outside sign-ins, in the order the sign-in page shows them. Each shows only when the
# site has its client ID (deploying.md).
PROVIDERS = {"github": "GitHub", "google": "Google"}
# How each way of signing in names the account, on the account page and in the account tool.
METHOD_NAMES = {"github": "GitHub username", "google": "Google name", "password": "username"}
FULL = "CodeCompass is full for now: it has reached its limit of accounts. Existing accounts can still sign in."
# Google's ID tokens name either issuer.
GOOGLE_CLAIMS = {"iss": {"values": ["https://accounts.google.com", "accounts.google.com"]}}

_oauth = None


class UsernameTaken(Exception):
    pass


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
    # Google's endpoints are written out rather than read from its discovery document, so
    # starting a sign-in sends no request from the server.
    _oauth.register(
        "google",
        client_id=app.config.get("GOOGLE_CLIENT_ID"),
        client_secret=app.config.get("GOOGLE_CLIENT_SECRET"),
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        access_token_url="https://oauth2.googleapis.com/token",
        jwks_uri="https://www.googleapis.com/oauth2/v3/certs",
        client_kwargs={"scope": "openid profile"},  # The account's ID and name: no email.
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


def _method(row):
    if row["github_id"] is not None:
        return "github"
    return "google" if row["google_id"] is not None else "password"


def _signed_in():
    """Find the signed-in account, or send the visitor to sign in."""
    g.user_id = g.user = None
    token = session.get("token")
    if token:
        conn = db.open_db(current_app.config)
        try:
            row = conn.execute(
                """SELECT u.id, u.login, u.name, u.github_id, u.google_id, s.last_used
                   FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash = ?""",
                (_hash(token),)).fetchone()
            now = time.time()
            if row and now - row["last_used"] > SESSION_DAYS * 86400:
                with conn:
                    conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_hash(token),))
                row = None
            if row:
                if now - row["last_used"] > TOUCH_SECONDS:
                    with conn:
                        conn.execute("UPDATE sessions SET last_used = ? WHERE token_hash = ?", (now, _hash(token)))
                g.user_id = row["id"]
                g.user = {"login": row["login"], "name": row["name"], "method": _method(row)}
        finally:
            conn.close()
        if g.user_id is None:
            session.pop("token", None)
    if g.user_id is None and current_app.testing and current_app.config.get("TESTING_USER_ID"):
        g.user_id = current_app.config["TESTING_USER_ID"]  # Tests of other features run signed in.
        g.user = {"login": "tester", "name": None, "method": "github"}
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
    if request.endpoint == "main.restore_backup":
        from .backup import MAX_BACKUP_BYTES

        # Reading the token below reads the upload, so a backup's own limit must apply first.
        request.max_content_length = MAX_BACKUP_BYTES
    sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token") or ""
    expected = session.get("csrf", "")
    # Compared as bytes: compare_digest refuses text with non-ASCII characters.
    if not expected or not hmac.compare_digest(sent.encode(), expected.encode()):
        if _wants_json():
            return jsonify({"error": "expired"}), 400
        return render_template("form_expired.html"), 400


# Only this site's own scripts run; styles may sit in attributes (charts and score tiles use
# them); forms post only here, or to GitHub or Google when signing in; and no site may frame the pages.
CONTENT_POLICY = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                  "connect-src 'self'; form-action 'self' https://github.com https://accounts.google.com; "
                  "frame-ancestors 'none'; base-uri 'none'; object-src 'none'")


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


def _providers():
    """The outside sign-ins this site has set up, as (key, label) pairs."""
    return [(key, label) for key, label in PROVIDERS.items() if current_app.config.get(f"{key.upper()}_CLIENT_ID")]


@bp.route("/signin")
def sign_in():
    if g.get("user_id") and session.get("token"):
        return redirect(_safe_next(request.args.get("next")))
    return render_template("signin.html", next=_safe_next(request.args.get("next")),
                           providers=_providers() if db.hosted() else [])


def _allow_sign_in(conn):
    """Count a sign-in attempt from this address (R-53). False, with a message, past the limit."""
    if limits.allow(conn, f"signin:{request.remote_addr}", c.SIGNIN_LIMIT, c.LIMIT_WINDOW_SECONDS):
        return True
    flash("Too many sign-in attempts. Wait a few minutes and try again.")
    return False


def _send_to(provider):
    """Send the visitor to GitHub or Google to sign in. Posted, so another site cannot start it."""
    if not db.hosted() or not current_app.config.get(f"{provider.upper()}_CLIENT_ID"):
        abort(404)  # Local mode has no sign-in; its landing page links to the dashboard instead.
    conn = db.open_db(current_app.config)
    try:
        if not _allow_sign_in(conn):
            return redirect(url_for("auth.sign_in"))
    finally:
        conn.close()
    session["next"] = _safe_next(request.form.get("next"))
    client = _oauth.create_client(provider)
    return client.authorize_redirect(url_for(f"auth.{provider}_callback", _external=True))


@bp.post("/signin/github")
def github():
    return _send_to("github")


@bp.post("/signin/google")
def google():
    return _send_to("google")


def github_profile():
    """The signed-in GitHub account's public profile, after GitHub sends the visitor back.
    Replaced in tests, which never contact GitHub."""
    token = _oauth.github.authorize_access_token()
    return _oauth.github.get("user", token=token).json()


def google_profile():
    """The claims in the signed-in Google account's ID token, after Google sends the visitor
    back. Authlib checks the token against Google's published keys, and its issuer, audience,
    expiry, and the nonce sent with the visitor. Replaced in tests, which never contact Google."""
    return _oauth.google.authorize_access_token(claims_options=GOOGLE_CLAIMS).get("userinfo")


@bp.route("/signin/github/callback")
def github_callback():
    if not db.hosted():
        abort(404)
    try:
        profile = github_profile()
    except Exception:  # Declined on GitHub, an expired link, or GitHub could not be reached.
        flash("Signing in with GitHub did not finish. Try again.")
        return redirect(url_for("auth.sign_in"))
    if not isinstance(profile, dict) or not isinstance(profile.get("id"), int) or not profile.get("login"):
        flash("GitHub did not say who you are. Try again.")
        return redirect(url_for("auth.sign_in"))
    return _sign_in_as("github_id", profile["id"], profile["login"], profile.get("name"))


@bp.route("/signin/google/callback")
def google_callback():
    if not db.hosted():
        abort(404)
    try:
        profile = google_profile()
    except Exception:  # Declined on Google, an expired link, a token that fails its checks, or no reply.
        flash("Signing in with Google did not finish. Try again.")
        return redirect(url_for("auth.sign_in"))
    if not isinstance(profile, dict) or not isinstance(profile.get("sub"), str) or not profile["sub"]:
        flash("Google did not say who you are. Try again.")
        return redirect(url_for("auth.sign_in"))
    name = profile.get("name") if isinstance(profile.get("name"), str) else None
    name = (name or "").strip()[:100] or None
    return _sign_in_as("google_id", profile["sub"], name or "Google account", name)


def _sign_in_as(column, key, login, name):
    """Sign in to the account for a GitHub or Google ID, made if new and there is room."""
    from .views import today

    # Read before start_session, which clears the session.
    next_page = _safe_next(session.pop("next", None))
    conn = db.open_db(current_app.config)
    try:
        user_id = account_for(conn, column, key, login, name, today())
        if user_id is None:
            flash(FULL)
            return redirect(url_for("auth.sign_in"))
        start_session(conn, user_id)
    finally:
        conn.close()
    return redirect(next_page)


def _sign_up_lock(conn):
    conn.execute("SELECT pg_advisory_xact_lock(726356)")  # One sign-up at a time, so the cap holds.


def _full(conn):
    return conn.execute("SELECT count(*) FROM users").fetchone()[0] >= c.MAX_ACCOUNTS


def account_for(conn, column, key, login, name, today):
    """The account for a GitHub or Google ID (`column` is github_id or google_id), made if new
    and there is room (R-51). None when full. `today` is the user's date, kept as the day the
    account was made."""
    if column not in ("github_id", "google_id"):
        raise ValueError(column)
    with conn:
        _sign_up_lock(conn)
        row = conn.execute(f"SELECT id FROM users WHERE {column} = ?", (key,)).fetchone()
        if row:
            conn.execute("UPDATE users SET login = ?, name = ? WHERE id = ?", (login, name, row["id"]))
            return row["id"]
        if _full(conn):
            return None
        user_id = conn.execute(f"INSERT INTO users ({column}, login, name, created) VALUES (?, ?, ?, ?)",
                               (key, login, name, today)).lastrowid
    from . import pg

    pg.ensure_user_schema(conn, user_id)
    return user_id


def make_password_account(conn, username, password, today):
    """A new account that signs in with `username` and `password` (R-51). None when full;
    raises UsernameTaken when another password account has the username, ignoring case."""
    password_hash = generate_password_hash(password)
    with conn:
        _sign_up_lock(conn)
        if conn.execute("SELECT 1 FROM users WHERE lower(login) = lower(?) AND password_hash IS NOT NULL",
                        (username,)).fetchone():
            raise UsernameTaken(username)
        if _full(conn):
            return None
        user_id = conn.execute("INSERT INTO users (login, password_hash, created) VALUES (?, ?, ?)",
                               (username, password_hash, today)).lastrowid
    from . import pg

    pg.ensure_user_schema(conn, user_id)
    return user_id


@functools.cache
def _stand_in_hash():
    return generate_password_hash(secrets.token_urlsafe(16))


def check_password(conn, username, password):
    """The id of the password account with this username and password, else None. A username
    with no account takes as long to check, so the time taken does not tell which usernames exist."""
    if len(password) > c.PASSWORD_MAX_LENGTH:
        return None
    row = conn.execute("SELECT id, password_hash FROM users WHERE lower(login) = lower(?) AND password_hash IS NOT NULL",
                       (username,)).fetchone()
    if row is None:
        check_password_hash(_stand_in_hash(), password)
        return None
    return row["id"] if check_password_hash(row["password_hash"], password) else None


def set_password(conn, user_id, password, keep_session=None):
    """Give a password account a new password, and end its sessions but `keep_session` (a
    session token), so anyone who knew the old password is signed out."""
    with conn:
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ? AND password_hash IS NOT NULL",
                     (generate_password_hash(password), user_id))
        conn.execute("DELETE FROM sessions WHERE user_id = ? AND token_hash <> ?",
                     (user_id, _hash(keep_session) if keep_session else ""))


def _allow_password_try(conn, username):
    """Count a password try for this username from any address (R-53)."""
    key = f"password:{username.lower()[:c.USERNAME_MAX_LENGTH]}"
    if limits.allow(conn, key, c.PASSWORD_TRY_LIMIT, c.LIMIT_WINDOW_SECONDS):
        return True
    flash("Too many sign-in attempts for this username. Wait a few minutes and try again.")
    return False


def _password_page(making, next_page, errors=None, username="", status=200):
    return render_template("password.html", making=making, next=next_page, errors=errors or {}, username=username,
                           username_min=c.USERNAME_MIN_LENGTH, username_max=c.USERNAME_MAX_LENGTH,
                           password_min=c.PASSWORD_MIN_LENGTH, password_max=c.PASSWORD_MAX_LENGTH), status


@bp.route("/signin/password", methods=["GET", "POST"])
def password_sign_in():
    if not db.hosted():
        abort(404)
    next_page = _safe_next(request.values.get("next"))
    if request.method == "GET":
        return _password_page(False, next_page)
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    conn = db.open_db(current_app.config)
    try:
        if not _allow_sign_in(conn) or not _allow_password_try(conn, username):
            return redirect(url_for("auth.password_sign_in", next=next_page))
        user_id = check_password(conn, username, password)
        if user_id is not None:
            start_session(conn, user_id)
            return redirect(next_page)
    finally:
        conn.close()
    return _password_page(False, next_page, {"form": "The username or password is wrong."}, username, 400)


@bp.route("/signup", methods=["GET", "POST"])
def sign_up():
    if not db.hosted():
        abort(404)
    next_page = _safe_next(request.values.get("next"))
    if request.method == "GET":
        return _password_page(True, next_page)
    values, errors = validate_new_login(request.form)
    conn = db.open_db(current_app.config)
    try:
        if not _allow_sign_in(conn):
            return redirect(url_for("auth.sign_up", next=next_page))
        if not errors:
            from .views import today

            try:
                user_id = make_password_account(conn, values["username"], values["password"], today())
            except UsernameTaken:
                errors["username"] = "That username is taken. Choose another."
            else:
                if user_id is None:
                    flash(FULL)
                    return redirect(url_for("auth.sign_in"))
                start_session(conn, user_id)
                return redirect(next_page)
    finally:
        conn.close()
    return _password_page(True, next_page, errors, values["username"], 400)


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


# --- The account page: changing a password, and deleting the account (R-51, R-56) ---

def _account_page(errors=None, status=200):
    return render_template("account.html", method_name=METHOD_NAMES[g.user["method"]],
                           provider=PROVIDERS.get(g.user["method"]), errors=errors or {},
                           password_min=c.PASSWORD_MIN_LENGTH, password_max=c.PASSWORD_MAX_LENGTH), status


@bp.route("/account", methods=["GET", "POST"])
def account():
    """The account page, and deleting the account after the user confirms."""
    if not db.hosted():
        abort(404)
    if request.method == "POST":
        if (request.form.get("confirm") or "").strip() != g.user["login"]:
            flash(f"Type your {METHOD_NAMES[g.user['method']]} to confirm. Nothing was deleted.")
            return _account_page(status=400)
        delete_account(db.get_db(), g.user_id)
        session.clear()
        flash("Your account and all its data were deleted.")
        return redirect(url_for("auth.sign_in"))
    return _account_page()


@bp.post("/account/password")
def change_password():
    """Change a password account's password, after checking the current one."""
    if not db.hosted() or g.user["method"] != "password":
        abort(404)
    values, errors = validate_password(request.form, g.user["login"])
    conn = db.open_db(current_app.config)
    try:
        if not _allow_password_try(conn, g.user["login"]):
            return redirect(url_for("auth.account"))
        if check_password(conn, g.user["login"], request.form.get("current_password") or "") != g.user_id:
            errors = {"current_password": "That is not your current password."}
        if not errors:
            set_password(conn, g.user_id, values["password"], keep_session=session.get("token"))
            flash("Your password was changed. Any other browser signed in to this account was signed out.")
            return redirect(url_for("auth.account"))
    finally:
        conn.close()
    return _account_page(errors, 400)


def delete_account(conn, user_id):
    """Remove the account's schema, custom problems, sessions, and the account itself."""
    from . import pg

    with conn:
        pg.drop_user_schema(conn, user_id)
        conn.execute("DELETE FROM public.users WHERE id = ?", (user_id,))


# --- The author's account tool (security review): run from a laptop against the database ---

def _account_rows(conn):
    rows = []
    for user in conn.execute("""SELECT u.id, u.login, u.github_id, u.google_id, u.created,
                                       max(s.last_used) AS last_used
                                FROM users u LEFT JOIN sessions s ON s.user_id = u.id
                                GROUP BY u.id, u.login, u.github_id, u.google_id, u.created
                                ORDER BY u.id""").fetchall():
        from . import pg

        schema = pg.schema_name(user["id"])
        has = conn.execute("SELECT 1 FROM information_schema.tables WHERE table_schema = ? AND table_name = 'attempts'",
                           (schema,)).fetchone()
        attempts = conn.execute(f"SELECT count(*) FROM {schema}.attempts").fetchone()[0] if has else 0
        seen = time.strftime("%Y-%m-%d", time.gmtime(user["last_used"])) if user["last_used"] else "-"
        rows.append((user["login"], user["created"], seen, attempts, _method(user)))
    return rows


def _find_account(conn, login, method):
    """The one account named `login`, signing in by `method` if given. Several accounts can
    share a name across the ways of signing in, and then `method` must say which."""
    rows = [row for row in conn.execute("SELECT id, login, github_id, google_id FROM users WHERE login = ?",
                                        (login,)).fetchall()
            if method is None or _method(row) == method]
    if not rows:
        raise click.ClickException(f"No account has the name {login}" + (f" with {method} sign-in." if method else "."))
    if len(rows) > 1:
        methods = ", ".join(sorted({_method(row) for row in rows}))
        raise click.ClickException(f"More than one account has the name {login} ({methods}). "
                                   "Add --method to say which.")
    return rows[0]


METHOD_OPTION = click.option("--method", type=click.Choice(["github", "google", "password"]),
                             help="How the account signs in, when several share the name.")


@click.group("accounts", invoke_without_command=True)
@click.pass_context
@with_appcontext
def accounts_command(ctx):
    """Hosted mode: list the accounts (name, created, last signed in, attempts, how it signs in)."""
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
    for login, created, seen, attempts, method in rows:
        click.echo(f"{login:<40} created {created}  last signed in {seen}  {attempts} attempts  ({method})")


@accounts_command.command("delete")
@click.argument("login")
@METHOD_OPTION
@click.option("--yes", is_flag=True, help="Do not ask to confirm.")
@with_appcontext
def delete_account_command(login, method, yes):
    """Delete the account with this name and all its data. It cannot be undone."""
    conn = db.open_db(current_app.config)
    try:
        row = _find_account(conn, login, method)
        if not yes:
            click.confirm(f"Delete {login}'s account and all its data? This cannot be undone.", abort=True)
        delete_account(conn, row["id"])
    finally:
        conn.close()
    click.echo(f"Deleted {login}'s account.")


@accounts_command.command("reset-password")
@click.argument("username")
@with_appcontext
def reset_password_command(username):
    """Give a username-and-password account a new password, and sign it out everywhere.
    The site sends no email, so its owner passes the new password on (R-51)."""
    conn = db.open_db(current_app.config)
    try:
        row = conn.execute("SELECT id, login FROM users WHERE lower(login) = lower(?) AND password_hash IS NOT NULL",
                           (username,)).fetchone()
        if row is None:
            raise click.ClickException(f"No account signs in with the username {username}.")
        password = secrets.token_urlsafe(c.PASSWORD_MIN_LENGTH)
        set_password(conn, row["id"], password)
    finally:
        conn.close()
    click.echo(f"{row['login']}'s new password is {password}")
    click.echo("Pass it on privately. They can change it on their account page. "
               "Every browser signed in to the account was signed out.")
