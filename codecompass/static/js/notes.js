// A problem's note saves as it is typed (R-45): a moment after typing stops, the note is
// sent in the background, one save at a time. Leaving the page sends any edit still
// waiting. Without JavaScript, Save note posts it.
(function () {
  var form = document.getElementById("note-form");
  var status = document.getElementById("note-status");
  if (!form || !status || !window.fetch) return;
  var button = form.querySelector('button[type="submit"]');
  var area = form.querySelector("textarea");
  var timer = null, saving = false, again = false, waiting = false;
  // Browsers send a request that outlives the page only up to 64 KB.
  var KEEPALIVE_LIMIT = 60000;

  function send(leaving) {
    var body = new FormData(form);
    var small = new Blob([area.value]).size < KEEPALIVE_LIMIT;
    return fetch(form.action, { method: "POST", body: body, keepalive: leaving && small,
                                headers: { "X-Autosave": "1", "Accept": "application/json" } });
  }

  function save() {
    waiting = false;
    if (saving) { again = true; return; }
    saving = true;
    again = false;
    status.textContent = "Saving…";
    send(false)
      .then(function (r) { return r.json().then(function (body) { if (!r.ok || !body.saved) throw body; }); })
      .then(function () {
        saving = false;
        if (again) return save();
        status.textContent = "Saved";
      })
      .catch(function (body) {
        saving = false;
        status.textContent = (body && body.error) || "Not saved. Check that CodeCompass is still running.";
        button.hidden = false;
      });
  }

  area.addEventListener("input", function () {
    clearTimeout(timer);
    waiting = true;
    status.textContent = "";
    timer = setTimeout(save, 700);
  });
  form.addEventListener("submit", function (event) { event.preventDefault(); clearTimeout(timer); save(); });
  // Leaving within a moment of typing: send the edit now, so it is not lost.
  function flush() {
    if (!waiting) return;
    clearTimeout(timer);
    waiting = false;
    send(true).catch(function () {});
  }
  window.addEventListener("pagehide", flush);
  document.addEventListener("visibilitychange", function () { if (document.visibilityState === "hidden") flush(); });
  button.hidden = true;
})();
