import os

# The API modules read configuration at import time, so the environment has to
# be populated before any of them are imported by a test module.
os.environ.setdefault("DATABASE_URL", "postgresql://axiom:axiom@localhost:26257/axiom")
os.environ.setdefault("AWS_REGION", "eu-west-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_SESSION_TOKEN", "testing")

import pytest


class FakeCursor:
    """Cursor double that records statements and replays scripted result sets.

    ``results`` maps a substring of a SQL statement to the rows that a
    subsequent ``fetchall``/``fetchone`` should return.
    """

    def __init__(self, results=None):
        self.results = results or {}
        self.statements = []
        self._rows = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self.statements.append((" ".join(sql.split()), params))
        self._rows = []

        for marker, rows in self.results.items():
            if " ".join(marker.split()) in " ".join(sql.split()):
                self._rows = list(rows)
                break

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def statements_matching(self, marker):
        marker = " ".join(marker.split())
        return [s for s in self.statements if marker in s[0]]


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return self._cursor


def fake_connect(cursor):
    """Build a ``psycopg.connect`` replacement that yields ``cursor``."""

    calls = []

    def connect(dsn, *args, **kwargs):
        calls.append(dsn)
        return FakeConnection(cursor)

    connect.calls = calls
    return connect


@pytest.fixture
def cursor():
    return FakeCursor()
