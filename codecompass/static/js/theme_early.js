// Apply a saved light or dark choice before the page paints, so it never flashes the other one.
// Loaded in the head, before the page, as its own file so no script sits inside the page.
try {
  var theme = localStorage.getItem("codecompass-theme");
  if (theme === "light" || theme === "dark") document.documentElement.setAttribute("data-theme", theme);
} catch (e) { /* Storage may be unavailable; the system setting is used. */ }
