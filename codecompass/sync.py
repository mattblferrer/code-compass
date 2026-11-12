"""Linked accounts, sync items, and rating history in the database (R-33, R-34).

remote.py makes the requests and core/sync.py reads them; this module stores the
results. The current time and the user's local dates come from the route layer.
"""
import json
import threading
from datetime import datetime, timezone

from . import remote
from .db import connect
from .core import constants as c
from .core.dates import undo_cutoff
from .core import sync as rules

SYNC_SITES = tuple(rules.SITES)
# LeetCode's data comes from an undocumented source its terms do not allow scraping, so a
# public server never asks it for anyone: hosted mode syncs Codeforces and AtCoder only (R-33).
HOSTED_SITES = tuple(s for s in SYNC_SITES if s != "leetcode")


def sites_for(conn):
    """The sites this mode can sync."""
    return HOSTED_SITES if getattr(conn, "hosted", False) else SYNC_SITES


def accounts(conn):
    """Linked usernames by site, with when each last synced (UTC ISO text, or None). In hosted
    mode a LeetCode username, as a backup from local mode may bring, is left out (R-33)."""
    rows = conn.execute("SELECT site, username, last_synced FROM linked_accounts").fetchall()
    sites = sites_for(conn)
    return {row["site"]: dict(row) for row in rows if row["site"] in sites}


def link_accounts(conn, values):
    """Save one username per site; a blank one unlinks the site. A new username starts with a first sync."""
    current = accounts(conn)
    with conn:
        for site, username in values.items():
            old = current.get(site)
            if old and old["username"] == username:
                continue
            conn.execute("DELETE FROM linked_accounts WHERE site = ?", (site,))
            if username:
                conn.execute("INSERT INTO linked_accounts (site, username) VALUES (?, ?)", (site, username))


def _seconds(text):
    return int(datetime.fromisoformat(text).timestamp()) if text else None


def run(conn, now, local_date, report=None):
    """Sync every linked account. Returns one result per site: its label, username, items added,
    and any error kind.

    Each site is stored in its own transaction, and only once all its requests
    succeed, so a failed or refused sync changes nothing and leaves the previous
    sync time in place. `report`, if given, is called as report(site, fields) as
    each site starts, reads, and finishes, for the progress shown while syncing.
    """
    results = []
    for site, account in sorted(accounts(conn).items(), key=lambda kv: SYNC_SITES.index(kv[0])):
        result = {"site": site, "label": rules.SITES[site], "username": account["username"], "added": 0,
                  "error": None}
        since = rules.sync_since(_seconds(account["last_synced"]), now)
        known = {row["link"] for row in conn.execute("SELECT link FROM problems WHERE link LIKE ?",
                                                     (f"%{site}.%",))}

        def read(seen, site=site, since=since):
            if report:
                report(site, {"state": "running", "step": seen["step"], "read": seen["read"],
                              "oldest": seen["oldest"], "newest": seen["newest"], "first": since == 0,
                              "fraction": rules.sync_fraction(site, since, now, seen["oldest"], seen["newest"])})

        if report:
            report(site, {"state": "running", "step": "submissions", "first": since == 0})
        try:
            submissions, ratings = remote.sync(site, account["username"], since, known, read)
        except remote.RequestFailed as error:
            result["error"], result["source"] = error.kind, error.site
            results.append(result)
            if report:
                report(site, {"state": "error", "error": error.kind, "source": error.site,
                              "username": account["username"]})
            continue
        if report:
            report(site, {"state": "running", "step": "saving", "fraction": 1.0})
        result["added"] = _store(conn, site, account["username"], submissions, ratings, now, local_date)
        results.append(result)
        if report:
            report(site, {"state": "done", "added": result["added"], "fraction": 1.0})
    return results


