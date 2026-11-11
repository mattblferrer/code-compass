// Problem picker on the logging form (R-38). Without JavaScript the form still
// works: the server matches the typed title, or the site and ID, on save.
// The requests below go only to this app, which reads its own database.
(function () {
  var box = document.querySelector("fieldset.picker");
  if (!box || !window.fetch) return;

  var input = document.getElementById("problem-search");
  var list = document.getElementById("problem-results");
  var hidden = document.getElementById("problem-id");
  var site = document.getElementById("problem-site");
  var ref = document.getElementById("problem-ref");
  var hint = document.getElementById("problem-ref-hint");
  var status = document.getElementById("problem-status");
  var hints = {};
  try { hints = JSON.parse(box.getAttribute("data-hints")); } catch (e) { /* Keep the default hint. */ }

  var results = [];
  var active = -1;
  var timer = null;
  var latest = 0;

  function levelClass(level) {
    return "mark level-" + level.replace(" ", "-");
  }

  // A title picked from the list replaces any site and ID typed earlier,
  // because the server uses the ID when one is filled in.
  function chooseFromList(item) {
    choose(item);
    ref.value = "";
    if (site.value === "other") {
      site.value = "";
      updateHint();
    }
    setStatus("");
  }

  function close() {
    list.hidden = true;
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
    active = -1;
  }

  function choose(item) {
    input.value = item.label;
    hidden.value = item.id;
    close();
  }

  function highlight(index) {
    var options = list.querySelectorAll("[role=option]");
    options.forEach(function (o, i) { o.setAttribute("aria-selected", i === index ? "true" : "false"); });
    active = index;
    if (options[index]) {
      input.setAttribute("aria-activedescendant", options[index].id);
      options[index].scrollIntoView({ block: "nearest" });
    }
  }

  function render(items) {
    results = items;
    list.innerHTML = "";
    if (!items.length) {
      var empty = document.createElement("li");
      empty.className = "picker-empty";
      empty.textContent = "No matches. Try finding it by site and ID below.";
      list.appendChild(empty);
    }
    items.forEach(function (item, i) {
      var li = document.createElement("li");
      li.id = "problem-option-" + i;
      li.setAttribute("role", "option");
      li.setAttribute("aria-selected", "false");
      var name = document.createElement("span");
      name.textContent = item.label;
      var level = document.createElement("span");
      level.className = levelClass(item.difficulty);
      level.textContent = item.difficulty;
      li.appendChild(name);
      li.appendChild(level);
      if (item.reserve) {
        var tag = document.createElement("small");
        tag.textContent = "unreviewed";
        li.appendChild(tag);
      }
      // mousedown fires before the input loses focus, so the list is still there.
      li.addEventListener("mousedown", function (event) {
        event.preventDefault();
        chooseFromList(item);
      });
      list.appendChild(li);
    });
    list.hidden = false;
    input.setAttribute("aria-expanded", "true");
    active = -1;
  }

  function search() {
    var text = input.value.trim();
    if (text.length < 2) { close(); return; }
    var ticket = ++latest;
    fetch(box.getAttribute("data-search-url") + "?q=" + encodeURIComponent(text), { headers: { "Accept": "application/json" } })
      .then(function (r) { if (!r.ok) throw new Error(); return r.json(); })
      .then(function (items) { if (ticket === latest) render(items); })
      .catch(close);
  }

  input.addEventListener("input", function () {
    hidden.value = "";
    clearTimeout(timer);
    timer = setTimeout(search, 150);
  });

  input.addEventListener("keydown", function (event) {
    if (list.hidden || !results.length) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      highlight(Math.min(active + 1, results.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      highlight(Math.max(active - 1, 0));
    } else if (event.key === "Enter" && active >= 0) {
      event.preventDefault();
      chooseFromList(results[active]);
    } else if (event.key === "Escape") {
      close();
    }
  });

  input.addEventListener("blur", close);

  // --- Site and ID ---

  function setStatus(text, link) {
    status.textContent = text || "";
    if (link) {
      var a = document.createElement("a");
      a.href = link;
      a.textContent = "Add it as a custom problem";
      status.appendChild(document.createTextNode(" "));
      status.appendChild(a);
      status.appendChild(document.createTextNode("."));
    }
  }

  function updateHint() {
    var other = site.value === "other";
    ref.disabled = other;
    hint.textContent = other ? "Problems from other sites are added as custom problems."
      : (hints[site.value] ? "Enter " + hints[site.value] + ", or paste the link." : "Choose a site first, or paste a link.");
  }

  function find() {
    var text = ref.value.trim();
    if (site.value !== "other" && !text) { setStatus(""); return; }
    var url = box.getAttribute("data-find-url") + "?site=" + encodeURIComponent(site.value) + "&ref=" + encodeURIComponent(text);
    fetch(url, { headers: { "Accept": "application/json" } })
      .then(function (r) { if (!r.ok) throw new Error(); return r.json(); })
      .then(function (data) {
        if (data.problem) {
          choose(data.problem);
          setStatus("Found: " + data.problem.label + ".");
        } else {
          // Clear any problem found earlier, so the title shown matches what will be saved.
          input.value = "";
          hidden.value = "";
          setStatus(data.message, data.custom_url);
        }
      })
      .catch(function () { setStatus(""); });
  }

  site.addEventListener("change", function () { updateHint(); find(); });
  ref.addEventListener("change", find);
  updateHint();
})();
