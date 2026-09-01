"""watchlist 설정 로드 및 매칭.

config/watchlist.yaml 형식:
  watches:
    - title: 레지던트 이블        # 영화명 부분 일치 (공백 무시)
      theaters: [강남, 용산아이파크몰]
      date_from: 2026-09-17     # 선택 — 없으면 모든 날짜
      date_to: 2026-09-20       # 선택 — 없으면 date_from과 동일
      time_from: "18:00"        # 선택 — 상영 시작시간 범위
      time_to: "23:00"
"""
from datetime import date
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "watchlist.yaml"


class WatchlistError(RuntimeError):
    pass


def normalize_title(s: str) -> str:
    return "".join((s or "").lower().split())


def load_watchlist(path: Path = CONFIG_PATH) -> list[dict]:
    if not path.exists():
        raise WatchlistError(
            f"watchlist 없음: {path}\n"
            f"config/watchlist.example.yaml을 복사해 작성해 주세요."
        )
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    watches = doc.get("watches") or []
    out = []
    for i, w in enumerate(watches):
        if not w.get("title"):
            raise WatchlistError(f"watches[{i}]: title 필수")
        theaters = w.get("theaters") or []
        if not theaters:
            raise WatchlistError(f"watches[{i}] ({w['title']}): theaters 필수")
        out.append(
            {
                "title": str(w["title"]),
                "theaters": [str(t) for t in theaters],
                "date_from": _as_date(w.get("date_from")),
                "date_to": _as_date(w.get("date_to")) or _as_date(w.get("date_from")),
                "time_from": _as_hhmm(w.get("time_from")),
                "time_to": _as_hhmm(w.get("time_to")),
            }
        )
    return out


def _as_date(v) -> date | None:
    if v is None:
        return None
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v))


def _as_hhmm(v) -> str | None:
    """'18:00' → '1800' (CGV scnsrtTm 형식)."""
    if v is None:
        return None
    s = str(v).replace(":", "").strip()
    if len(s) != 4 or not s.isdigit():
        raise WatchlistError(f"시간 형식 오류: {v!r} (예: '18:00')")
    return s


def title_matches(watch_title: str, movie_title: str) -> bool:
    a, b = normalize_title(watch_title), normalize_title(movie_title)
    return bool(a) and (a in b or b in a)


def session_matches(watch: dict, session: dict) -> bool:
    """시간표 회차가 watch의 시간대 조건에 맞는지. (심야 26:00 표기도 그대로 문자열 비교)"""
    start = session.get("scnsrtTm") or ""
    if watch["time_from"] and start < watch["time_from"]:
        return False
    if watch["time_to"] and start > watch["time_to"]:
        return False
    return True
