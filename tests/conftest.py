import csv

import pytest

from codecompass import create_app

TEST_CATALOG = [
    ["Two Sum", "https://example.com/two-sum", "easy", "", "Test list", "Arrays and Hashing"],
    ["Valid Parentheses", "https://example.com/parens", "easy", "", "Test list", "Stack"],
    ["Daily Temperatures", "https://example.com/temps", "medium", "", "Test list", "Monotonic Stack and Queue; Stack"],
    ["Course Schedule", "https://example.com/courses", "medium", "1700", "Codeforces", "Topological Sort"],
]


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.sqlite")


@pytest.fixture
def catalog_path(tmp_path):
    path = tmp_path / "catalog.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["title", "link", "difficulty", "rating", "source", "patterns"])
        writer.writerows(TEST_CATALOG)
    return str(path)


@pytest.fixture
def app(db_path, catalog_path):
    return create_app({"TESTING": True, "DATABASE": db_path, "CATALOG_PATH": catalog_path, "RESERVE_PATH": None})


@pytest.fixture
def client(app):
    return app.test_client()