class Job:
    """A sync running in the background, with what each site has read so far (R-33).

    The sync page asks for its progress while it runs and shows the results once,
    when it is done. Only one runs at a time.
    """

    def __init__(self, sites, earlier=None):
        self._lock = threading.Lock()
        self.earlier = earlier or []  # Results of a finished sync not shown yet, shown with these.
        self.sites = {site: {"site": site, "label": rules.SITES[site], "state": "waiting", "step": None,
                             "read": 0, "oldest": None, "newest": None, "first": False, "fraction": None,
                             "added": None} for site in sites}
        self.results = None
        self.done = False
        self.shown = False

    def report(self, site, fields):
        with self._lock:
            self.sites[site].update(fields)

    def progress(self):
        with self._lock:
            return {"running": not self.done, "done": self.done,
                    "sites": [dict(self.sites[s]) for s in SYNC_SITES if s in self.sites]}

    def take_results(self):
        """The results, the first time they are asked for after the sync ends; otherwise None."""
        with self._lock:
            if not self.done or self.shown:
                return None
            self.shown = True
            return self.earlier + (self.results or [])


_jobs = {}  # By database path.
_jobs_lock = threading.Lock()


def current_job(database):
    return _jobs.get(database)


def start(database, now, local_date):
    """Start syncing every linked account in the background, unless a sync is already running.

    Returns the running job. The sync uses its own database connection, since the
    request that started it ends right away.
    """
    with _jobs_lock:
        job = _jobs.get(database)
        if job is not None and not job.done:
            return job
        conn = connect(database)
        try:
            sites = [s for s in SYNC_SITES if s in accounts(conn)]
        finally:
            conn.close()
        # A finished sync whose results were never shown passes them on, so none are lost.
        unseen = job.take_results() if job is not None else None
        job = Job(sites, unseen)
        _jobs[database] = job
    job.thread = threading.Thread(target=_work, args=(job, database, now, local_date), daemon=True)
    job.thread.start()
    return job


def _work(job, database, now, local_date):
    conn = connect(database)
    try:
        job.results = run(conn, now, local_date, job.report)
    except Exception:  # Never leave the page waiting on a sync that stopped.
        # Each site keeps what happened to it: its results, its own error, or that the sync
        # stopped before or while it ran.
        results = []
        for s in job.sites:
            state = job.sites[s]
            result = {"site": s, "label": rules.SITES[s], "added": 0, "error": None, "username": ""}
            if state["state"] == "done":
                result["added"] = state["added"] or 0
            elif state["state"] == "error" and state.get("error"):
                result.update(error=state["error"], source=state.get("source") or rules.SITES[s],
                              username=state.get("username", ""))
            else:
                result["error"] = "stopped"
                job.report(s, {"state": "error"})
            results.append(result)
        job.results = results
    finally:
        conn.close()
        job.done = True


