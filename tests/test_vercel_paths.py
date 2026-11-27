"""Hosted mode on Vercel (R-50): pages whose addresses hold encoded characters still open.

Vercel passes PATH_INFO still percent-encoded, so `/patterns/Prefix%20Sums` reached Flask
as a pattern named `Prefix%20Sums` and answered 404. The tests send the path the way
Vercel does.
"""
from codecompass.vercel_paths import DecodedPath


def _get_raw(app, raw_path):
    return app.test_client().get("/", environ_overrides={"PATH_INFO": raw_path})


def test_a_still_encoded_pattern_address_opens_the_pattern(app):
    app.wsgi_app = DecodedPath(app.wsgi_app)
    response = _get_raw(app, "/patterns/Prefix%20Sums")
    assert response.status_code == 200
    assert "Prefix Sums" in response.get_data(as_text=True)


def test_without_decoding_the_encoded_address_is_not_found(app):
    assert _get_raw(app, "/patterns/Prefix%20Sums").status_code == 404


def test_encoded_utf8_and_plain_paths_pass_through_unchanged():
    seen = []
    middleware = DecodedPath(lambda environ, start_response: seen.append(environ["PATH_INFO"]))
    for raw in ("/patterns/Prefix%20Sums", "/problems/caf%C3%A9", "/help"):
        middleware({"PATH_INFO": raw}, None)
    # PEP 3333 strings carry the bytes as latin-1; Werkzeug turns them back into UTF-8 text.
    assert seen == ["/patterns/Prefix Sums", "/problems/caf\u00c3\u00a9", "/help"]
