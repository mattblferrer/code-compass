// A problem's note saves as it is typed (R-45): a moment after typing stops, the note is
// sent in the background, one save at a time. Without JavaScript, Save note posts it.
(function () {
  var form = document.getElementById("note-form");
  var status = document.getElementById("note-status");
  if (!form || !status || !window.fetch) return;
  var button = form.querySelector('button[type="submit"]');
  var timer = null, saving = false, again = false;

  function save() {
    if (saving) { again = true; return; }
    saving = true;
    again = false;
    status.textContent = "Saving…";
    fetch(form.action, { method: "POST", body: new FormData(form), keepalive: true,
                         headers: { "X-Autosave": "1", "Accept": "application/json" } })
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

  form.querySelector("textarea").addEventListener("input", function () {
    clearTimeout(timer);
    status.textContent = "";
    timer = setTimeout(save, 700);
  });
  form.addEventListener("submit", function (event) { event.preventDefault(); clearTimeout(timer); save(); });
  button.hidden = true;
})();
