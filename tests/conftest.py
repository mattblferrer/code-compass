import pytest

from codecompass import create_app


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.sqlite")


@pytest.fixture
def app(db_path):
    return create_app({"TESTING": True, "DATABASE": db_path})


@pytest.fixture
def client(app):
    return app.test_client()
