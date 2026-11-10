// Rating history charts (R-34): each contest sits at its date, and the time axis
// can be zoomed and panned with the buttons, the mouse wheel, dragging, or pinching.
// The rating axis fits the contests in view. Without JavaScript, the server-drawn
// chart shows the whole history.
(function () {
  var NS = "http://www.w3.org/2000/svg";
  var DAY = 86400000;
  var MIN_SPAN = 14 * DAY;
  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  var W = 640, H = 220, LEFT = 48, RIGHT = 16, TOP = 14, BOTTOM = 34;
  var PLOT = W - LEFT - RIGHT;
  var count = 0;

  function make(name, attrs, parent, text) {
    var node = document.createElementNS(NS, name);
    Object.keys(attrs).forEach(function (key) { node.setAttribute(key, attrs[key]); });
    if (text !== undefined) node.textContent = text;
    if (parent) parent.appendChild(node);
    return node;
  }

  function parseDay(text) {
    var p = text.split("-");
    return Date.UTC(+p[0], +p[1] - 1, +p[2]);
  }

  function formatDay(t) {
    return new Date(t).toISOString().slice(0, 10);
  }

  function niceStep(span, parts) {
    var raw = Math.max(span / parts, 1);
    var mag = Math.pow(10, Math.floor(Math.log(raw) / Math.LN10));
    var n = raw / mag;
    return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * mag;
  }

  // Date ticks for the visible range: weeks, months, or years, at most about 6.
  function timeTicks(from, to) {
    var days = (to - from) / DAY;
    var steps = [[7, 0], [14, 0], [0, 1], [0, 2], [0, 3], [0, 6], [0, 12], [0, 24], [0, 60], [0, 120]];
    var step = steps[steps.length - 1];
    for (var i = 0; i < steps.length; i++) {
      var length = steps[i][0] || steps[i][1] * 30.44;
      if (days / length <= 6) { step = steps[i]; break; }
    }
    var ticks = [];
    if (step[0]) {
      for (var t = Math.ceil(from / (step[0] * DAY)) * step[0] * DAY; t <= to; t += step[0] * DAY) {
        var d = new Date(t);
        ticks.push({ t: t, label: MONTHS[d.getUTCMonth()] + " " + d.getUTCDate() });
      }
      return ticks;
    }
    var months = step[1];
    var start = new Date(from);
    var index = start.getUTCFullYear() * 12 + start.getUTCMonth();
    index = Math.ceil(index / months) * months;
    for (;; index += months) {
      var year = Math.floor(index / 12), month = index % 12;
      var at = Date.UTC(year, month, 1);
      if (at > to) break;
      if (at >= from) ticks.push({ t: at, label: months >= 12 ? String(year) : MONTHS[month] + " " + year });
    }
    return ticks;
  }

  function setup(figure) {
    var points = JSON.parse(figure.getAttribute("data-points")).map(function (p) {
      return { t: parseDay(p.date), date: p.date, rating: p.rating, contest: p.contest,
               old: p.old_rating, change: p.change };
    });
    var svg = figure.querySelector("svg");
    if (points.length < 2 || !svg) return;
    var label = figure.getAttribute("data-label") || "Rating";
    var first = points[0].t, last = points[points.length - 1].t;
    var pad = Math.max((last - first) * 0.02, 3 * DAY);
    var full = [first - pad, last + pad];
    var view = full.slice();
    var clipId = "rating-clip-" + (++count);

    var controls = document.createElement("div");
    controls.className = "chart-controls";
    controls.setAttribute("role", "group");
    controls.setAttribute("aria-label", label + " time range");
    function button(text, title, action) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "quiet small";
      b.textContent = text;
      b.title = title;
      b.addEventListener("click", action);
      controls.appendChild(b);
      return b;
    }
    var zoomIn = button("Zoom in", "Show a shorter time range", function () { zoom(0.5); });
    var zoomOut = button("Zoom out", "Show a longer time range", function () { zoom(2); });
    var earlier = button("Earlier", "Move the range earlier", function () { pan(-(view[1] - view[0]) / 2); });
    var later = button("Later", "Move the range later", function () { pan((view[1] - view[0]) / 2); });
    var all = button("Show all", "Show the whole history", function () { view = full.slice(); render(); });
    figure.insertBefore(controls, svg);
    var hint = document.createElement("small");
    hint.className = "chart-hint";
    hint.textContent = "Point at a contest for its details. Scroll over the chart to zoom, and drag to move. " +
      "With the chart focused, arrow keys step through contests and + and - zoom.";
    figure.insertBefore(hint, svg);
    var caption = figure.querySelector("figcaption span") || figure.appendChild(document.createElement("figcaption"));

    // Details for the contest under the pointer, or chosen with the arrow keys.
    var tip = document.createElement("div");
    tip.className = "chart-tip";
    tip.hidden = true;
    tip.setAttribute("role", "status");
    figure.appendChild(tip);
    var visible = [], yOf = null, focusDot = null, selected = null;
    svg.setAttribute("tabindex", "0");

    function clamp(from, to) {
      var span = Math.min(Math.max(to - from, MIN_SPAN), full[1] - full[0]);
      from = Math.max(full[0], Math.min(from, full[1] - span));
      return [from, from + span];
    }

    function zoom(factor, center) {
      if (center === undefined) center = (view[0] + view[1]) / 2;
      view = clamp(center - (center - view[0]) * factor, center + (view[1] - center) * factor);
      render();
    }

    function pan(dt) {
      view = clamp(view[0] + dt, view[1] + dt);
      render();
    }

    function x(t) { return LEFT + PLOT * (t - view[0]) / (view[1] - view[0]); }

    function timeAt(clientX) {
      var rect = svg.getBoundingClientRect();
      var sx = (clientX - rect.left) * W / rect.width;
      return view[0] + (sx - LEFT) / PLOT * (view[1] - view[0]);
    }

    function render() {
      while (svg.firstChild) svg.removeChild(svg.firstChild);
      // Contests in view, plus one on each side so the line runs to the edges.
      var a = 0, b = points.length - 1;
      while (a < points.length - 1 && points[a + 1].t < view[0]) a++;
      while (b > 0 && points[b - 1].t > view[1]) b--;
      var shown = points.slice(a, b + 1);
      var inView = shown.filter(function (p) { return p.t >= view[0] && p.t <= view[1]; });
      var basis = inView.length ? inView : shown;
      var lo = Math.min.apply(null, basis.map(function (p) { return p.rating; }));
      var hi = Math.max.apply(null, basis.map(function (p) { return p.rating; }));
      if (hi - lo < 40) { lo -= 20; hi += 20; }
      var step = niceStep(hi - lo, 4);
      var y0 = Math.floor(lo / step) * step, y1 = Math.ceil(hi / step) * step;
      function y(v) { return TOP + (H - TOP - BOTTOM) * (1 - (v - y0) / (y1 - y0)); }

      var clip = make("clipPath", { id: clipId }, make("defs", {}, svg));
      make("rect", { x: LEFT - 4, y: TOP - 4, width: PLOT + 8, height: H - TOP - BOTTOM + 8 }, clip);
      for (var v = y0; v <= y1 + step / 2; v += step) {
        make("line", { "class": "guide", x1: LEFT, x2: W - RIGHT, y1: y(v), y2: y(v) }, svg);
        make("text", { "class": "guide-label", x: LEFT - 6, y: y(v) + 4, "text-anchor": "end" }, svg, String(v));
      }
      timeTicks(view[0], view[1]).forEach(function (tick) {
        var tx = x(tick.t);
        make("line", { "class": "tick", x1: tx, x2: tx, y1: H - BOTTOM, y2: H - BOTTOM + 5 }, svg);
        make("text", { "class": "tick-label", x: tx, y: H - BOTTOM + 18, "text-anchor": "middle" }, svg, tick.label);
      });
      var plotted = make("g", { "clip-path": "url(#" + clipId + ")" }, svg);
      make("polyline", { "class": "line", points: shown.map(function (p) {
        return x(p.t).toFixed(1) + "," + y(p.rating).toFixed(1);
      }).join(" ") }, plotted);
      var radius = inView.length > 80 ? 1.8 : 3;  // Smaller dots keep a long history readable.
      inView.forEach(function (p) {
        make("circle", { "class": "dot", cx: x(p.t).toFixed(1), cy: y(p.rating).toFixed(1), r: radius }, plotted);
      });
      focusDot = make("circle", { "class": "dot focus", r: 5, visibility: "hidden" }, svg);
      visible = inView;
      yOf = y;
      show(visible.indexOf(selected) >= 0 ? selected : null);

      var from = formatDay(Math.max(view[0], first)), to = formatDay(Math.min(view[1], last));
      var whole = view[0] <= full[0] && view[1] >= full[1];
      caption.textContent = (whole ? "All contests, " : "Showing ") + from + " to " + to + ", " +
        inView.length + " of " + points.length + " rated contests";
      svg.setAttribute("aria-label", label + " from " + from + " to " + to + ", " + inView.length + " contests in view");
      zoomIn.disabled = view[1] - view[0] <= MIN_SPAN + 1;
      zoomOut.disabled = all.disabled = whole;
      earlier.disabled = view[0] <= full[0];
      later.disabled = view[1] >= full[1];
    }

    function changeText(p) {
      if (p.old === null || p.old === undefined) return String(p.rating);
      var sign = p.change > 0 ? "+" + p.change : p.change < 0 ? "−" + (-p.change) : "0";
      return p.old + " → " + p.rating + " (" + sign + ")";
    }

    function show(p) {
      selected = p;
      if (!p) {
        tip.hidden = true;
        if (focusDot) focusDot.setAttribute("visibility", "hidden");
        return;
      }
      var sx = x(p.t), sy = yOf(p.rating);
      focusDot.setAttribute("cx", sx.toFixed(1));
      focusDot.setAttribute("cy", sy.toFixed(1));
      focusDot.setAttribute("visibility", "visible");
      tip.textContent = "";
      var name = document.createElement("strong");
      name.textContent = p.contest;
      var when = document.createElement("span");
      when.textContent = p.date;
      var rating = document.createElement("span");
      rating.className = "tip-change" + (p.change > 0 ? " up" : p.change < 0 ? " down" : "");
      rating.textContent = changeText(p);
      tip.appendChild(name);
      tip.appendChild(when);
      tip.appendChild(rating);
      tip.hidden = false;
      // Place it beside the point, flipping to the left near the right edge.
      var box = svg.getBoundingClientRect(), outer = figure.getBoundingClientRect();
      var px = box.left - outer.left + sx * box.width / W;
      var py = box.top - outer.top + sy * box.height / H;
      var flip = px + tip.offsetWidth + 16 > outer.width;
      tip.style.left = Math.max(4, flip ? px - tip.offsetWidth - 12 : px + 12) + "px";
      tip.style.top = Math.max(4, py - tip.offsetHeight / 2) + "px";
    }

    function nearest(clientX) {
      var rect = svg.getBoundingClientRect();
      var sx = (clientX - rect.left) * W / rect.width;
      var best = null, gap = 24;  // Within 24 chart units of the pointer, about a dot's spacing.
      visible.forEach(function (p) {
        var d = Math.abs(x(p.t) - sx);
        if (d < gap) { gap = d; best = p; }
      });
      return best;
    }

    svg.addEventListener("pointerleave", function () { if (!Object.keys(pointers).length) show(null); });
    svg.addEventListener("keydown", function (event) {
      var key = event.key, i = visible.indexOf(selected);
      if (key === "ArrowLeft" || key === "ArrowRight") {
        if (!visible.length) return;
        i = i < 0 ? (key === "ArrowLeft" ? visible.length - 1 : 0) : Math.max(0, Math.min(visible.length - 1, i + (key === "ArrowLeft" ? -1 : 1)));
        show(visible[i]);
      } else if (key === "+" || key === "=") {
        zoom(0.5, selected ? selected.t : undefined);
      } else if (key === "-") {
        zoom(2, selected ? selected.t : undefined);
      } else if (key === "Escape") {
        show(null);
        return;
      } else {
        return;
      }
      event.preventDefault();
    });

    // Wheel zooms around the pointer; dragging pans; two fingers pinch to zoom.
    svg.addEventListener("wheel", function (event) {
      event.preventDefault();
      zoom(event.deltaY < 0 ? 0.8 : 1.25, timeAt(event.clientX));
    }, { passive: false });

    var pointers = {};
    function spread() {
      var xs = Object.keys(pointers).map(function (id) { return pointers[id]; });
      return xs.length === 2 ? { gap: Math.abs(xs[0] - xs[1]), mid: (xs[0] + xs[1]) / 2 } : null;
    }
    var moved = false;
    svg.addEventListener("pointerdown", function (event) {
      pointers[event.pointerId] = event.clientX;
      moved = false;
      svg.setPointerCapture(event.pointerId);
      svg.classList.add("dragging");
      show(nearest(event.clientX));  // A tap on a touch screen shows the contest too.
    });
    svg.addEventListener("pointermove", function (event) {
      if (!(event.pointerId in pointers)) {
        show(nearest(event.clientX));
        return;
      }
      if (!moved && Math.abs(event.clientX - pointers[event.pointerId]) < 3) return;  // A tap, not a drag.
      if (!moved) show(null);
      moved = true;
      var before = spread();
      var previous = pointers[event.pointerId];
      pointers[event.pointerId] = event.clientX;
      var after = spread();
      if (before && after && after.gap > 10) {
        zoom(before.gap / after.gap, timeAt(after.mid));
      } else if (!before) {
        var rect = svg.getBoundingClientRect();
        pan(-(event.clientX - previous) / (rect.width * PLOT / W) * (view[1] - view[0]));
      }
    });
    function release(event) {
      delete pointers[event.pointerId];
      if (!Object.keys(pointers).length) svg.classList.remove("dragging");
    }
    svg.addEventListener("pointerup", release);
    svg.addEventListener("pointercancel", release);

    figure.classList.add("zoomable");
    render();
  }

  document.querySelectorAll("figure.rating-chart[data-points]").forEach(setup);
})();
