"""Smoke test for the Playwright install: launches headless Chromium, loads a URL,
and saves a screenshot. Run this after `playwright install chromium` in a new
container/venv to confirm the browser binary is actually usable, before writing any
real scraping code against it.

Usage:
    python scripts/playwright_smoke.py
    python scripts/playwright_smoke.py https://www.google.com/maps
    python scripts/playwright_smoke.py https://example.com tmp/example.png
"""

import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright

DEFAULT_URL = "https://example.com"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "playwright_smoke.png"


async def run(url: str, output_path: Path) -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.goto(url, wait_until="load")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            await page.screenshot(path=str(output_path))
        finally:
            await browser.close()

    print(f"OK: loaded {url}, screenshot saved to {output_path}")


def main() -> None:
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUTPUT
    asyncio.run(run(url, output_path))


if __name__ == "__main__":
    main()
