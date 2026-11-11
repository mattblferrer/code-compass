// Filter bars on History and Sync: each change applies at once, so the Apply button is
// only needed without JavaScript. Filters live in the page's address, so a reload or a
// bookmark keeps them.
(function () {
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
