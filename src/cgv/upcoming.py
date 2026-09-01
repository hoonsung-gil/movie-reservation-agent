"""CGV 무비차트/상영예정작 수집.

무비차트 페이지(https://cgv.co.kr/cnm/cgvChart/movieChart)가 로드될 때
내부 API `searchScrDspCpotDtl` 응답을 캡처해 영화 목록을 얻는다.

응답 구조 (2026-09 기준):
  data.dspScrdispMovctTab.dspScrdispMovctDtlList[] — 탭(무비차트/현재상영작/상영예정/...)
    .movctSearchResDtoList[] — 영화 목록
      movNo        영화 번호
      movNm        영화명
      rlsYmd       개봉일 (YYYYMMDD 또는 YYYYMM — 미확정이면 월까지만)
      atktPsblYn   예매 가능 여부 (Y/N)  ← 오픈 감지의 핵심 필드
      atktRate     예매율(%)
      likeCount    기대해요/좋아요 수
      genr         장르
      movmdaTypeNmLstvalList  상영 포맷 (IMAX, 4DX 등)
"""
import json

CHART_URL = "https://cgv.co.kr/cnm/cgvChart/movieChart"
CHART_API_MARKER = "/met/dsp/scrDsp/searchScrDspCpotDtl"


class CgvStructureError(RuntimeError):
    """CGV 응답 구조가 예상과 다를 때 (사이트 개편 감지용)."""


def fetch_movie_chart(page) -> dict:
    """무비차트 페이지를 열고 차트 API 원본 JSON을 반환한다."""
    with page.expect_response(
        lambda r: CHART_API_MARKER in r.url and r.status == 200, timeout=60000
    ) as res_info:
        page.goto(CHART_URL, wait_until="domcontentloaded", timeout=60000)
    return res_info.value.json()


def parse_movies(chart_json: dict) -> list[dict]:
    """차트 API 응답에서 영화 목록을 추출한다. movNo 기준 중복 제거."""
    try:
        tabs = chart_json["data"]["dspScrdispMovctTab"]["dspScrdispMovctDtlList"]
    except (KeyError, TypeError) as e:
        raise CgvStructureError(f"차트 응답 구조 변경 감지: {e}") from e

    movies: dict[str, dict] = {}
    for tab in tabs:
        tab_name = (tab.get("tabExpoNm") or "").strip()
        for mv in tab.get("movctSearchResDtoList") or []:
            mov_no = mv.get("movNo")
            if not mov_no:
                continue
            formats = [
                f.get("movmdaTypeNm")
                for f in mv.get("movmdaTypeNmLstvalList") or []
                if f.get("movmdaTypeNm")
            ]
            entry = movies.setdefault(
                mov_no,
                {
                    "mov_no": mov_no,
                    "title": (mv.get("movNm") or "").strip(),
                    "release_ymd": mv.get("rlsYmd") or "",
                    "bookable": mv.get("atktPsblYn") == "Y",
                    "booking_rate": _to_float(mv.get("atktRate")),
                    "like_count": _to_int(mv.get("likeCount")),
                    "genre": mv.get("genr") or "",
                    "formats": formats,
                    "tabs": [],
                },
            )
            if tab_name and tab_name not in entry["tabs"]:
                entry["tabs"].append(tab_name)
    if not movies:
        raise CgvStructureError("영화 목록이 비어 있음 — 응답 구조 확인 필요")
    return list(movies.values())


def _to_float(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _to_int(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
