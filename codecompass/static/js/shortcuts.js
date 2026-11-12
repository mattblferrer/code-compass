// Keyboard shortcuts (R-47): / searches for a problem to log, L opens the log form, 1 to 4
// pick an outcome and S saves on the log form, and ? lists them. They never act while
// the user types in a field, or with Ctrl, Alt, or Cmd held, so typing and the
// browser's own shortcuts are unaffected.
(function () {
  var help = document.getElementById("shortcuts");
  if (!help) return;
  var logUrl = help.getAttribute("data-log-url");
  var OUTCOMES = { "1": "solved_alone", "2": "solved_with_hints", "3": "solved_after_solution", "4": "not_solved" };

  function typing(el) {
    if (!el) return false;
    var tag = el.tagName;
    return el.isContentEditable || tag === "TEXTAREA" || tag === "SELECT" ||
      (tag === "INPUT" && !/^(checkbox|radio|button|submit|reset|range|color)$/i.test(el.type));
  }

  // Arriving at the log form from "/" elsewhere: start in the search box.
  if (location.hash === "#search") {
    var box = document.getElementById("problem-search");
    if (box) box.focus();
  }

  document.addEventListener("keydown", function (event) {
    if (event.ctrlKey || event.altKey || event.metaKey || event.defaultPrevented) return;
    if (help.open) return;  // The open sheet handles Escape itself.
    if (typing(document.activeElement)) return;
    var key = event.key;
    var form = document.getElementById("attempt-form");
    var search = document.getElementById("problem-search");
    if (key === "?") {
      if (typeof help.showModal === "function") help.showModal();
    } else if (key === "/") {
      if (search) search.focus();
      else location.href = logUrl + "#search";
    } else if (key === "l" || key === "L") {
      if (search) search.focus();
      else location.href = logUrl;
    } else if (form && OUTCOMES[key]) {
      var choice = form.querySelector('input[name="outcome"][value="' + OUTCOMES[key] + '"]');
      if (!choice || choice.disabled) return;
      choice.checked = true;
      choice.dispatchEvent(new Event("change", { bubbles: true }));
      choice.focus();
    } else if (form && (key === "s" || key === "S")) {
      form.requestSubmit();
    } else {
      return;
    }
    event.preventDefault();
  });
})();
