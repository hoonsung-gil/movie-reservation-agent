"""CGV same-origin API 호출 헬퍼.

cgv.co.kr/api/v1/* 는 Cloudflare 보호로 외부 HTTP 클라이언트는 403이지만,
Playwright로 연 CGV 페이지 컨텍스트 안에서 fetch하면 정상 호출된다.

사용 전 page가 cgv.co.kr 오리진에 있어야 한다 (아무 CGV 페이지나 goto 후 사용).
"""
CO_CD = "A420"

_FETCH_JS = """
async (url) => {
  const r = await fetch(url, { headers: { accept: "application/json" } });
  if (!r.ok) return { __http_error: r.status };
  return await r.json();
}
"""


class CgvApiError(RuntimeError):
    pass


class CgvApi:
    def __init__(self, page):
        self.page = page

    def _get(self, path: str) -> dict:
        res = self.page.evaluate(_FETCH_JS, path)
        if not isinstance(res, dict):
            raise CgvApiError(f"비정상 응답: {path} -> {res!r}")
        if "__http_error" in res:
            raise CgvApiError(f"HTTP {res['__http_error']}: {path}")
        if res.get("statusCode") != 0:
            raise CgvApiError(f"statusCode={res.get('statusCode')}: {path}")
        return res["data"]

    def theaters(self) -> list[dict]:
        """전국 극장 목록: [{siteNo, siteNm, regnGrpCd}]."""
        data = self._get(f"/api/v1/content/site/searchAllRegionAndSite?coCd={CO_CD}")
        return data["siteInfo"]

    def available_dates(self, site_no: str) -> list[str]:
        """해당 극장의 예매 가능 날짜(YYYYMMDD) 목록."""
        data = self._get(
            f"/api/v1/booking/searchSiteScnscYmdListBySite?coCd={CO_CD}&siteNo={site_no}"
        )
        return [d["scnYmd"] for d in data]

    def schedule(self, site_no: str, ymd: str) -> list[dict]:
        """극장+날짜의 상영시간표. 회차별 dict 목록."""
        data = self._get(
            f"/api/v1/booking/searchMovScnInfo?coCd={CO_CD}&siteNo={site_no}"
            f"&scnYmd={ymd}&rtctlScopCd=08"
        )
        return data or []
