// Restoring a backup (R-46, R-55): compress the chosen file with gzip before the form sends it,
// so a larger backup still fits the host's upload limit. The server unpacks it (backup.unpack).
// Without CompressionStream or DataTransfer, or if anything fails, the file is sent as chosen.
(function () {
  if (typeof CompressionStream === "undefined" || typeof DataTransfer === "undefined") return;

  document.querySelectorAll("form.restore-form").forEach(function (form) {
    var ready = false;
    form.addEventListener("submit", function (event) {
      var button = event.submitter;
      if (ready || (button && button.getAttribute("formmethod") === "dialog")) return;  // Cancel, or already packed.
      var input = form.querySelector('input[type="file"]');
      var file = input && input.files[0];
      if (!file || /\.gz$/i.test(file.name)) return;
      event.preventDefault();
      if (button) button.disabled = true;
      new Response(file.stream().pipeThrough(new CompressionStream("gzip"))).blob()
        .then(function (packed) {
          var box = new DataTransfer();
          box.items.add(new File([packed], file.name + ".gz", { type: "application/gzip" }));
          input.files = box.files;
        })
        .catch(function () { /* Send the file as chosen. */ })
        .then(function () {
          ready = true;
          if (button) button.disabled = false;
          form.submit();
        });
    });
  });
})();
