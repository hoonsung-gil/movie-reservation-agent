"""Playwright 브라우저 헬퍼.

CGV는 Cloudflare 보호로 단순 HTTP 요청(curl, requests)이 403 차단되므로
실제 Chromium 브라우저 컨텍스트로 접근한다.
"""
from contextlib import contextmanager

from playwright.sync_api import sync_playwright

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)


@contextmanager
def cgv_page(headless: bool = True):
    """CGV 접근용 Playwright page를 생성하는 컨텍스트 매니저."""
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            user_agent=USER_AGENT,
            locale="ko-KR",
            viewport={"width": 1280, "height": 900},
        )
        page = ctx.new_page()
        try:
            yield page
        finally:
            browser.close()
