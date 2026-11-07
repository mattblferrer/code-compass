// Optional solve timer (R-26). Saves exact seconds in a hidden field and shows
// minutes in the visible field. Typing in the minutes field clears the timer value.
(function () {
  var toggle = document.getElementById("timer-toggle");
  var display = document.getElementById("timer-display");
  var minutesField = document.getElementById("time-minutes");
  var secondsField = document.getElementById("time-seconds");
  if (!toggle) return;

  var startedAt = null;
  var saved = parseInt(secondsField.value, 10) || 0;
  var tick = null;

  function elapsed() {
    return saved + (startedAt ? Math.round((Date.now() - startedAt) / 1000) : 0);
  }

  function show() {
    var total = elapsed();
    var seconds = total % 60;
    display.textContent = Math.floor(total / 60) + ":" + (seconds < 10 ? "0" : "") + seconds;
  }

  function record() {
    var total = elapsed();
    if (total < 1) return;
    secondsField.value = total;
    var minutes = Math.round((total / 60) * 10000) / 10000;
    minutesField.value = String(minutes);
  }

  toggle.addEventListener("click", function () {
    if (startedAt) {
      saved = elapsed();
      startedAt = null;
      clearInterval(tick);
      toggle.textContent = "Resume timer";
      record();
    } else {
      startedAt = Date.now();
      tick = setInterval(show, 1000);
      toggle.textContent = "Stop timer";
    }
    show();
  });

  minutesField.addEventListener("input", function () {
    secondsField.value = "";
    saved = 0;
  });

  // Keep the time if the form is submitted while the timer is running.
  toggle.form.addEventListener("submit", function () {
    if (startedAt) record();
  });

  show();
})();
