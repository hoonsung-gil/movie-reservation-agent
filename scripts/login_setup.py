"""CGV 로그인용 브라우저 (1회 실행).

전용 Playwright 프로필(data/browser_profile)로 실제 크롬 창을 띄운다.
이 창에서 CGV에 로그인하면 쿠키가 프로필에 저장되어,
이후 자동 예매 스크립트가 같은 로그인 상태를 재사용한다.

사용법:
  python scripts/login_setup.py
  → 열린 창에서 로그인 → 로그인 완료되면 이 창을 닫으면 끝.
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

PROFILE_DIR = Path(__file__).resolve().parent.parent / "data" / "browser_profile"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")


def main():
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            user_agent=UA,
            locale="ko-KR",
            viewport={"width": 1400, "height": 950},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://cgv.co.kr/", wait_until="domcontentloaded", timeout=60000)
        print("=" * 60)
        print("이 창에서 CGV(우측 상단/메뉴)에 로그인해 주세요.")
        print("로그인 완료 후, 이 브라우저 창을 그냥 닫으면 저장됩니다.")
        print("=" * 60)
        sys.stdout.flush()
        # 사용자가 창을 닫을 때까지 대기
        try:
            page.wait_for_event("close", timeout=0)
        except Exception:
            pass
        try:
            ctx.close()
        except Exception:
            pass
    print("프로필 저장 완료:", PROFILE_DIR)


if __name__ == "__main__":
    main()
