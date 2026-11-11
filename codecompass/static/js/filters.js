// Filter bars on History and Sync: each change applies at once, so the Apply button is
// only needed without JavaScript. Filters live in the page's address, so a reload or a
// bookmark keeps them. On a phone the bar folds behind its Filters button unless a
// filter is on; on a wider screen it is always open.
(function () {
  var narrow = window.matchMedia ? window.matchMedia("(max-width: 40rem)") : null;
  document.querySelectorAll("details.filter-fold").forEach(function (fold) {
    var active = fold.getAttribute("data-active") !== "0";
    function fit() {
      if (!narrow || !narrow.matches) fold.open = true;
    }
    if (narrow && narrow.matches && !active) fold.open = false;
    // Turning a phone sideways, or widening a window, opens it again.
    if (narrow && narrow.addEventListener) narrow.addEventListener("change", fit);
  });

  document.querySelectorAll("form.filters").forEach(function (form) {
    var apply = form.querySelector('.filter-actions button[type="submit"]');
    if (apply) apply.hidden = true;
    form.addEventListener("change", function () {
      // Leave out empty fields, so the address shows only the filters in use.
      Array.prototype.forEach.call(form.elements, function (el) {
        if (el.name && !el.value && el.type !== "checkbox") el.disabled = true;
      });
      form.submit();
    });
    // Coming back to this page from the browser's history restores it as it was left,
    // with those fields still switched off; switch them on again.
    window.addEventListener("pageshow", function () {
      Array.prototype.forEach.call(form.elements, function (el) { el.disabled = false; });
    });
  });
})();
