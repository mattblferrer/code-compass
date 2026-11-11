// History calendar (R-40). Pointing at a day, or tabbing to one, shows the same details
// card as the rating and score charts (chart_tip.js): the date, how the day went by
// outcome, and the problems solved. On a narrow screen the year scrolls sideways, so it
// starts at the most recent weeks. Without JavaScript each day keeps its title instead.
(function () {
  var grid = document.getElementById("year-grid");
  if (!grid) return;
  if (grid.scrollWidth > grid.clientWidth) grid.scrollLeft = grid.scrollWidth;

  var panel = grid.closest(".progress-panel");
  if (!panel || !window.ChartTip) return;
  var tip = window.ChartTip.forCells(panel);
  var cells = grid.querySelectorAll(".cell[data-tip-title]");

  // The card replaces the browser's own tooltip, so the two never show together.
  Array.prototype.forEach.call(cells, function (cell) { cell.removeAttribute("title"); });

  function detail(cell) {
    return { title: cell.getAttribute("data-tip-title"), note: cell.getAttribute("data-tip-note"),
             value: cell.getAttribute("data-tip-value") };
  }

  grid.addEventListener("pointerover", function (event) {
    var cell = event.target.closest(".cell[data-tip-title]");
    if (cell) tip.show(cell, detail(cell));
  });
  grid.addEventListener("pointerleave", function () { tip.hide(); });
  grid.addEventListener("focusin", function (event) {
    var cell = event.target.closest(".cell[data-tip-title]");
    if (cell) tip.show(cell, detail(cell));
  });
  grid.addEventListener("focusout", function () { tip.hide(); });
  grid.addEventListener("keydown", function (event) { if (event.key === "Escape") tip.hide(); });
  // Scrolling the year on a phone would leave the card beside the wrong day.
  grid.addEventListener("scroll", function () { tip.hide(); }, { passive: true });
})();
