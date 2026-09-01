"""스냅샷 저장 및 예매 오픈 이력 관리.

data/
├── snapshots/{YYYYMMDD_HHMMSS}.json  # 수집 시점별 영화 목록
├── latest.json                        # 마지막 스냅샷 (비교용)
└── open_history.json                  # 영화별 예매 오픈 감지 이력
"""
import json
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SNAPSHOT_DIR = DATA_DIR / "snapshots"
LATEST_PATH = DATA_DIR / "latest.json"
HISTORY_PATH = DATA_DIR / "open_history.json"


def load_latest() -> list[dict] | None:
    if LATEST_PATH.exists():
        return json.loads(LATEST_PATH.read_text(encoding="utf-8"))["movies"]
    return None


def save_snapshot(movies: list[dict], now: datetime) -> Path:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"fetched_at": now.isoformat(timespec="seconds"), "movies": movies}
    text = json.dumps(payload, ensure_ascii=False, indent=1)
    path = SNAPSHOT_DIR / f"{now:%Y%m%d_%H%M%S}.json"
    path.write_text(text, encoding="utf-8")
    LATEST_PATH.write_text(text, encoding="utf-8")
    return path


def load_history() -> dict:
    if HISTORY_PATH.exists():
        return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    return {}


def update_history(movies: list[dict], prev: list[dict] | None, now: datetime) -> list[dict]:
    """이전 스냅샷과 비교해 오픈 이력을 갱신하고, 새로 오픈된 영화 목록을 반환한다.

    - 처음 보는 영화: first_seen 기록 (이미 bookable이면 오픈 시점은 알 수 없음 → opened_at=None, pre_open=False)
    - 예매불가 → 예매가능 전환: opened_at 기록 (pre_open=True — 미오픈 상태부터 관찰한 신뢰할 수 있는 데이터)
    """
    history = load_history()
    prev_map = {m["mov_no"]: m for m in prev} if prev else {}
    ts = now.isoformat(timespec="seconds")
    newly_opened = []

    for m in movies:
        h = history.setdefault(
            m["mov_no"],
            {
                "title": m["title"],
                "release_ymd": m["release_ymd"],
                "first_seen": ts,
                "seen_unbookable": not m["bookable"],
                "opened_at": None,
            },
        )
        h["title"] = m["title"]
        h["release_ymd"] = m["release_ymd"] or h.get("release_ymd", "")
        if not m["bookable"]:
            h["seen_unbookable"] = True
        was_bookable = prev_map.get(m["mov_no"], {}).get("bookable")
        if m["bookable"] and was_bookable is False and h["opened_at"] is None:
            h["opened_at"] = ts
            newly_opened.append(m)

    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(
        json.dumps(history, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return newly_opened
