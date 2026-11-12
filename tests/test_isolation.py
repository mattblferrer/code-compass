"""Tests never open the real data in the project's instance folder (conftest.py)."""
import pytest

from codecompass import create_app
from codecompass.db import connect


def test_opening_the_real_database_directly_is_refused():
    with pytest.raises(RuntimeError):
        connect("instance/codecompass.sqlite")


def test_an_app_without_a_test_database_is_refused():
    with pytest.raises(RuntimeError):
        create_app({"TESTING": True})
