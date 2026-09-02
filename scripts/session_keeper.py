"""CGV 로그인 세션 키퍼 (상시 실행).

CGV 웹 로그인은 세션 방식(브라우저 종료 = 로그아웃, 자동로그인 옵션 없음)이므로,
로그인한 브라우저를 계속 띄워두고 주기적으로 세션을 확인/유지한다.

- 시작하면 로그인 페이지가 열림 → 사용자가 로그인 (창은 절대 닫지 말 것, 최소화는 OK)
- 로그인 후: 5분마다 세션 확인(유지 겸용), 풀리면 텔레그램 알림
- CDP 포트(127.0.0.1:9222)를 열어두어 다른 스크립트(좌석 읽기/선점)가
  이 로그인된 브라우저에 접속해 작업할 수 있게 한다.
- 상태 파일: data/session_status.json

사용법: python scripts/session_keeper.py  (백그라운드 상시 실행)
"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.notify import send_telegram  # noqa: E402

PROFILE_DIR = ROOT / "data" / "browser_profile"
STATUS_PATH = ROOT / "data" / "session_status.json"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
LOGIN_URL = "https://cgv.co.kr/mem/login?returnUrl=%2F"
CHECK_URL = "https://cgv.co.kr/tme/tmeShowMore"
CDP_PORT = 9222
LOGIN_WAIT_MIN = 30
KEEPALIVE_SEC = 300


def write_status(**kw):
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    kw["updated_at"] = datetime.now().isoformat(timespec="seconds")
    STATUS_PATH.write_text(json.dumps(kw, ensure_ascii=False, indent=1), encoding="utf-8")


def check_session(ctx) -> bool:
    """새 탭에서 마이메뉴를 열어 로그인 유지 확인 (세션 keep-alive 겸용)."""
    pg = ctx.new_page()
    try:
        pg.goto(CHECK_URL, wait_until="domcontentloaded", timeout=30000)
        pg.wait_for_timeout(2500)
        txt = pg.evaluate("() => document.body.innerText")
        return "로그인하고 다양한" not in txt
    finally:
        try:
            pg.close()
        except Exception:
            pass


def main():
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR), headless=False, user_agent=UA,
            locale="ko-KR", viewport={"width": 1360, "height": 900},
            args=["--disable-blink-features=AutomationControlled",
                  "--disable-notifications",
                  f"--remote-debugging-port={CDP_PORT}"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
        print("=" * 60)
        print("로그인 페이지가 열렸습니다. 로그인해 주세요.")
        print("※ 이 창은 닫지 마세요! (최소화는 괜찮습니다)")
        print("  로그인 세션을 유지하는 창입니다. 닫으면 로그아웃됩니다.")
        print("=" * 60)
        sys.stdout.flush()
        write_status(state="waiting_login", cdp_port=CDP_PORT)

        # 1) 로그인 대기: 로그인 페이지를 벗어나면 성공으로 판단
        deadline = time.time() + LOGIN_WAIT_MIN * 60
        logged_in = False
        while time.time() < deadline:
            time.sleep(3)
            try:
                pages = [pg for pg in ctx.pages if not pg.is_closed()]
                if not pages:
                    print("브라우저가 닫혔습니다. 종료.")
                    write_status(state="browser_closed")
                    return 1
                if all("/mem/login" not in (pg.url or "") for pg in pages):
                    logged_in = True
                    break
            except Exception:
                pass
        if not logged_in:
            print("로그인 대기 시간 초과. 종료.")
            write_status(state="login_timeout")
            return 1

        # 로그인 직후 실제 세션 확인
        time.sleep(3)
        ok = check_session(ctx)
        print(f"✅ 로그인 감지. 세션 확인: {'정상' if ok else '비정상'}")
        write_status(state="logged_in" if ok else "unverified",
                     logged_in_at=datetime.now().isoformat(timespec="seconds"),
                     cdp_port=CDP_PORT)
        try:
            send_telegram("🔐 CGV 로그인 세션 확보! 세션 키퍼가 유지 중입니다. (창을 닫지 마세요)")
        except Exception:
            pass

        # 2) keep-alive 루프
        lost_alerted = False
        while True:
            time.sleep(KEEPALIVE_SEC)
            try:
                pages = [pg for pg in ctx.pages if not pg.is_closed()]
            except Exception:
                pages = []
            if not pages:
                print("브라우저가 닫혔습니다. 세션 종료.")
                write_status(state="browser_closed")
                try:
                    send_telegram("⚠️ CGV 세션 브라우저가 닫혔습니다. 재로그인이 필요합니다. (session_keeper 재실행)")
                except Exception:
                    pass
                return 1
            try:
                ok = check_session(ctx)
            except Exception as e:
                print("세션 확인 오류:", str(e)[:120])
                ok = False
            now = datetime.now().strftime("%H:%M:%S")
            if ok:
                print(f"[{now}] 세션 정상 (keep-alive)")
                write_status(state="logged_in", cdp_port=CDP_PORT)
                lost_alerted = False
            else:
                print(f"[{now}] ⚠️ 세션 풀림 감지")
                write_status(state="session_lost", cdp_port=CDP_PORT)
                if not lost_alerted:
                    try:
                        send_telegram("⚠️ CGV 로그인 세션이 풀렸습니다. 세션 키퍼 창에서 다시 로그인해 주세요.")
                    except Exception:
                        pass
                    lost_alerted = True
                # 재로그인 편의를 위해 로그인 페이지로 이동
                try:
                    pages[0].goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
                except Exception:
                    pass


if __name__ == "__main__":
    raise SystemExit(main())
