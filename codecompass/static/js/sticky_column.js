// Columns that stay in view while the page scrolls on wide screens (app.css): Practice next
// on the dashboard, and the side cards on a pattern's page. When one is taller than the
// window, its top moves up by the difference, so it scrolls until its end shows and then
// stays put. Without JavaScript it keeps the offset set in app.css.
(function () {
  var columns = document.querySelectorAll("[data-sticky]");
  if (!columns.length || !window.ResizeObserver) return;
  var header = document.querySelector(".site-header");
  var GAP = 16;

  function place(column) {
    var offset = (header ? header.offsetHeight : 0) + GAP;
    column.style.top = Math.min(offset, window.innerHeight - column.offsetHeight - GAP) + "px";
  }

  columns.forEach(function (column) {
    new ResizeObserver(function () { place(column); }).observe(column);
    window.addEventListener("resize", function () { place(column); });
    place(column);
  });
})();
