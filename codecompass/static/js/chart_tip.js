// Shared details box for the line charts (the rating history and a pattern's score
// over time): a highlighted point and a box beside it with a title, a muted line, and
// the change as old → new (+delta). Each chart decides which point is chosen.
window.ChartTip = (function () {
  var NS = "http://www.w3.org/2000/svg";

  // "1602 → 1764 (+162)", or just the value when there is nothing before it.
  function changeText(old, value, change) {
    if (old === null || old === undefined) return String(value);
    var sign = change > 0 ? "+" + change : change < 0 ? "−" + (-change) : "0";
    return old + " → " + value + " (" + sign + ")";
  }

  // `width` and `height` are the SVG's viewBox size, to place the box over the drawing.
  function create(figure, svg, width, height) {
    var tip = document.createElement("div");
    tip.className = "chart-tip";
    tip.hidden = true;
    tip.setAttribute("role", "status");
    figure.appendChild(tip);
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

    // `detail` is { title, note, old, value, change } at chart position (sx, sy).
    function show(sx, sy, detail) {
      if (!dot || !dot.parentNode) attach();
      dot.setAttribute("cx", sx.toFixed(1));
      dot.setAttribute("cy", sy.toFixed(1));
      dot.setAttribute("visibility", "visible");
      tip.textContent = "";
      var title = document.createElement("strong");
      title.textContent = detail.title;
      var note = document.createElement("span");
      note.textContent = detail.note;
      var change = document.createElement("span");
      change.className = "tip-change" + (detail.change > 0 ? " up" : detail.change < 0 ? " down" : "");
      change.textContent = (detail.prefix || "") + changeText(detail.old, detail.value, detail.change);
      tip.appendChild(title);
      tip.appendChild(note);
      tip.appendChild(change);
      tip.hidden = false;
      // Beside the point, flipping to the left near the right edge.
      var box = svg.getBoundingClientRect(), outer = figure.getBoundingClientRect();
      var px = box.left - outer.left + sx * box.width / width;
      var py = box.top - outer.top + sy * box.height / height;
      var flip = px + tip.offsetWidth + 16 > outer.width;
      tip.style.left = Math.max(4, flip ? px - tip.offsetWidth - 12 : px + 12) + "px";
      tip.style.top = Math.max(4, py - tip.offsetHeight / 2) + "px";
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

  return { create: create, changeText: changeText };
})();
