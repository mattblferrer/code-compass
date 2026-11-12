// Progress page (R-48): every pattern's score line is quiet until it is picked, by pointing
// at the chart (the nearest line), or at a pattern in the lists beside it, or by tabbing
// to one. A picked line turns blue, and the chart's details card shows its score at the
// nearest week, as the other charts do (chart_tip.js).
(function () {
  var figure = document.getElementById("all-scores");
  if (!figure || !window.ChartTip) return;
  var svg = figure.querySelector("svg");
  var view = svg.viewBox.baseVal;
  var tip = window.ChartTip.create(figure, svg, view.width, view.height);
  var lines = Array.prototype.map.call(svg.querySelectorAll("polyline.series"), function (el) {
    el.querySelector("title").remove();  // The card replaces the browser's own tooltip.
    return { el: el, name: el.getAttribute("data-pattern"), points: JSON.parse(el.getAttribute("data-points")) };
  });
  var picked = null;

  function pick(line, point) {
    if (picked && picked !== line) picked.el.classList.remove("picked");
    picked = line;
    document.querySelectorAll(".movers li").forEach(function (li) {
      li.classList.toggle("picked", !!line && li.getAttribute("data-pattern") === line.name);
    });
    if (!line) { tip.hide(); return; }
    line.el.classList.add("picked");
    svg.appendChild(line.el);  // Drawn last, so it sits on top.
    point = point || line.points[line.points.length - 1];
    var i = line.points.indexOf(point);
    var before = i > 0 ? line.points[i - 1] : null;
    tip.show(point.x, point.y, { title: line.name, note: window.ChartTip.dayLabel(point.date), prefix: "Score ",
                                 old: before ? before.score : null, value: point.score,
                                 change: before ? point.score - before.score : null });
  }

  // The line nearest the pointer, at the week nearest it across.
  svg.addEventListener("pointermove", function (event) {
    var box = svg.getBoundingClientRect();
    var sx = (event.clientX - box.left) * view.width / box.width;
    var sy = (event.clientY - box.top) * view.height / box.height;
    var best = null, bestPoint = null, gap = Infinity;
    lines.forEach(function (line) {
      line.points.forEach(function (p) {
        var d = Math.abs(p.x - sx) * 0.5 + Math.abs(p.y - sy);
        if (d < gap) { gap = d; best = line; bestPoint = p; }
      });
    });
    if (best && gap < 40) pick(best, bestPoint);
  });
  svg.addEventListener("pointerleave", function () { pick(null); });

  document.querySelectorAll(".movers li[data-pattern]").forEach(function (li) {
    var line = lines.filter(function (l) { return l.name === li.getAttribute("data-pattern"); })[0];
    if (!line) return;
    li.addEventListener("pointerenter", function () { pick(line); });
    li.addEventListener("pointerleave", function () { pick(null); });
    li.addEventListener("focusin", function () { pick(line); });
    li.addEventListener("focusout", function () { pick(null); });
  });
})();
