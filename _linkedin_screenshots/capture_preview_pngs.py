# -*- coding: utf-8 -*-
"""Serve static HTML in this folder and save PNG previews with Playwright (headless)."""
from __future__ import annotations

import http.server
import socketserver
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PORT = 9888


class _StaticHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(HERE), **kwargs)


def main() -> None:
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), _StaticHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    time.sleep(0.4)
    base = f"http://127.0.0.1:{PORT}"
    try:
        from playwright.sync_api import sync_playwright

        out = [
            ("demo_uploaders_login.html", "linkedin-01-uploaders-login-preview.png"),
            ("demo_cron_panel.html", "linkedin-02-cron-panel-preview.png"),
        ]
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1360, "height": 900})
            for html_name, png_name in out:
                page.goto(f"{base}/{html_name}", wait_until="networkidle", timeout=60_000)
                page.screenshot(path=str(HERE / png_name), full_page=True)
                print("Wrote", HERE / png_name)
            browser.close()
    finally:
        httpd.shutdown()


if __name__ == "__main__":
    main()
