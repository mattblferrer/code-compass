// Shared details card for the charts: the rating history, a pattern's score over time,
// and the History calendar. The card has a title, a muted line, and a value line (for
// the line charts, the change as old → new (+delta)). Each chart decides which point
// is chosen; the line charts also get a highlighted dot, the calendar its square.
window.ChartTip = (function () {
  var NS = "http://www.w3.org/2000/svg";
  var DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  // "2026-11-10" as "Tue 10 Nov 2026", as pages write dates in full.
  function dayLabel(text) {
    var p = text.split("-");
    var d = new Date(Date.UTC(+p[0], +p[1] - 1, +p[2]));
    return DAYS[d.getUTCDay()] + " " + d.getUTCDate() + " " + MONTHS[d.getUTCMonth()] + " " + d.getUTCFullYear();
  }

  // "1602 → 1764 (+162)", or just the value when there is nothing before it.
  function changeText(old, value, change) {
    if (old === null || old === undefined) return String(value);
    var sign = change > 0 ? "+" + change : change < 0 ? "−" + (-change) : "0";
    return old + " → " + value + " (" + sign + ")";
  }

  function card(container) {
    var tip = document.createElement("div");
    tip.className = "chart-tip";
    tip.hidden = true;
    tip.setAttribute("role", "status");
    container.appendChild(tip);
    return tip;
  }

  // `detail` is { title, note, value, old, change, prefix }; the value line is left out without a value.
  function fill(tip, detail) {
    tip.textContent = "";
    var title = document.createElement("strong");
    title.textContent = detail.title;
    tip.appendChild(title);
    if (detail.note) {
      var note = document.createElement("span");
      note.textContent = detail.note;
      tip.appendChild(note);
    }
    if (detail.value !== undefined && detail.value !== null && detail.value !== "") {
      var change = document.createElement("span");
      change.className = "tip-change" + (detail.change > 0 ? " up" : detail.change < 0 ? " down" : "");
      change.textContent = (detail.prefix || "") + changeText(detail.old, detail.value, detail.change);
      tip.appendChild(change);
    }
    tip.hidden = false;
  }

  // Beside the point at (px, py) within `container`, flipping to the left near the right edge.
  function place(tip, container, px, py, gap) {
    var width = container.getBoundingClientRect().width;
    var flip = px + gap + tip.offsetWidth + 4 > width;
    tip.style.left = Math.max(4, flip ? px - gap - tip.offsetWidth : px + gap) + "px";
    tip.style.top = Math.max(4, py - tip.offsetHeight / 2) + "px";
  }

  // For a line chart drawn in `svg`, whose viewBox is `width` by `height`.
  function create(figure, svg, width, height) {
    var tip = card(figure);
    var dot = null;
    svg.setAttribute("tabindex", "0");

    // The highlight is redrawn with the chart, so the chart asks for a new one after each render.
    function attach() {
      dot = document.createElementNS(NS, "circle");
      dot.setAttribute("class", "dot focus");
      dot.setAttribute("r", "5");
      dot.setAttribute("visibility", "hidden");
      svg.appendChild(dot);
    }

    function hide() {
      tip.hidden = true;
      if (dot) dot.setAttribute("visibility", "hidden");
    }

    function show(sx, sy, detail) {
      if (!dot || !dot.parentNode) attach();
      dot.setAttribute("cx", sx.toFixed(1));
      dot.setAttribute("cy", sy.toFixed(1));
      dot.setAttribute("visibility", "visible");
      fill(tip, detail);
      var box = svg.getBoundingClientRect(), outer = figure.getBoundingClientRect();
      place(tip, figure, box.left - outer.left + sx * box.width / width,
            box.top - outer.top + sy * box.height / height, 12);
    }

    // The point nearest the pointer across, within about a dot's spacing, or null.
    function nearest(clientX, points, xOf) {
      var rect = svg.getBoundingClientRect();
      var sx = (clientX - rect.left) * width / rect.width;
      var best = null, gap = 24;
      points.forEach(function (p) {
        var d = Math.abs(xOf(p) - sx);
        if (d < gap) { gap = d; best = p; }
      });
      return best;
    }

    // Left and right arrows step through `points` from `current`; returns the next one.
    function step(key, points, current) {
      if (!points.length) return null;
      var i = points.indexOf(current);
      if (i < 0) return key === "ArrowLeft" ? points[points.length - 1] : points[0];
      return points[Math.max(0, Math.min(points.length - 1, i + (key === "ArrowLeft" ? -1 : 1)))];
    }

    return { attach: attach, show: show, hide: hide, nearest: nearest, step: step };
  }

  // For a chart built from elements, such as the calendar's squares: the card sits
  // beside the element pointed at or focused, within `container`.
  function forCells(container) {
    var tip = card(container);
    var current = null;

    function hide() {
      tip.hidden = true;
      if (current) current.classList.remove("tipped");
      current = null;
    }

    function show(element, detail) {
      if (current && current !== element) current.classList.remove("tipped");
      current = element;
      element.classList.add("tipped");
      fill(tip, detail);
      // Right of the element, or left of it when there is no room on the right.
      var box = element.getBoundingClientRect(), outer = container.getBoundingClientRect();
      var right = box.right - outer.left + 8, left = box.left - outer.left - 8 - tip.offsetWidth;
      tip.style.left = Math.max(4, right + tip.offsetWidth + 4 > outer.width ? left : right) + "px";
      tip.style.top = Math.max(4, box.top - outer.top + box.height / 2 - tip.offsetHeight / 2) + "px";
    }

    return { show: show, hide: hide };
  }

  return { create: create, forCells: forCells, changeText: changeText, dayLabel: dayLabel };
})();
