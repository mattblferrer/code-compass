// Light and dark mode toggle in the header. The page follows the system setting
// until the user picks the other one; the choice is kept in this browser only.
// Picking the mode the system already uses clears the choice, so the page follows
// the system again. base.html applies a saved choice before the page paints.
(function () {
  var KEY = "codecompass-theme";
  var root = document.documentElement;
  var button = document.getElementById("theme-toggle");
  if (!button) return;
  var label = button.querySelector(".theme-label");
  var system = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;

  function systemTheme() {
    return system && system.matches ? "dark" : "light";
  }

  function current() {
    return root.getAttribute("data-theme") || systemTheme();
  }

  function update() {
    var dark = current() === "dark";
    // The button names the mode it switches to.
    label.textContent = dark ? "Light" : "Dark";
    button.setAttribute("aria-label", dark ? "Switch to light mode" : "Switch to dark mode");
    button.title = button.getAttribute("aria-label");
    button.classList.toggle("is-dark", dark);
  }

  button.addEventListener("click", function () {
    var next = current() === "dark" ? "light" : "dark";
    try {
      if (next === systemTheme()) localStorage.removeItem(KEY);
      else localStorage.setItem(KEY, next);
    } catch (e) { /* Storage may be unavailable; the choice lasts until the page changes. */ }
    if (next === systemTheme()) root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", next);
    update();
  });

  if (system && system.addEventListener) system.addEventListener("change", update);
  button.hidden = false;
  update();
})();