def _store(conn, site, username, submissions, ratings, now, local_date):
    added = 0
    with conn:
        for item in rules.group_by_day(submissions, local_date):
            existing = conn.execute("SELECT id, accepted FROM sync_items WHERE site = ? AND problem_link = ? AND date = ?",
                                    (site, item["link"], item["date"])).fetchone()
            if item["accepted"]:
                # Failed tries on earlier days, still waiting for an outcome, fold into this solve.
                conn.execute("""DELETE FROM sync_items WHERE site = ? AND problem_link = ? AND date < ?
                                AND accepted = 0 AND status = 'pending'""", (site, item["link"], item["date"]))
            elif conn.execute("""SELECT 1 FROM sync_items WHERE site = ? AND problem_link = ? AND date > ?
                                 AND accepted = 1""", (site, item["link"], item["date"])).fetchone():
                continue  # Already solved on a later day.
            if existing:
                # A later accepted submission that day marks the item accepted; nothing is listed twice.
                if item["accepted"] and not existing["accepted"]:
                    conn.execute("UPDATE sync_items SET accepted = 1 WHERE id = ?", (existing["id"],))
                continue
            conn.execute(
                """INSERT INTO sync_items (site, username, problem_link, title, date, accepted, rating, tags, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
                (site, username, item["link"], item["title"], item["date"], int(item["accepted"]),
                 item["rating"], json.dumps(item["tags"]) if item["tags"] else None),
            )
            added += 1
        conn.execute("DELETE FROM rating_history WHERE site = ? AND username = ?", (site, username))
        conn.executemany(
            """INSERT INTO rating_history (site, username, contest, date, rating) VALUES (?, ?, ?, ?, ?)
               ON CONFLICT (site, username, contest) DO UPDATE SET date = excluded.date, rating = excluded.rating""",
            [(site, username, r["contest"], local_date(r["time"]), r["rating"]) for r in ratings],
        )
        stamp = datetime.fromtimestamp(now, timezone.utc).isoformat(timespec="seconds")
        conn.execute("UPDATE linked_accounts SET last_synced = ? WHERE site = ? AND username = ?",
                     (stamp, site, username))
    return added


def _with_problem(conn, row):
    item = dict(row)
    item["tags"] = json.loads(item["tags"]) if item["tags"] else []
    problem = conn.execute("SELECT id, title FROM problems WHERE link = ?", (item["problem_link"],)).fetchone()
    item["problem_id"] = problem["id"] if problem else None
    if problem:
        item["title"] = problem["title"]
    return item


# Waiting items with their problem when it is in CodeCompass, leaving out any whose
# problem already has an attempt that day, however it was logged (R-33). One query.
_PENDING = """
    FROM sync_items s LEFT JOIN problems p ON p.link = s.problem_link
    WHERE s.status = 'pending'
      AND NOT EXISTS (SELECT 1 FROM attempts a WHERE a.problem_id = p.id AND a.date = s.date)"""


def pending_items(conn):
    """Items waiting for an outcome, oldest first, each with "problem_id" (None when the
    problem is new to CodeCompass) and, for a known problem, its title and "difficulty"."""
    items = []
    for row in conn.execute(f"SELECT s.*, p.id AS known_id, p.title AS known_title, p.difficulty AS known_difficulty"
                            f" {_PENDING} ORDER BY s.date, s.id"):
        item = dict(row)
        item["tags"] = json.loads(item["tags"]) if item["tags"] else []
        item["problem_id"] = item.pop("known_id")
        title, item["difficulty"] = item.pop("known_title"), item.pop("known_difficulty")
        if title is not None:
            item["title"] = title
        items.append(item)
    return items


def pending_count(conn):
    """How many items wait for an outcome, as pending_items would list them."""
    return conn.execute(f"SELECT count(*) {_PENDING}").fetchone()[0]


def get_item(conn, item_id):
    row = conn.execute("SELECT * FROM sync_items WHERE id = ?", (item_id,)).fetchone()
    return _with_problem(conn, row) if row else None


def set_status(conn, item_id, status):
    with conn:
        conn.execute("UPDATE sync_items SET status = ? WHERE id = ?", (status, item_id))


def record_batch(conn, done, today):
    """Keep what a batch action did so it can be undone, and drop records older than c.UNDO_DAYS.

    `done` holds the lists "items", "attempts", "problems", and "hints". Returns the record's id.
    """
    cutoff = undo_cutoff(today)
    with conn:
        conn.execute("DELETE FROM sync_batches WHERE date < ?", (cutoff,))
        return conn.execute("INSERT INTO sync_batches (payload, date) VALUES (?, ?)",
                            (json.dumps(done), today)).lastrowid


def undo_batch(conn, batch_id, today):
    """Reverse a batch action: its attempts are removed, custom problems it added that
    nothing else uses are removed, used hints are unused again, and its items wait for an
    outcome again. Returns how many items came back, or None if it can no longer be undone.
    """
    row = conn.execute("SELECT * FROM sync_batches WHERE id = ?", (batch_id,)).fetchone()
    if row is None:
        return None
    cutoff = undo_cutoff(today)
    with conn:
        conn.execute("DELETE FROM sync_batches WHERE id = ?", (batch_id,))
        if row["date"] < cutoff:
            return None
        done = json.loads(row["payload"])
        conn.executemany("DELETE FROM attempts WHERE id = ? AND entry_method = 'sync'",
                         [(i,) for i in done["attempts"]])
        conn.executemany(
            """DELETE FROM problems WHERE id = ? AND is_custom = 1
               AND NOT EXISTS (SELECT 1 FROM attempts WHERE problem_id = problems.id OR review_of_problem_id = problems.id)
               AND NOT EXISTS (SELECT 1 FROM problem_notes WHERE problem_id = problems.id)
               AND NOT EXISTS (SELECT 1 FROM problem_links WHERE problem_id = problems.id)""",
            [(i,) for i in done["problems"]])
        conn.executemany("UPDATE hint_reveals SET used = 0 WHERE id = ?", [(i,) for i in done["hints"]])
        back = 0
        for item_id in done["items"]:
            back += conn.execute("UPDATE sync_items SET status = 'pending' WHERE id = ? AND status != 'pending'",
                                 (item_id,)).rowcount
    return back


def rating_history(conn):
    """Stored ratings for each linked account, oldest first. Shown only; never scored (R-34)."""
    out = {}
    for site, account in accounts(conn).items():
        out[site] = [dict(r) for r in conn.execute(
            "SELECT contest, date, rating FROM rating_history WHERE site = ? AND username = ? ORDER BY date, rowid",
            (site, account["username"]))]
    return out


# --- Hosted mode (R-54): a sync run in steps across requests ---
#
# Nothing runs between requests on the host, so the sync's state is saved in the account's
# sync_job table, and each request that asks (any open CodeCompass page does, every second
# or so) runs it for up to c.SYNC_STEP_SECONDS. Requests to a site are spaced across every
# account by the shared site_clock table; a request whose turn falls after the step ends
# waits for the next step.

LEASE_MARGIN = 30.0  # Seconds past its end before a step that stopped answering is given up.


class Later(Exception):
    """The site's next turn falls after this step ends, so the sync goes on at the next step."""


def _shared_pacer(conn, deadline):
    """Wait for the host's turn across every account, reserving it, or raise Later."""

    def pace(host, spacing):
        with conn:
            conn.execute("INSERT INTO site_clock (host, next_at) VALUES (?, 0) ON CONFLICT DO NOTHING", (host,))
            next_at = conn.execute("SELECT next_at FROM site_clock WHERE host = ? FOR UPDATE", (host,)).fetchone()[0]
            now = remote.wall_clock()
            slot = max(next_at, now)
            if slot > deadline:
                raise Later(host)
            conn.execute("UPDATE site_clock SET next_at = ? WHERE host = ?", (slot + spacing, host))
        if slot > now:
            remote.sleep(round(slot - now, 3))  # To the millisecond: times of day are large numbers.

    return pace


def _site_progress(site):
    return {"site": site, "label": rules.SITES[site], "state": "waiting", "step": None, "read": 0, "oldest": None,
            "newest": None, "first": False, "fraction": None, "added": None, "turn": False}


def _load(conn):
    row = conn.execute("SELECT data FROM sync_job WHERE id = 1").fetchone()
    return json.loads(row["data"]) if row else None


def _save(conn, data, lease=None):
    with conn:
        if lease is None:
            conn.execute("""INSERT INTO sync_job (id, data, lease) VALUES (1, ?, 0)
                            ON CONFLICT (id) DO UPDATE SET data = excluded.data, lease = 0""", (json.dumps(data),))
        else:
            conn.execute("UPDATE sync_job SET data = ?, lease = ? WHERE id = 1", (json.dumps(data), lease))


class StoredJob:
    """The account's saved sync, read like Job."""

    def __init__(self, conn, data):
        self.conn, self.data = conn, data

    @property
    def done(self):
        return self.data["done"]

    def progress(self):
        return {"running": not self.done, "done": self.done,
                "sites": [dict(self.data["sites"][s]) for s in self.data["order"]]}

    def take_results(self):
        """The results, the first time they are asked for after the sync ends; otherwise None."""
        if not self.done or self.data["shown"]:
            return None
        self.data["shown"] = True
        with self.conn:
            self.conn.execute("UPDATE sync_job SET data = ? WHERE id = 1", (json.dumps(self.data),))
        return self.data["earlier"] + self.data["results"]


def stored_job(conn):
    data = _load(conn)
    return StoredJob(conn, data) if data else None


def start_steps(conn, now):
    """Start a sync of every linked account, to run in steps, unless one is running. Returns it."""
    job = stored_job(conn)
    if job and not job.done:
        return job
    earlier = (job.take_results() or []) if job else []  # Results never shown are shown with these.
    sites = [s for s in SYNC_SITES if s in accounts(conn)]
    data = {"now": now, "order": sites, "sites": {s: _site_progress(s) for s in sites}, "index": 0, "state": None,
            "results": [], "earlier": earlier, "done": not sites, "shown": False}
    _save(conn, data)
    return StoredJob(conn, data)


def advance(conn, local_date, budget):
    """Run the account's sync for up to `budget` seconds, unless another request is running it.
    Returns the job, or None when there is none."""
    began = remote.wall_clock()
    deadline = began + budget
    with conn:
        row = conn.execute("UPDATE sync_job SET lease = ? WHERE id = 1 AND lease < ? RETURNING data",
                           (deadline + LEASE_MARGIN, began)).fetchone()
    if row is None:
        return stored_job(conn)
    data = json.loads(row["data"])
    token = remote.pacer.set(_shared_pacer(conn, deadline))
    try:
        while not data["done"] and remote.wall_clock() < deadline:
            _step(conn, data, local_date)
            _save(conn, data, lease=deadline + LEASE_MARGIN)
    except Later:
        site = data["order"][data["index"]]
        data["sites"][site]["turn"] = True  # Shown as waiting for the site's turn.
    except Exception:  # Never leave the pages waiting on a sync that stopped.
        conn.rollback()
        _stop(data)
    finally:
        remote.pacer.reset(token)
        _save(conn, data, lease=0)
    return StoredJob(conn, data)


def _step(conn, data, local_date):
    """Make the current site's next request, and store its results when it is done."""
    site = data["order"][data["index"]]
    progress = data["sites"][site]
    account = accounts(conn).get(site)
    if account is None:  # Unlinked while the sync ran: nothing to read.
        progress.update(state="done", added=0, fraction=1.0)
        data["results"].append({"site": site, "label": rules.SITES[site], "username": "", "added": 0, "error": None})
        _next(data)
        return
    if data["state"] is None:
        since = rules.sync_since(_seconds(account["last_synced"]), data["now"])
        data["state"] = remote.sync_state(site, account["username"], since)
        progress.update(state="running", step="submissions", first=since == 0)
    state = data["state"]
    known = {row["link"] for row in conn.execute("SELECT link FROM problems WHERE link LIKE ?", (f"%{site}.%",))}
    progress["turn"] = False
    try:
        done = remote.sync_step(state, known)
    except remote.RequestFailed as error:
        progress.update(state="error", error=error.kind, source=error.site, username=account["username"])
        data["results"].append({"site": site, "label": rules.SITES[site], "username": account["username"],
                                "added": 0, "error": error.kind, "source": error.site})
        _next(data)
        return
    finally:
        for event in state["events"]:
            if progress["state"] == "running":
                progress.update(step=event["step"], read=event["read"], oldest=event["oldest"], newest=event["newest"],
                                fraction=rules.sync_fraction(site, state["since"], data["now"], event["oldest"],
                                                             event["newest"]))
        state["events"] = []
    if done:
        progress.update(step="saving", fraction=1.0)
        added = _store(conn, site, account["username"], state["submissions"], state["ratings"], data["now"],
                       local_date)
        progress.update(state="done", added=added, fraction=1.0)
        data["results"].append({"site": site, "label": rules.SITES[site], "username": account["username"],
                                "added": added, "error": None})
        _next(data)


def _next(data):
    data["index"] += 1
    data["state"] = None
    if data["index"] >= len(data["order"]):
        data["done"] = True


def _stop(data):
    """End a sync that stopped unexpectedly: finished sites keep their results and errors, and the
    site it stopped on, and any after, say so."""
    reported = {r["site"] for r in data["results"]}
    for site in data["order"]:
        if site not in reported:
            data["sites"][site]["state"] = "error"
            data["results"].append({"site": site, "label": rules.SITES[site], "username": "", "added": 0,
                                    "error": "stopped"})
    data["results"].sort(key=lambda r: data["order"].index(r["site"]))
    data["done"], data["state"] = True, None
