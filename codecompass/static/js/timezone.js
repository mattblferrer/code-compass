// Hosted mode: the server's clock is in UTC, so the browser says its offset from UTC, and dates
// (today, a synced submission's day) follow the user's own day. Local mode uses the computer's.
try {
  document.cookie = "tz=" + (-new Date().getTimezoneOffset()) + "; path=/; max-age=31536000; samesite=lax" +
    (location.protocol === "https:" ? "; secure" : "");
} catch (e) { /* Without it, dates follow UTC. */ }
