"""CGV 로그인용 브라우저 (1회 실행).

전용 Playwright 프로필(data/browser_profile)로 실제 크롬 창을 띄운다.
이 창에서 CGV에 로그인하면 쿠키가 프로필에 저장되어,
이후 자동 예매 스크립트가 같은 로그인 상태를 재사용한다.

개선점:
- 홈 광고/이벤트 팝업을 자동으로 닫아준다(Escape + 흔한 닫기 버튼, 광고 팝업창 close).
- 로그인 완료(SSO ssoMbrNo 등장)를 자동 감지하면 저장 후 스스로 종료.
  → 사용자가 창을 직접 닫을 필요 없음.

사용법:
  python scripts/login_setup.py
  → 열린 창에서 로그인만 하면 됨. (완료되면 자동으로 닫힘)
"""
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from playwright.sync_api import sync_playwright

PROFILE_DIR = Path(__file__).resolve().parent.parent / "data" / "browser_profile"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
TIMEOUT_MIN = 15
LOGIN_URL = "https://cgv.co.kr/mem/login?returnUrl=%2F"


def dismiss_ads(page):
    """광고 모달(.cgv-modal.active)이 떠 있으면 닫는다. 최대 10초 재시도."""
    for _ in range(10):
        try:
            modal = page.locator(".cgv-modal.active")
            if modal.count() == 0:
                return
            for sel in ["button:has-text('오늘은 그만 보기')", "button:has-text('오늘 하루 보지 않기')",
                        "button:has-text('닫기')", "button[class*='close']"]:
                try:
                    modal.first.locator(sel).first.click(timeout=1500)
                    break
                except Exception:
                    continue
            page.wait_for_timeout(700)
        except Exception:
            return


def is_logged_in(page) -> str | None:
    try:
        sso = page.evaluate("""async () => {
            try { const r = await fetch('https://oidc.cgv.co.kr/cjone/getCjssoq?ssoCheck=Y',{credentials:'include'}); return await r.json(); }
            catch(e){ return {err:''+e}; }
        }""")
        return (sso.get("data") or {}).get("ssoMbrNo")
    except Exception:
        return None


def main():
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR), headless=False, user_agent=UA,
            locale="ko-KR", viewport={"width": 1360, "height": 900},
            args=["--disable-blink-features=AutomationControlled", "--disable-notifications"],
        )
        # 광고 팝업창(새 창) 자동 닫기 — 확실한 광고 URL일 때만. 애매하면 절대 닫지 않음.
        def on_page(pg):
            try:
                time.sleep(2)  # 네비게이션 완료 대기 (about:blank → 실제 URL)
                url = (pg.url or "").lower()
                if "ad.cgv" in url or "netinsight" in url:
                    pg.close()
            except Exception:
                pass
        ctx.on("page", on_page)

        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2000)
        dismiss_ads(page)

        print("=" * 60)
        print("로그인 페이지가 바로 열렸습니다. 아이디/비밀번호로 로그인해 주세요.")
        print("완료되면 자동으로 저장되고 창이 닫힙니다.")
        print("=" * 60)
        sys.stdout.flush()

        deadline = time.time() + TIMEOUT_MIN * 60
        logged = None
        while time.time() < deadline:
            time.sleep(3)
            # 조용히 SSO만 폴링 — 사용자 입력(로그인 폼)을 방해하지 않도록
            # Escape/닫기 클릭/포커스 이동은 절대 반복하지 않는다.
            pages = [pg for pg in ctx.pages if not pg.is_closed()]
            if not pages:
                break
            for cur in pages:
                logged = is_logged_in(cur)
                if logged:
                    break
            if logged:
                break

        if logged:
            print(f"✅ 로그인 확인됨 (회원번호 {logged}). 프로필 저장 후 종료합니다.")
        else:
            print("⏱ 시간 초과 — 로그인 감지 못함. 다시 시도해 주세요.")
        try:
            ctx.close()
        except Exception:
            pass
    print("프로필 위치:", PROFILE_DIR)


if __name__ == "__main__":
    main()
