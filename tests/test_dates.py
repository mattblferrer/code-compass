"""How pages word dates: relative near today, short otherwise, full on hover."""
from codecompass.core.dates import friendly_date, full_date, short_date

TODAY = "2026-11-11"  # A Wednesday.


def test_near_dates_are_relative():
    assert friendly_date("2026-11-11", TODAY) == "Today"
    assert friendly_date("2026-11-10", TODAY) == "Yesterday"
    assert friendly_date("2026-11-12", TODAY) == "Tomorrow"
    assert friendly_date("2026-11-14", TODAY) == "in 3 days"
    assert friendly_date("2026-11-06", TODAY) == "5 days ago"
    assert friendly_date("2026-11-17", TODAY) == "in 6 days"
    assert friendly_date("2026-11-18", TODAY) == "Wed 18 Nov"  # A week or more away.
    assert friendly_date("2026-11-04", TODAY) == "Wed 4 Nov"


def test_day_headings_name_only_today_and_yesterday():
    assert friendly_date("2026-11-10", TODAY, within=1) == "Yesterday"
    assert friendly_date("2026-11-09", TODAY, within=1) == "Mon 9 Nov"


def test_short_and_full_dates():
    assert short_date("2026-03-02", TODAY) == "Mon 2 Mar"
    assert short_date("2025-12-31", TODAY) == "Wed 31 Dec 2025"  # Another year shows its year.
    assert full_date("2026-11-11") == "Wed 11 Nov 2026"
