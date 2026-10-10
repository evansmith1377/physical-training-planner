"""Regenerate the link-preview image and README screenshots.

Usage: python scripts/screenshots.py   (needs the dev dependencies in requirements-dev.txt)
Writes assets/og-image.png (1200x630) and docs/screenshot-desktop.png, docs/screenshot-mobile.png.
"""
import functools
import http.server
import threading
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
DEMO = "?raceTime=1%3A50%3A00&anchorDate=2027-03-14"  # sample settings shown in the screenshots
NOW = datetime(2026, 10, 10, 12, 0)

OG_CARD = """<!doctype html><meta charset="utf-8"><style>
  body { margin: 0; width: 1200px; height: 630px; display: grid; grid-template-columns: 1.05fr 1fr; gap: 48px;
         align-items: center; padding: 0 72px; box-sizing: border-box; background: #1d2733; color: #fff;
         font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
  h1 { font-size: 66px; line-height: 1.05; margin: 0 0 24px; }
  p { font-size: 28px; line-height: 1.35; color: #c9d4e0; margin: 0 0 32px; }
  .url { font-size: 22px; color: #7fb0ec; }
  .cal { display: grid; grid-template-columns: repeat(7, 1fr); gap: 8px; }
  .cal div { height: 58px; border-radius: 6px; background: #2a3542; border-left: 6px solid var(--c); }
</style>
<div><h1>Physical Training Planner</h1>
<p>Printable, week-by-week marathon &amp; half-marathon plans from your current fitness.</p>
<div class="url">Free · private · no sign-up</div></div>
<div class="cal">""" + "".join(
    f'<div style="--c:{c}"></div>'
    for c in ("#8a96a3 #3c9a5f #d97a1e #b9c2cc #3c9a5f #3c9a5f #2f6db5 " * 6).split()
) + "</div>"


def main():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
    handler.log_message = lambda *a: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}/{DEMO}"
    (ROOT / "docs").mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()

        card = browser.new_page(viewport={"width": 1200, "height": 630})
        card.set_content(OG_CARD)
        card.screenshot(path=ROOT / "assets" / "og-image.png")

        desk = browser.new_page(viewport={"width": 1280, "height": 860})
        desk.clock.set_fixed_time(NOW)
        desk.goto(url)
        desk.locator("#summary").scroll_into_view_if_needed()
        desk.evaluate("scrollBy(0, -12)")
        desk.screenshot(path=ROOT / "docs" / "screenshot-desktop.png")

        mob = browser.new_page(viewport={"width": 390, "height": 760}, device_scale_factor=2, is_mobile=True)
        mob.clock.set_fixed_time(NOW)
        mob.goto(url)
        mob.locator("tr.week").first.scroll_into_view_if_needed()
        mob.evaluate("scrollBy(0, -60)")
        mob.screenshot(path=ROOT / "docs" / "screenshot-mobile.png")
        browser.close()
    server.shutdown()
    print("Wrote assets/og-image.png, docs/screenshot-desktop.png, docs/screenshot-mobile.png")


if __name__ == "__main__":
    main()
