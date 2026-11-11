"""Linked accounts, sync items, and rating history in the database (R-33, R-34).

remote.py makes the requests and core/sync.py reads them; this module stores the
results. The current time and the user's local dates come from the route layer.
"""
import json
import threading
from datetime import date, datetime, timedelta, timezone

from . import remote
from .db import connect
from .core import constants as c
from .core import sync as rules

SYNC_SITES = tuple(rules.SITES)


def accounts(conn):
    """Linked usernames by site, with when each last synced (UTC ISO text, or None)."""
    rows = conn.execute("SELECT site, username, last_synced FROM linked_accounts").fetchall()
    return {row["site"]: dict(row) for row in rows}


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
                report(site, {"state": "error"})
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
        # Sites that finished before the error keep their results; the rest say it failed.
        results = []
        for s in job.sites:
            state = job.sites[s]
            if state["state"] == "done":
                results.append({"site": s, "label": rules.SITES[s], "added": state["added"] or 0, "error": None})
            else:
                results.append({"site": s, "label": rules.SITES[s], "added": 0, "error": "failed",
                                "source": rules.SITES[s], "username": ""})
                job.report(s, {"state": "error"})
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
            "INSERT OR REPLACE INTO rating_history (site, username, contest, date, rating) VALUES (?, ?, ?, ?, ?)",
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


def pending_items(conn):
    """Items waiting for an outcome, oldest first. An item is hidden once an attempt
    on its problem and date exists, however that attempt was logged (R-33)."""
    rows = conn.execute("SELECT * FROM sync_items WHERE status = 'pending' ORDER BY date, id").fetchall()
    items = []
    for row in rows:
        item = _with_problem(conn, row)
        if item["problem_id"] and conn.execute("SELECT 1 FROM attempts WHERE problem_id = ? AND date = ?",
                                               (item["problem_id"], item["date"])).fetchone():
            continue
        items.append(item)
    return items


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
    cutoff = (date.fromisoformat(today) - timedelta(days=c.UNDO_DAYS)).isoformat()
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
    cutoff = (date.fromisoformat(today) - timedelta(days=c.UNDO_DAYS)).isoformat()
    with conn:
        conn.execute("DELETE FROM sync_batches WHERE id = ?", (batch_id,))
        if row["date"] < cutoff:
            return None
        done = json.loads(row["payload"])
        conn.executemany("DELETE FROM attempts WHERE id = ? AND entry_method = 'sync'",
                         [(i,) for i in done["attempts"]])
        conn.executemany(
            """DELETE FROM problems WHERE id = ? AND is_custom = 1
               AND NOT EXISTS (SELECT 1 FROM attempts WHERE problem_id = problems.id OR review_of_problem_id = problems.id)""",
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
