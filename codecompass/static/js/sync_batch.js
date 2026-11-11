// Selecting several sync items to save or dismiss at once (R-33). Adds Select all, a
// count of what is selected, and Shift-click to select a run of items, and turns off
// the actions until something is selected. Without JavaScript the checkboxes and
// actions still work; the server checks each item either way.
(function () {
  var form = document.getElementById("batch-form");
  if (!form) return;
  var boxes = Array.prototype.slice.call(document.querySelectorAll('input.pick[form="batch-form"]'));
  var all = document.getElementById("select-all");
  var count = document.getElementById("batch-count");
  var buttons = form.querySelectorAll(".batch-actions button");
  var help = form.querySelector(".batch-actions details");
  var notSolved = form.querySelector('button[value="not_solved"]');
  var idle = count.textContent;
  var last = null;

  function update() {
    var picked = boxes.filter(function (b) { return b.checked; });
    var n = picked.length;
    count.textContent = n ? n + " of " + boxes.length + " selected" : idle;
    count.classList.toggle("picked", n > 0);
    Array.prototype.forEach.call(buttons, function (b) { b.disabled = !n; });
    help.classList.toggle("disabled", !n);
    if (!n) help.open = false;
    // "Not solved" fits only items with no accepted submission.
    notSolved.disabled = !picked.some(function (b) { return b.getAttribute("data-accepted") === "0"; });
    all.checked = n > 0 && n === boxes.length;
    all.indeterminate = n > 0 && n < boxes.length;
  }

  boxes.forEach(function (box, i) {
    box.addEventListener("click", function (event) {
      // Shift-click sets every item between this one and the last one clicked to match.
      if (event.shiftKey && last !== null && last !== i) {
        var from = Math.min(last, i), to = Math.max(last, i);
        for (var k = from; k <= to; k++) boxes[k].checked = box.checked;
      }
      last = i;
      update();
    });
  });

  all.addEventListener("change", function () {
    boxes.forEach(function (b) { b.checked = all.checked; });
    update();
  });

  // Keyboard users can still open "Had external help" only with something selected.
  help.addEventListener("toggle", function () {
    if (help.open && help.classList.contains("disabled")) help.open = false;
  });

  all.closest("label").hidden = false;
  update();
})();
