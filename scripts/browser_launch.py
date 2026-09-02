"""CGV 세션용 크롬을 '독립 프로세스'로 실행.

어떤 파이썬/Playwright 스크립트에도 종속되지 않으므로,
키퍼나 좌석 스크립트가 죽거나 재시작돼도 브라우저(=로그인 세션)는 유지된다.
브라우저가 닫히는 경우는 사용자가 창을 닫거나 PC를 재부팅할 때뿐.

CDP: 127.0.0.1:9222 (로컬 전용)
"""
import subprocess
import sys
from glob import glob
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
PROFILE_DIR = ROOT / "data" / "browser_profile"
LOGIN_URL = "https://cgv.co.kr/mem/login?returnUrl=%2F"
CDP_PORT = 9222

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200


def find_chrome() -> str:
    home = Path.home() / "AppData" / "Local" / "ms-playwright"
    hits = glob(str(home / "chromium-*" / "chrome-win*" / "chrome.exe"))
    if not hits:
        raise FileNotFoundError("Playwright Chromium을 찾을 수 없음 — playwright install chromium 필요")
    return sorted(hits)[-1]


def launch() -> int:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    chrome = find_chrome()
    proc = subprocess.Popen(
        [
            chrome,
            f"--user-data-dir={PROFILE_DIR}",
            f"--remote-debugging-port={CDP_PORT}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-blink-features=AutomationControlled",
            "--disable-notifications",
            "--window-size=1360,900",
            LOGIN_URL,
        ],
        creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )
    print(f"브라우저 실행 (독립 프로세스, pid={proc.pid}, CDP {CDP_PORT})")
    return proc.pid


if __name__ == "__main__":
    launch()
