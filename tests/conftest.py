"""Shared fixtures: serve the repo over local HTTP (so the CSP applies as in production)
and give each test a fresh page that fails on any console error or page error."""
import functools
import http.server
import threading
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@pytest.fixture(scope="session")
def base_url():
    handler = functools.partial(_QuietHandler, directory=str(ROOT))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/"
    server.shutdown()
    server.server_close()


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def make_page(browser, base_url):
    """Factory: make_page(query="", width=1280, height=900, mobile=False, dark=False, now=None)."""
    contexts, errors = [], []

    def _make(query="", width=1280, height=900, mobile=False, dark=False, now=None):
        ctx = browser.new_context(
            viewport={"width": width, "height": height},
            is_mobile=mobile, has_touch=mobile,
            color_scheme="dark" if dark else "light",
            accept_downloads=True, locale="en-US", timezone_id="America/Chicago",
        )
        contexts.append(ctx)
        page = ctx.new_page()
        page.on("console", lambda m: m.type == "error" and errors.append(m.text))
        page.on("pageerror", lambda e: errors.append(str(e)))
        if now:
            page.clock.set_fixed_time(now)
        page.goto(base_url + query)
        page.wait_for_selector("#calBody tr.week")
        return page

    yield _make
    for ctx in contexts:
        ctx.close()
    assert not errors, f"Console/page errors: {errors}"


@pytest.fixture
def page(make_page):
    return make_page()
