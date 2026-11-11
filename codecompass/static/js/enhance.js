// Submit forms marked with data-swap in the background and replace only the
// listed parts of the page, so buttons like "Not now" don't reload it.
// Without JavaScript, or if a request fails, the form submits normally.
(function () {
  // Remember whether each revealed hint is shown or hidden, for this browser session.
  function hintKey(details) {
    return "codecompass-hint-" + details.getAttribute("data-hint-id");
  }

  function restoreHints(root) {
    root.querySelectorAll("details[data-hint-id]").forEach(function (details) {
      try {
        if (sessionStorage.getItem(hintKey(details)) === "hidden") details.open = false;
      } catch (e) { /* Storage may be unavailable; the hint just stays open. */ }
    });
  }

  document.addEventListener("toggle", function (event) {
    var details = event.target;
    if (!details.matches || !details.matches("details[data-hint-id]")) return;
    try {
      sessionStorage.setItem(hintKey(details), details.open ? "shown" : "hidden");
    } catch (e) { /* Ignore. */ }
  }, true);

  restoreHints(document);

  if (!window.fetch || !window.DOMParser) return;

  document.addEventListener("submit", function (event) {
    var form = event.target;
    var targets = form.getAttribute("data-swap");
    if (!targets || form.method.toLowerCase() !== "post") return;
    event.preventDefault();

    var buttons = form.querySelectorAll("button");
    buttons.forEach(function (b) { b.disabled = true; });

    fetch(form.action, {
      method: "POST",
      body: new FormData(form),
      credentials: "same-origin",
      headers: { "Accept": "text/html" },
    })
      .then(function (response) {
        if (!response.ok) throw new Error("Request failed");
        return response.text();
      })
      .then(function (html) {
        var page = new DOMParser().parseFromString(html, "text/html");
        targets.split(",").forEach(function (selector) {
          selector = selector.trim();
          var current = document.querySelector(selector);
          var replacement = page.querySelector(selector);
          if (!current || !replacement) return;
          if (current.hasAttribute("aria-live")) {
            // Keep the live region itself, so screen readers announce the new message.
            current.innerHTML = replacement.innerHTML;
          } else {
            current.replaceWith(replacement);
            restoreHints(replacement);
          }
        });
      })
      .catch(function () {
        buttons.forEach(function (b) { b.disabled = false; });
        form.removeAttribute("data-swap");
        form.submit();
      });
  });
})();

// Popovers and sheets built on <details class="dismissable"> (the More sheet, the
// "Had external help" menu) close on Escape or a click outside them, so only one is
// open at a time. Without JavaScript they still open and close from their button.
(function () {
  function openOnes() {
    return document.querySelectorAll("details.dismissable[open]");
  }

  document.addEventListener("click", function (event) {
    openOnes().forEach(function (details) {
      if (!details.contains(event.target)) details.open = false;
    });
  });

  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") return;
    openOnes().forEach(function (details) {
      var hadFocus = details.contains(document.activeElement);
      details.open = false;
      var summary = details.querySelector("summary");
      if (hadFocus && summary) summary.focus();
    });
  });
})();
