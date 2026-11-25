// Company presets (R-60) on the interview form. The Company field searches the presets as you
// type, like the problem picker (R-38), though any name can still be typed. The fill button
// follows the company typed and fills in its patterns in place, checking exactly those and
// unchecking the rest; nothing is saved. A company with too few problems for its own preset
// fills in the most common patterns across companies (data.general) instead. Without
// JavaScript, the field is a plain text field and the fill button sends the form back with the
// patterns checked instead.
// Everything here works from the page's own data; nothing is requested.
(function () {
  var MAX_RESULTS = 8;

  function shares(patterns) {
    return patterns.map(function (p) { return p[0] + " " + p[1] + "%"; }).join(", ");
  }

  function problemCount(n) {
    return n.toLocaleString("en-US") + (n === 1 ? " problem" : " problems");
  }

  // The same text as the template's preset_detail.
  function detailText(preset, general) {
    if (preset.general) {
      return preset.company + " has only " + problemCount(preset.problems) +
        " in LeetCode's company tags, too few for its own preset. These are the most common patterns across the " +
        general.companies + " companies that have one: " + shares(general.patterns) +
        ". Snapshot of " + general.snapshot + ".";
    }
    return shares(preset.patterns) + ". From LeetCode's company tags: " + problemCount(preset.problems) +
      ", snapshot of " + preset.snapshot + ".";
  }

  document.querySelectorAll(".company-preset[data-presets]").forEach(function (box) {
    var data;
    try {
      data = JSON.parse(box.getAttribute("data-presets"));
    } catch (e) {
      return; // The button still works by sending the form.
    }
    var form = box.closest("form");
    var input = form && form.querySelector('input[name="company"]');
    var list = form && form.querySelector("#company-results");
    var button = box.querySelector("[data-preset-fill]");
    var detail = box.querySelector("[data-preset-detail]");
    var notice = box.querySelector("[data-preset-notice]");
    if (!input || !button || !detail || !notice) return;
    button.type = "button";

    // The other names each preset is found by, for the search list.
    var aliases = data.presets.map(function () { return []; });
    Object.keys(data.names).forEach(function (name) {
      var preset = data.presets[data.names[name]];
      if (name !== preset.company.toLowerCase()) aliases[data.names[name]].push(name);
    });

    function current() {
      var index = data.names[input.value.trim().toLowerCase()];
      return index === undefined ? null : data.presets[index];
    }

    function patternsOf(preset) {
      return (preset.general ? data.general.patterns : preset.patterns).map(function (p) { return p[0]; });
    }

    function update() {
      var preset = current();
      button.hidden = detail.hidden = !preset;
      if (!preset) return;
      button.textContent = preset.general ? "Fill in the most common patterns" : "Fill in patterns for " + preset.company;
      detail.textContent = detailText(preset, data.general);
    }

    // --- The search list ---

    var results = [];
    var active = -1;

    // Presets whose name, or another name, starts with the text first, then those containing it;
    // within each, the companies with the most problems first, so the best-known come first.
    function matches(text) {
      var starts = [], contains = [];
      data.presets.forEach(function (preset, i) {
        var names = [preset.company.toLowerCase()].concat(aliases[i]);
        var hit = null;
        names.forEach(function (name, n) {
          var at = name.indexOf(text);
          if (at === -1) return;
          var found = { preset: preset, alias: n ? name : null, start: at === 0 };
          if (!hit || (found.start && !hit.start)) hit = found;
        });
        if (hit) (hit.start ? starts : contains).push(hit);
      });
      function byProblems(a, b) { return b.preset.problems - a.preset.problems; }
      // Array.prototype.sort is stable, so ties stay in name order.
      return starts.sort(byProblems).concat(contains.sort(byProblems)).slice(0, MAX_RESULTS);
    }

    function close() {
      if (!list) return;
      list.hidden = true;
      input.setAttribute("aria-expanded", "false");
      input.removeAttribute("aria-activedescendant");
      active = -1;
    }

    function choose(item) {
      input.value = item.preset.company;
      close();
      notice.textContent = "";
      update();
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

    function search() {
      if (!list) return;
      var text = input.value.trim().toLowerCase();
      var exact = current();
      results = text ? matches(text) : [];
      // Nothing to suggest, or the only suggestion is the company already typed.
      if (!results.length || (results.length === 1 && exact && results[0].preset === exact)) {
        close();
        return;
      }
      list.innerHTML = "";
      results.forEach(function (item, i) {
        var li = document.createElement("li");
        li.id = "company-option-" + i;
        li.setAttribute("role", "option");
        li.setAttribute("aria-selected", "false");
        var name = document.createElement("span");
        name.textContent = item.preset.company;
        li.appendChild(name);
        var note = document.createElement("small");
        // Other names are kept in lowercase for matching; shown with capitals, such as "also Facebook".
        var alias = item.alias && item.alias.replace(/(^|[\s.])([a-z])/g, function (m, before, letter) {
          return before + letter.toUpperCase();
        });
        note.textContent = alias ? "also " + alias : problemCount(item.preset.problems);
        li.appendChild(note);
        // mousedown fires before the field loses focus, so the list is still there.
        li.addEventListener("mousedown", function (event) {
          event.preventDefault();
          choose(item);
        });
        list.appendChild(li);
      });
      list.hidden = false;
      input.setAttribute("aria-expanded", "true");
      active = -1;
    }

    input.addEventListener("input", function () {
      notice.textContent = "";
      update();
      search();
    });

    input.addEventListener("keydown", function (event) {
      if (!list || list.hidden || !results.length) return;
      if (event.key === "ArrowDown") {
        event.preventDefault();
        highlight(Math.min(active + 1, results.length - 1));
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        highlight(Math.max(active - 1, 0));
      } else if (event.key === "Enter" && active >= 0) {
        event.preventDefault();
        choose(results[active]);
      } else if (event.key === "Escape") {
        close();
      }
    });

    input.addEventListener("blur", close);

    // --- Filling in ---

    button.addEventListener("click", function () {
      var preset = current();
      if (!preset) return;
      var names = patternsOf(preset);
      form.querySelectorAll('input[name="patterns"]').forEach(function (check) {
        check.checked = names.indexOf(check.value) !== -1;
      });
      var filled = preset.general ? "Filled in the most common patterns across companies" :
        "Filled in " + names.length + (names.length === 1 ? " pattern" : " patterns") + " for " + preset.company;
      notice.textContent = filled + ". Nothing is saved until you " + box.getAttribute("data-save-label") + ".";
    });

    update();
  });
})();
