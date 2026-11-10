"""Linked accounts, sync items, and rating history in the database (R-33, R-34).

remote.py makes the requests and core/sync.py reads them; this module stores the
results. The current time and the user's local dates come from the route layer.
"""
import json
from datetime import datetime, timezone

from . import remote
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


def run(conn, now, local_date):
    """Sync every linked account. Returns one result per site: its label, items added, and any error kind.

    Each site is stored in its own transaction, and only once all its requests
    succeed, so a failed or refused sync changes nothing and leaves the previous
    sync time in place.
    """
    results = []
    for site, account in sorted(accounts(conn).items(), key=lambda kv: SYNC_SITES.index(kv[0])):
        result = {"site": site, "label": rules.SITES[site], "added": 0, "error": None}
        since = rules.sync_since(_seconds(account["last_synced"]), now)
        known = {row["link"] for row in conn.execute("SELECT link FROM problems WHERE link LIKE ?",
                                                     (f"%{site}.%",))}
        try:
            submissions, ratings = remote.sync(site, account["username"], since, known)
        except remote.RequestFailed as error:
            result["error"], result["source"] = error.kind, error.site
            results.append(result)
            continue
        result["added"] = _store(conn, site, account["username"], submissions, ratings, now, local_date)
        results.append(result)
    return results


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


def rating_history(conn):
    """Stored ratings for each linked account, oldest first. Shown only; never scored (R-34)."""
    out = {}
    for site, account in accounts(conn).items():
        out[site] = [dict(r) for r in conn.execute(
            "SELECT contest, date, rating FROM rating_history WHERE site = ? AND username = ? ORDER BY date, rowid",
            (site, account["username"]))]
    return out
