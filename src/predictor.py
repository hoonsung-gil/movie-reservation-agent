"""예매 오픈일 추측.

규칙 기반 초기값:
  - 일반 영화: 개봉일 D-14
  - 대작(기대 수 높음 또는 IMAX/4DX 동시 개봉): 개봉일 D-21
이력 보정:
  - open_history.json에 "미오픈 → 오픈" 전환이 관찰된 표본이 5개 이상 쌓이면
    실측 리드타임의 중앙값으로 기본 리드타임을 대체한다.

개봉일이 YYYYMM(일 미정)인 영화는 해당 월 1일로 가정하고 신뢰도 low로 표시.
"""
from datetime import date, timedelta
from statistics import median

DEFAULT_LEAD_DAYS = 14
BLOCKBUSTER_LEAD_DAYS = 21
BLOCKBUSTER_LIKE_COUNT = 20000
BLOCKBUSTER_FORMATS = {"IMAX", "4DX", "SCREENX"}
MIN_SAMPLES_FOR_LEARNED_LEAD = 5


def parse_release(ymd: str) -> tuple[date | None, bool]:
    """(개봉일, 일자 확정 여부). YYYYMM이면 1일로 가정."""
    ymd = (ymd or "").strip()
    try:
        if len(ymd) == 8:
            return date(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:8])), True
        if len(ymd) == 6:
            return date(int(ymd[:4]), int(ymd[4:6]), 1), False
    except ValueError:
        pass
    return None, False


def learned_lead_days(history: dict) -> int | None:
    """오픈 전환이 실측된 표본들의 리드타임(개봉일-오픈일) 중앙값."""
    leads = []
    for h in history.values():
        if not h.get("opened_at") or not h.get("seen_unbookable"):
            continue
        release, exact = parse_release(h.get("release_ymd", ""))
        if not release or not exact:
            continue
        opened = date.fromisoformat(h["opened_at"][:10])
        lead = (release - opened).days
        if 0 < lead < 90:
            leads.append(lead)
    if len(leads) >= MIN_SAMPLES_FOR_LEARNED_LEAD:
        return round(median(leads))
    return None


def is_blockbuster(movie: dict) -> bool:
    if (movie.get("like_count") or 0) >= BLOCKBUSTER_LIKE_COUNT:
        return True
    formats = {f.upper() for f in movie.get("formats") or []}
    return bool(formats & BLOCKBUSTER_FORMATS)


def predict_open(movie: dict, history: dict, today: date) -> dict:
    """영화 하나의 예매 오픈일 추측 결과를 반환한다."""
    release, exact = parse_release(movie.get("release_ymd", ""))
    if movie.get("bookable"):
        return {"status": "opened", "release": release}
    if release is None:
        return {"status": "unknown", "release": None}
    if release < today:
        # 개봉일이 이미 지난 항목(재개봉/특별상영/기획전) — 리드타임 예측 부적합
        return {"status": "stale", "release": release}

    base = learned_lead_days(history)
    confidence = "mid" if base else "rule"
    lead = base or DEFAULT_LEAD_DAYS
    if is_blockbuster(movie):
        lead = max(lead, BLOCKBUSTER_LEAD_DAYS)
    if not exact:
        confidence = "low"

    predicted = release - timedelta(days=lead)
    return {
        "status": "predicted",
        "release": release,
        "release_exact": exact,
        "predicted_open": predicted,
        "lead_days": lead,
        "confidence": confidence,
        "days_until_open": (predicted - today).days,
    }
