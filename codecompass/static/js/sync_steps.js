// Hosted mode (R-54): nothing runs on the host between requests, so while the account's sync
// runs, every CodeCompass page asks for it to run a step further, about once a second. The
// sync page shows its progress itself; here the steps run quietly until the sync ends, and the
// sync page shows the results on the next visit. Closing every page pauses the sync.
(function () {
  var script = document.currentScript;
  var url = script && script.getAttribute("data-step-url");
  if (!url || !window.fetch) return;
  var meta = document.querySelector('meta[name="csrf-token"]');
  var failures = 0;

  function step() {
    fetch(url, { method: "POST", headers: { "Accept": "application/json", "X-CSRF-Token": meta ? meta.content : "" } })
      .then(function (r) { if (!r.ok) throw new Error(); return r.json(); })
      .then(function (progress) {
        failures = 0;
        if (!progress.done) setTimeout(step, 1000);
      })
      .catch(function () {
        failures++;
        if (failures < 6) setTimeout(step, 1000 * Math.pow(2, failures));
      });
  }

  setTimeout(step, 500);
})();
