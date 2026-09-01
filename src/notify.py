"""텔레그램 알림 발송.

프로젝트 루트 .env에서 설정을 읽는다:
  TELEGRAM_BOT_TOKEN=123456:ABC-...
  TELEGRAM_CHAT_ID=987654321
"""
import json
import urllib.parse
import urllib.request
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


class NotifyConfigError(RuntimeError):
    pass


def load_env() -> dict[str, str]:
    env = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


def telegram_config() -> tuple[str, str]:
    env = load_env()
    token = env.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = env.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        raise NotifyConfigError(
            f".env에 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID를 설정해 주세요 (경로: {ENV_PATH})"
        )
    return token, chat_id


def send_telegram(text: str) -> None:
    """텔레그램 메시지 발송. 실패 시 예외."""
    token, chat_id = telegram_config()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    req = urllib.request.Request(url, data=payload)
    with urllib.request.urlopen(req, timeout=15) as res:
        body = json.loads(res.read().decode())
    if not body.get("ok"):
        raise RuntimeError(f"텔레그램 발송 실패: {body}")


def get_updates() -> list[dict]:
    """봇의 최근 수신 메시지 (chat_id 확인용)."""
    env = load_env()
    token = env.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise NotifyConfigError(f".env에 TELEGRAM_BOT_TOKEN을 설정해 주세요 (경로: {ENV_PATH})")
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    with urllib.request.urlopen(url, timeout=15) as res:
        body = json.loads(res.read().decode())
    return body.get("result", [])
