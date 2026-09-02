"""CGV 로그인 세션 키퍼 v2 (접속 방식, 상시 실행).

브라우저는 browser_launch.py가 '독립 프로세스'로 띄우고,
키퍼는 CDP로 접속만 한다 → 키퍼가 죽거나 재시작돼도 로그인 세션은 유지.

동작:
- CDP(9222)에 접속 (브라우저 없으면 자동 실행)
- 로그인 대기 (마이메뉴 확인) → 확인되면 텔레그램 알림
- 이후 5분마다 세션 확인(keep-alive), 풀리면 텔레그램 알림
- 브라우저가 닫히면: 자동 재실행 + 재로그인 요청 텔레그램
- 상태 파일: data/session_status.json (state: waiting_login | logged_in | session_lost | browser_down)

사용법: python scripts/session_keeper.py  (백그라운드 상시 실행)
"""
import json
import sys
import time
import traceback
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
from scripts.browser_launch import launch as launch_browser  # noqa: E402

STATUS_PATH = ROOT / "data" / "session_status.json"
CDP_URL = "http://127.0.0.1:9222"
CHECK_URL = "https://cgv.co.kr/tme/tmeShowMore"
KEEPALIVE_SEC = 300
LOGIN_POLL_SEC = 5


def write_status(state: str, **kw):
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    kw.update(state=state, updated_at=datetime.now().isoformat(timespec="seconds"))
    STATUS_PATH.write_text(json.dumps(kw, ensure_ascii=False, indent=1), encoding="utf-8")


def log(msg: str):
    print(f"[{datetime.now():%H:%M:%S}] {msg}")
    sys.stdout.flush()


def tg(msg: str):
    try:
        send_telegram(msg)
    except Exception as e:
        log(f"텔레그램 실패: {e}")


def check_session(ctx) -> bool:
    """새 탭에서 마이메뉴를 열어 로그인 유지 확인 (keep-alive 겸용)."""
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


def quiet_login_probe(ctx) -> bool:
    """로그인 대기용 무간섭 확인: 기존 페이지의 렌더 상태만 읽는다 (탭/포커스 안 건드림).

    로그인 성공 시 returnUrl로 이동한 CGV 페이지 푸터에 '로그아웃'이 표시됨.
    """
    for pg in ctx.pages:
        try:
            url = pg.url or ""
            if "cgv.co.kr" not in url or "/mem/login" in url:
                continue
            txt = pg.evaluate("() => document.body.innerText")
            if "로그아웃" in txt:
                return True
        except Exception:
            continue
    return False


def connect(p):
    """CDP 접속. 실패 시 브라우저 자동 실행 후 재시도."""
    for attempt in range(3):
        try:
            return p.chromium.connect_over_cdp(CDP_URL, timeout=10000)
        except Exception:
            if attempt == 0:
                log("CDP 접속 실패 — 브라우저 실행")
                try:
                    launch_browser()
                except Exception as e:
                    log(f"브라우저 실행 실패: {e}")
            time.sleep(5)
    raise RuntimeError("브라우저 CDP 접속 불가")


def main():
    log("세션 키퍼 v2 시작")
    while True:  # 브라우저 다운 시 재실행 루프
        try:
            with sync_playwright() as p:
                browser = connect(p)
                ctx = browser.contexts[0]
                log("CDP 접속 완료")

                # 1) 로그인 확인/대기 — 무간섭 확인(사용자 입력 방해 금지)
                announced = False
                while True:
                    if quiet_login_probe(ctx):
                        break
                    if not announced:
                        log("로그인 대기 중... (열린 창에서 로그인해 주세요)")
                        write_status("waiting_login")
                        announced = True
                    time.sleep(LOGIN_POLL_SEC)

                log("✅ 로그인 확인")
                write_status("logged_in", logged_in_at=datetime.now().isoformat(timespec="seconds"))
                tg("🔐 CGV 로그인 세션 확보! 키퍼가 유지 중입니다. (브라우저 창을 닫지 마세요)")

                # 2) keep-alive
                lost_alerted = False
                while True:
                    time.sleep(KEEPALIVE_SEC)
                    ok = check_session(ctx)  # 예외 → 바깥 루프 재접속
                    if ok:
                        log("세션 정상 (keep-alive)")
                        write_status("logged_in")
                        if lost_alerted:
                            tg("✅ CGV 세션이 다시 정상입니다.")
                            lost_alerted = False
                    else:
                        log("⚠️ 세션 풀림 감지")
                        write_status("session_lost")
                        if not lost_alerted:
                            tg("⚠️ CGV 로그인 세션이 풀렸습니다. 세션 브라우저에서 다시 로그인해 주세요.")
                            lost_alerted = True
        except KeyboardInterrupt:
            log("종료")
            return 0
        except Exception as e:
            log(f"브라우저 연결 문제: {str(e)[:150]}")
            traceback.print_exc()
            write_status("browser_down")
            tg("⚠️ CGV 세션 브라우저가 닫혔거나 응답하지 않습니다. 다시 실행하고 재로그인을 요청드립니다.")
            time.sleep(5)
            # 루프 계속 → connect()가 브라우저 재실행


if __name__ == "__main__":
    raise SystemExit(main())
