// Settings save as they are changed: recommendations, sites, and pattern goals (R-13,
// R-32, R-36, R-41). Each change sends the whole form in the background, one save at a
// time; a change made during a save is sent once it ends. If a save fails, the Save
// settings button comes back. Linked accounts and Delete all data keep their own
// buttons. Without JavaScript, Save settings posts the form as before.
(function () {
  var form = document.getElementById("settings-form");
  var status = document.getElementById("autosave-status");
  if (!form || !status || !window.fetch || !window.FormData) return;
  var fallback = form.querySelector(".settings-save");
  var saving = false, again = false;

  function say(text, problem) {
    status.textContent = text;
    status.classList.toggle("problem", !!problem);
    status.hidden = false;
  }

  function save() {
    if (saving) { again = true; return; }
    saving = true;
    again = false;
    say("Saving…");
    fetch(form.getAttribute("action") || location.pathname, {
      method: "POST",
      body: new FormData(form),
      headers: { "X-Autosave": "1", "Accept": "application/json" },
      keepalive: true,  // A save started just before leaving the page still finishes.
    })
      .then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (body) {
          if (!r.ok || !body.saved) throw new Error();
        });
      })
      .then(function () {
        saving = false;
        if (again) return save();
        say("All changes saved");
      })
      .catch(function () {
        saving = false;
        say("Not saved. Check that CodeCompass is still running, then save.", true);
        if (fallback) fallback.hidden = false;
      });
  }

  form.addEventListener("change", save);
  // Typing in a field and pressing Enter would post the form and reload; save in place instead.
  form.addEventListener("submit", function (event) { event.preventDefault(); save(); });
  if (fallback) fallback.hidden = true;
  say("Changes save as you make them");
})();
