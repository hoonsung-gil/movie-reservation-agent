"""watchlist 설정 로드 및 매칭.

config/watchlist.yaml 형식:
  watches:
    - title: 레지던트 이블        # 영화명 부분 일치 (공백 무시)
      theaters: [강남, 용산아이파크몰]
      date_from: 2026-09-17     # 선택 — 없으면 모든 날짜
      date_to: 2026-09-20       # 선택 — 없으면 date_from과 동일
      time_from: "18:00"        # 선택 — 상영 시작시간 범위
      time_to: "23:00"
      days: [토, 일]             # 선택 — 요일 필터 (월~일 또는 mon~sun)
      screen: IMAX              # 선택 — 상영관/포맷 필터 (관 이름 또는 포맷명에 포함, 대소문자 무시)
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
                "days": _as_days(w.get("days")),
                "screen": str(w["screen"]).strip() if w.get("screen") else None,
            }
        )
    return out


_DAY_TOKENS = {
    "월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6,
    "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
}


def _as_days(v) -> set[int] | None:
    """요일 목록 → weekday 정수 집합 (월=0 ... 일=6)."""
    if not v:
        return None
    days = set()
    for tok in v:
        t = str(tok).strip().lower()[:3]
        t = t if t in _DAY_TOKENS else str(tok).strip()[0]
        if t not in _DAY_TOKENS:
            raise WatchlistError(f"요일 형식 오류: {tok!r} (예: 토, 일, sat, sun)")
        days.add(_DAY_TOKENS[t])
    return days


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
    """시간표 회차가 watch의 시간대/상영관 조건에 맞는지. (심야 26:00 표기도 그대로 문자열 비교)"""
    start = session.get("scnsrtTm") or ""
    if watch["time_from"] and start < watch["time_from"]:
        return False
    if watch["time_to"] and start > watch["time_to"]:
        return False
    if watch.get("screen"):
        target = watch["screen"].lower()
        haystack = f"{session.get('scnsNm', '')} {session.get('movkndDsplNm', '')}".lower()
        if target not in haystack:
            return False
    return True
