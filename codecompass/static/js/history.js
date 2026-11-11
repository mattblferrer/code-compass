// History calendar (R-40): on a narrow screen the year scrolls sideways, so start it at
// the most recent weeks, where the latest practice is. Without JavaScript it starts at
// the oldest weeks and can still be scrolled.
(function () {
  var grid = document.getElementById("year-grid");
  if (grid && grid.scrollWidth > grid.clientWidth) grid.scrollLeft = grid.scrollWidth;
})();
