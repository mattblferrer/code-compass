// The cards beside the log form. When a problem is chosen in the picker, the
// "This problem" card is fetched from this app and swapped in; a problem in the
// "Practice next" card fills in the form. Without JavaScript, those links open the
// log page with the problem chosen, and the card is drawn with the page.
(function () {
  var box = document.querySelector("fieldset.picker");
  var card = document.getElementById("log-context");
  if (!box || !card || !window.fetch) return;

  var url = card.getAttribute("data-url");
  var editing = card.hasAttribute("data-editing");
  var empty = document.getElementById("log-context-empty");
  var current = card.getAttribute("data-problem-id") || "";
  var latest = 0;

  function changed() {
    card.classList.remove("changed");
    void card.offsetWidth;  // Restart the highlight.
    card.classList.add("changed");
  }

  function show(id) {
    id = id ? String(id) : "";
    if (id === current) return;
    current = id;
    var ticket = ++latest;
    if (!id) {
      if (empty) card.innerHTML = empty.innerHTML;
      return;
    }
    fetch(url.replace("/0/", "/" + encodeURIComponent(id) + "/") + (editing ? "?editing=1" : ""),
          { headers: { "Accept": "text/html" } })
      .then(function (r) { if (!r.ok) throw new Error(); return r.text(); })
      .then(function (html) {
        if (ticket !== latest) return;  // A later choice has replaced this one.
        card.innerHTML = html;
        changed();
      })
      .catch(function () { /* Keep the card as it was; the form still works. */ });
  }

  // Mark the chosen problem in the "Practice next" card, if it is there.
  function mark(id) {
    document.querySelectorAll("[data-pick-id]").forEach(function (link) {
      if (id && link.getAttribute("data-pick-id") === String(id)) link.setAttribute("aria-current", "true");
      else link.removeAttribute("aria-current");
    });
  }

  box.addEventListener("problem-change", function (event) {
    mark(event.detail.id);
    show(event.detail.id);
  });
  mark(current);

  document.addEventListener("click", function (event) {
    var link = event.target.closest && event.target.closest("[data-pick-id]");
    if (!link || event.ctrlKey || event.metaKey || event.shiftKey) return;
    event.preventDefault();
    box.dispatchEvent(new CustomEvent("pick-problem", {
      detail: { id: link.getAttribute("data-pick-id"), label: link.getAttribute("data-pick-label") }
    }));
    // The next thing to fill in is how it went.
    var outcome = document.querySelector('input[name="outcome"]');
    if (outcome) outcome.focus({ preventScroll: true });
    var still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    box.scrollIntoView({ block: "nearest", behavior: still ? "auto" : "smooth" });
  });
})();
