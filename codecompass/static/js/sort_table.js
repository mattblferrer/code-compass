// Sortable attempt lists on a pattern's page. Clicking a header sorts by that column, and
// clicking it again sorts the other way, in place, with the same rules as the server
// (core/ordering.py): newest dates first, the rest A to Z on first click, ties newest
// first. The sort goes into this page's address, so a reload keeps it and other
// patterns keep their own. Without JavaScript, the header links load the page sorted.
(function () {
  var FIRST = { date: "desc", problem: "asc", difficulty: "asc", outcome: "asc" };

  function setup(table) {
    var body = table.tBodies[0];
    var links = table.querySelectorAll("thead a.sort");
    var key = table.getAttribute("data-sort"), order = table.getAttribute("data-order");

    function value(row, k) {
      if (k === "date") return row.getAttribute("data-date");
      if (k === "problem") return row.getAttribute("data-problem");
      return Number(row.getAttribute("data-" + k));
    }

    function newest(a, b) {
      var da = a.getAttribute("data-date"), db = b.getAttribute("data-date");
      if (da !== db) return da < db ? 1 : -1;
      return Number(b.getAttribute("data-id")) - Number(a.getAttribute("data-id"));
    }

    function sort(k, o) {
      var rows = Array.prototype.slice.call(body.rows);
      rows.sort(function (a, b) {
        var va = value(a, k), vb = value(b, k);
        if (va !== vb) return (va < vb ? -1 : 1) * (o === "desc" ? -1 : 1);
        return newest(a, b);
      });
      rows.forEach(function (r) { body.appendChild(r); });
      key = k;
      order = o;
      Array.prototype.forEach.call(links, function (link) {
        var col = link.getAttribute("data-key");
        link.parentNode.setAttribute("aria-sort", col === key ? (order === "asc" ? "ascending" : "descending") : "none");
      });
      var url = new URL(location.href);
      url.searchParams.set("sort", key);
      url.searchParams.set("order", order);
      url.hash = "attempts";
      history.replaceState(null, "", url);
    }

    Array.prototype.forEach.call(links, function (link) {
      link.addEventListener("click", function (event) {
        event.preventDefault();
        var col = link.getAttribute("data-key");
        sort(col, col === key ? (order === "asc" ? "desc" : "asc") : FIRST[col]);
      });
    });
  }

  document.querySelectorAll("table.sortable").forEach(setup);
})();
