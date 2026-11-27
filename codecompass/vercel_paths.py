"""Undo Vercel's still-encoded request paths (R-50).

WSGI servers must hand the app a percent-decoded PATH_INFO (PEP 3333), but Vercel's
Python runtime passes the path as the browser sent it. Flask then sees
`/patterns/Prefix%20Sums`, finds no pattern named `Prefix%20Sums`, and answers 404,
so every page whose address holds a space or other encoded character breaks.

`api/index.py` wraps the hosted app in it; local mode never uses it.
"""
from urllib.parse import unquote_to_bytes


class DecodedPath:
    """WSGI middleware that percent-decodes PATH_INFO before Flask routes it."""

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        if "%" in path:
            # PEP 3333 carries the path's bytes as a latin-1 string; Werkzeug decodes them as UTF-8.
            environ["PATH_INFO"] = unquote_to_bytes(path).decode("latin-1")
        return self.app(environ, start_response)
