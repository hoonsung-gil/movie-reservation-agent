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
CLOSE_SELECTORS = [
    "text=오늘 하루 보지 않기", "text=오늘 하루 열지 않기", "text=일주일간 보지 않기",
    "button:has-text('닫기')", "[class*='close']", "[class*='btnClose']", "[aria-label='닫기']",
]


def dismiss_ads(page):
    """홈 광고/이벤트 레이어 닫기 시도 (안전한 것만)."""
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass
    for sel in CLOSE_SELECTORS:
        try:
            loc = page.locator(sel)
            for i in range(min(loc.count(), 3)):
                try:
                    loc.nth(i).click(timeout=800)
                except Exception:
                    pass
        except Exception:
            pass


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
        # 광고 팝업창(새 창)은 자동으로 닫기 — 단 로그인/CJ ONE 창은 유지
        def on_page(pg):
            try:
                url = pg.url or ""
                if "ad.cgv" in url or url in ("about:blank", ""):
                    time.sleep(1)
                    if "cjone" not in (pg.url or "") and "login" not in (pg.url or "").lower():
                        pg.close()
            except Exception:
                pass
        ctx.on("page", on_page)

        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://cgv.co.kr/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2000)
        dismiss_ads(page)

        print("=" * 60)
        print("이 창에서 CGV(우측 상단 사람/메뉴 아이콘)에 로그인해 주세요.")
        print("로그인만 하시면 됩니다 — 완료되면 자동으로 저장되고 창이 닫힙니다.")
        print("(광고 팝업은 자동으로 닫으려 시도합니다. 남으면 그냥 두셔도 됩니다.)")
        print("=" * 60)
        sys.stdout.flush()

        deadline = time.time() + TIMEOUT_MIN * 60
        logged = None
        while time.time() < deadline:
            time.sleep(3)
            # 현재 활성 페이지(로그인 후 리다이렉트될 수 있음)에서 확인
            pages = [pg for pg in ctx.pages if not pg.is_closed()]
            if not pages:
                break
            cur = pages[-1]
            try:
                cur.bring_to_front()
            except Exception:
                pass
            dismiss_ads(cur)
            logged = is_logged_in(cur)
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
