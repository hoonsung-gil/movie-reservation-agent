"""저장된 프로필의 CGV 로그인 상태 확인 (헤드리스).

login_setup.py로 로그인한 뒤 실행하면, 프로필 재사용으로 로그인이 유지되는지 확인한다.
로그인 판별: 마이페이지/회원 전용 영역 접근 또는 로그인 링크 부재.
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

PROFILE_DIR = Path(__file__).resolve().parent.parent / "data" / "browser_profile"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")


def main():
    if not PROFILE_DIR.exists():
        print("프로필 없음 — 먼저 python scripts/login_setup.py 로 로그인하세요.")
        return 1
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=True,
            user_agent=UA,
            locale="ko-KR",
            viewport={"width": 1400, "height": 950},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        # CJ ONE SSO 상태 확인 API
        page.goto("https://cgv.co.kr/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2000)
        sso = page.evaluate("""async () => {
            try {
                const r = await fetch('https://oidc.cgv.co.kr/cjone/getCjssoq?ssoCheck=Y', {credentials:'include'});
                return await r.json();
            } catch(e) { return {err: ''+e}; }
        }""")
        mbr = (sso.get("data") or {}).get("ssoMbrNo")
        logged_in = bool(mbr)
        print("로그인 상태:", "✅ 로그인됨" if logged_in else "❌ 미로그인")
        if logged_in:
            print("회원번호(ssoMbrNo):", mbr)
        ctx.close()
    return 0 if logged_in else 2


if __name__ == "__main__":
    raise SystemExit(main())
