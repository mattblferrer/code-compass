// Score over time on a pattern's page: pointing at a point, tapping it, or stepping
// with the arrow keys shows its score and how it changed, with the same details box
// as the rating history (chart_tip.js). Without JavaScript, each dot keeps its title.
(function () {
  function setup(figure) {
    var svg = figure.querySelector("svg");
    var points = JSON.parse(figure.getAttribute("data-points"));
    if (!svg || points.length < 2) return;
    var view = svg.viewBox.baseVal;
    var tip = window.ChartTip.create(figure, svg, view.width, view.height);
    var selected = null;

    // The details box replaces the browser's own titles, so the two never show together.
    svg.querySelectorAll("circle.dot title").forEach(function (t) { t.remove(); });
    var hint = document.createElement("small");
    hint.className = "chart-hint";
    hint.textContent = "Point at a date for its score. With the chart focused, arrow keys step through the dates.";
    figure.insertBefore(hint, svg);

    // Attempts since the point before, which is a week back except at today's point.
    function attempts(p) {
      var n = p.attempts === 0 ? "No attempts" : p.attempts === 1 ? "1 attempt" : p.attempts + " attempts";
      return p.since ? n + " since " + window.ChartTip.dayLabel(p.since) : n;
    }

    function show(p) {
      selected = p;
      if (!p) { tip.hide(); return; }
      tip.show(p.x, p.y, { title: window.ChartTip.dayLabel(p.date), note: attempts(p), prefix: "Score ",
                           old: p.old, value: p.shown, change: p.change });
    }

    function nearest(clientX) {
      return tip.nearest(clientX, points, function (p) { return p.x; });
    }

    svg.addEventListener("pointermove", function (event) { show(nearest(event.clientX)); });
    svg.addEventListener("pointerdown", function (event) { show(nearest(event.clientX)); });
    svg.addEventListener("pointerleave", function (event) {
      if (event.pointerType === "mouse") show(null);  // A tap on a touch screen keeps its details.
    });
    svg.addEventListener("keydown", function (event) {
      if (event.key === "ArrowLeft" || event.key === "ArrowRight") show(tip.step(event.key, points, selected));
      else if (event.key === "Escape") show(null);
      else return;
      event.preventDefault();
    });
    svg.addEventListener("blur", function () { show(null); });
  }

  document.querySelectorAll("figure.score-chart[data-points]").forEach(setup);
})();
