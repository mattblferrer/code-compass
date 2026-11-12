// Sync progress (R-33). Sync now starts the sync in the background, and this shows
// what each site has read so far: a bar (filled as far as can be told, or sweeping
// while the total is unknown), the submissions read, and how far back they reach.
// When the sync ends the page reloads to show the results. Without JavaScript the
// sync runs within the request and the page shows the results when it ends.
(function () {
  var panel = document.getElementById("sync-progress");
  var form = document.getElementById("sync-form");
  if (!panel || !form || !window.fetch) return;
  var list = panel.querySelector(".sync-progress-sites");
  var status = document.getElementById("sync-status");
  var button = form.querySelector("button");
  var rows = {};
  var lastStatus = "";
  var failures = 0;

  function csrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : "";
  }

  function month(seconds) {
    return new Date(seconds * 1000).toLocaleDateString(undefined, { year: "numeric", month: "short" });
  }

  function count(n) {
    return n.toLocaleString() + (n === 1 ? " submission" : " submissions");
  }

  // What a site's row says, from what it has read so far.
  function detail(s) {
    if (s.state === "waiting") return "Waiting for its turn";
    if (s.turn) return count(s.read) + " read. Waiting for " + s.label + "'s turn; other syncs are using it";
    if (s.state === "error") return "Stopped; the reason shows when the sync ends";
    if (s.state === "done") {
      return count(s.read) + " read. " + (s.added ? s.added + " new to confirm" : "Nothing new");
    }
    if (s.step === "ratings" && !s.read) return "Reading the rating history";
    if (s.step === "saving") return count(s.read) + " read. Saving";
    if (s.step === "details") return count(s.read) + " read. Looking up titles and levels of new problems";
    if (s.site === "leetcode") return "Reading the recent submissions LeetCode shows";
    if (!s.read) return "Asking " + s.label + " for submissions";
    var reach = s.site === "codeforces" ? ", back to " + month(s.oldest) : ", through " + month(s.newest);
    return count(s.read) + " read" + reach;
  }

  function row(s) {
    if (rows[s.site]) return rows[s.site];
    var li = document.createElement("li");
    var name = document.createElement("strong");
    name.textContent = s.label;
    var bar = document.createElement("progress");
    bar.max = 1;
    bar.setAttribute("aria-label", s.label + " sync");
    var text = document.createElement("span");
    text.className = "detail";
    li.appendChild(name);
    li.appendChild(bar);
    li.appendChild(text);
    list.appendChild(li);
    rows[s.site] = { li: li, bar: bar, text: text };
    return rows[s.site];
  }

  function draw(progress) {
    panel.hidden = false;
    button.disabled = true;
    button.textContent = "Syncing…";
    var active = null, finished = 0;
    progress.sites.forEach(function (s) {
      var r = row(s);
      r.li.className = s.state;
      r.text.textContent = detail(s);
      if (s.state === "done") r.bar.value = 1;
      else if (s.state === "error" || s.state === "waiting") r.bar.value = 0;
      else if (s.fraction === null || s.fraction === undefined) r.bar.removeAttribute("value");  // Total unknown.
      else r.bar.value = s.fraction;
      if (s.state === "running" && !active) active = s;
      if (s.state === "done" || s.state === "error") finished++;
    });
    // Announced only as each site starts or ends, not at every page read.
    var line = progress.done ? "Sync finished." :
      "Syncing " + (active ? active.label : "") + " (" + (finished + 1) + " of " + progress.sites.length + ").";
    if (line !== lastStatus) status.textContent = lastStatus = line;
  }

  // In hosted mode each poll also runs the sync a step further (R-54).
  var stepUrl = panel.getAttribute("data-step-url");

  function poll() {
    var ask = stepUrl ?
      fetch(stepUrl, { method: "POST", headers: { "Accept": "application/json", "X-CSRF-Token": csrfToken() } }) :
      fetch(panel.getAttribute("data-progress-url"), { headers: { "Accept": "application/json" } });
    ask
      .then(function (r) { if (!r.ok) throw new Error(); return r.json(); })
      .then(function (progress) {
        failures = 0;
        draw(progress);
        if (progress.done) {
          setTimeout(function () { location.href = panel.getAttribute("data-page-url"); }, 600);
        } else {
          setTimeout(poll, 500);
        }
      })
      .catch(function () {
        // The app may be busy for a moment; keep asking, more slowly.
        failures++;
        setTimeout(poll, Math.min(5000, 500 * Math.pow(2, failures)));
      });
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    button.disabled = true;
    fetch(form.action, { method: "POST", headers: { "X-Sync-Background": "1", "Accept": "application/json",
                                                   "X-CSRF-Token": csrfToken() } })
      .then(function (r) { if (r.status !== 202) throw new Error(); return r.json(); })
      .then(function (progress) { draw(progress); setTimeout(poll, 400); })
      .catch(function () { form.submit(); });  // Fall back to syncing within the request.
  });

  // Opened while a sync is running: carry on showing it.
  var running = panel.getAttribute("data-progress");
  if (running) {
    try { draw(JSON.parse(running)); } catch (e) { /* The next poll draws it. */ }
    poll();
  }
})();
