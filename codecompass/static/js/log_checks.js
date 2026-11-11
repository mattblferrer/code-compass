// Checks on the log form as each field is left, with the server's own messages
// (R-05), so a mistake shows where it is made rather than after saving. The server
// still checks everything on save; without JavaScript, only that check runs.
(function () {
  var form = document.getElementById("attempt-form");
  if (!form) return;
  var messages = {};
  try { messages = JSON.parse(form.getAttribute("data-messages")); } catch (e) { return; }

  var search = document.getElementById("problem-search");
  var chosen = document.getElementById("problem-id");
  var picker = form.querySelector("fieldset.picker");
  var date = form.querySelector('input[name="date"]');
  var minutes = document.getElementById("time-minutes");
  var outcomes = form.querySelectorAll('input[name="outcome"]');
  var outcomeSet = outcomes.length ? outcomes[0].closest("fieldset") : null;

  // Show or clear one field's message, in the same place and form the server uses.
  function report(field, target, holder, message) {
    var id = field + "-error";
    var note = document.getElementById(id);
    if (!message) {
      if (note) note.remove();
      if (target) {
        target.removeAttribute("aria-invalid");
        var rest = (target.getAttribute("aria-describedby") || "").split(" ").filter(function (x) { return x && x !== id; });
        if (rest.length) target.setAttribute("aria-describedby", rest.join(" "));
        else target.removeAttribute("aria-describedby");
      }
      return true;
    }
    if (!note) {
      note = document.createElement("small");
      note.className = "field-error";
      note.id = id;
      holder.appendChild(note);
    }
    note.textContent = message;
    if (target) {
      target.setAttribute("aria-invalid", "true");
      var ids = (target.getAttribute("aria-describedby") || "").split(" ").filter(Boolean);
      if (ids.indexOf(id) < 0) ids.push(id);
      target.setAttribute("aria-describedby", ids.join(" "));
    }
    return false;
  }

  // Each check follows validate_attempt (core/validation.py) exactly, so it never stops a
  // save the server would accept. An empty date is fine: the server takes it as today.
  function checkDate() {
    var value = date.value;
    if (!value) return report("date", date, date.closest("label"), null);
    var max = date.getAttribute("max");
    return report("date", date, date.closest("label"), max && value > max ? messages.date_future : null);
  }

  // Minutes are read as the server reads them, with Python's float(): "5", "5.", "1e1",
  // and "1_0" all count, and the number must be positive and finite.
  function checkTime() {
    var text = minutes.value.trim();
    var n = Number(text.replace(/(\d)_(?=\d)/g, "$1"));
    var ok = !text || (isFinite(n) && n > 0);
    return report("time", minutes, minutes.closest("label"), ok ? null : messages.time);
  }

  function checkOutcome() {
    var picked = Array.prototype.some.call(outcomes, function (o) { return o.checked; });
    return report("outcome", outcomes[0], outcomeSet, picked ? null : messages.outcome);
  }

  // A typed title the picker did not match: ask the same search the list uses whether
  // exactly one problem has that title or label, as saving would.
  var pending = 0;
  function checkProblem() {
    var text = search.value.trim();
    var ticket = ++pending;
    if (!text || chosen.value || /^https?:\/\/|\.\w+\//i.test(text)) {
      report("problem", search, picker, null);
      return;
    }
    fetch(form.getAttribute("data-search-url") + "?q=" + encodeURIComponent(text), { headers: { "Accept": "application/json" } })
      .then(function (r) { if (!r.ok) throw new Error(); return r.json(); })
      .then(function (results) {
        if (ticket !== pending || chosen.value) return;
        var lower = text.toLowerCase();
        var byLabel = results.filter(function (r) { return r.label.toLowerCase() === lower; });
        var byTitle = results.filter(function (r) { return r.label.toLowerCase().indexOf(lower + " (") === 0; });
        var message = null;
        if (!byLabel.length && byTitle.length > 1) message = messages.ambiguous;
        else if (!byLabel.length && !byTitle.length) message = messages.unknown;
        report("problem", search, picker, message);
      })
      .catch(function () { /* The check on save still runs. */ });
  }

  date.addEventListener("change", checkDate);
  date.addEventListener("blur", checkDate);
  minutes.addEventListener("blur", checkTime);
  minutes.addEventListener("input", function () { if (document.getElementById("time-error")) checkTime(); });
  outcomes.forEach(function (o) { o.addEventListener("change", checkOutcome); });
  // Wait a moment after leaving the search box, since picking from its list also leaves it.
  search.addEventListener("blur", function () { setTimeout(checkProblem, 250); });
  picker.addEventListener("problem-change", function () { report("problem", search, picker, null); });

  // On save, check the fields that can be checked here, and stay on the first problem.
  form.addEventListener("submit", function (event) {
    var fine = [checkDate(), checkTime(), checkOutcome()];
    if (fine.indexOf(false) >= 0) {
      event.preventDefault();
      var first = form.querySelector('[aria-invalid="true"]');
      if (first) first.focus();
    }
  });

  // After a save the server refused, start at the first field it marked.
  var marked = form.querySelector('[aria-invalid="true"]');
  if (marked) marked.focus();
})();
