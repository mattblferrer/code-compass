"""Limits on how often an account or address may do costly things in hosted mode (R-53).

Counts are kept in the shared rate_limits table, per key and fixed window, so they hold
across every copy of the app the host runs. Local mode has no limits.
"""
import random
import time


def allow(conn, key, limit, window):
    """Count one use of `key`. False once it has been used more than `limit` times in the
    current window of `window` seconds."""
    if not getattr(conn, "hosted", False):
        return True
    now = time.time()
    start = now - window
    with conn:
        count = conn.execute(
            """INSERT INTO rate_limits (key, window_start, count) VALUES (?, ?, 1)
               ON CONFLICT (key) DO UPDATE SET
                   count = CASE WHEN rate_limits.window_start <= ? THEN 1 ELSE rate_limits.count + 1 END,
                   window_start = CASE WHEN rate_limits.window_start <= ? THEN ? ELSE rate_limits.window_start END
               RETURNING count""", (key, now, start, start, now)).fetchone()[0]
        if random.random() < 0.01:  # Now and then, forget windows long past.
            conn.execute("DELETE FROM rate_limits WHERE window_start < ?", (now - 7 * 86400,))
    return count <= limit
