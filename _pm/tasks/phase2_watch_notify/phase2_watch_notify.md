# 2단계: 오픈 감지 + 텔레그램 알림

## 목적
사용자가 원하는 영화/영화관/날짜/시간대를 watchlist에 등록하면,
조건에 맞는 예매가 오픈되는 즉시 텔레그램으로 알림을 보낸다.

## 배경
- 1단계에서 무비차트 수집 + 오픈일 추측 구현 완료
- 사용자 결정: 알림은 텔레그램, 상시 실행 PC에서 구동, 자동 예매(3단계)는 보류

## 확보된 CGV API (2026-09-01 탐색)
모두 `https://cgv.co.kr/api/v1/*` (same-origin, Cloudflare 보호 → Playwright 페이지 컨텍스트 내 fetch로 호출)
- 극장 목록: `content/site/searchAllRegionAndSite?coCd=A420` → `data.siteInfo[]` = {siteNo, siteNm, regnGrpCd}
  - 예: 강남=0056, 강변=0001, 건대입구=0229, 용산아이파크몰(별도 확인 필요)
- 상영 가능 날짜: `booking/searchSiteScnscYmdListBySite?coCd=A420&siteNo=0056`
- 상영시간표: `booking/searchMovScnInfo?coCd=A420&siteNo=0056&scnYmd=20260901&rtctlScopCd=08`
  - 회차별: movNo, movNm, scnsNm(관), scnsrtTm(시작 HHMM), scnendTm, frSeatCnt(잔여석), stcnt(총좌석), salEndTm

## 설계
1. **watchlist**: `config/watchlist.yaml` (gitignore, example 제공)
   - 항목: title(부분일치), theaters[], date_from/date_to(선택), time_from/time_to(선택)
2. **감시 루프**: `python -m src.main watch [--interval 초]`
   - 매 사이클: 무비차트 수집(1단계 파이프라인 재사용) → watchlist 매칭 → 극장별 시간표 확인
   - 알림 이벤트 2종:
     a. `movie_open` — 영화가 예매 가능(atktPsblYn=Y) 전환
     b. `session_found` — 원하는 극장/날짜/시간대에 상영 회차 등장 (회차 상세 포함)
   - 중복 방지: `data/alert_state.json`에 발송 이력 기록
   - 적응형 주기: 오픈 예상일 3일 이내 영화가 있으면 짧은 주기, 아니면 기본 주기
3. **텔레그램**: `.env`의 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID, urllib 직접 호출(의존성 無)
   - `python -m src.main telegram-test`로 설정 확인

## 수정 대상 파일
- `src/cgv/api.py` (신규) — 페이지 컨텍스트 내 same-origin fetch 헬퍼
- `src/notify.py` (신규) — 텔레그램 발송
- `src/watchlist.py` (신규) — 설정 로드/매칭
- `src/watcher.py` (신규) — 감시 루프
- `src/main.py` — watch / telegram-test / theaters 커맨드 추가
- `config/watchlist.example.yaml`, `.env.example`

## 안전성 체크리스트
- [ ] 사이클당 API 호출 수 제한 (watch 항목 × 극장 × 날짜 범위 캡)
- [ ] 텔레그램 발송 실패 시 다음 사이클 재시도 (state 기록은 발송 성공 후)
- [ ] 크롤링 실패해도 루프 지속 (연속 실패 시 텔레그램으로 자체 경고)

## 미결정 사항
- 같은 (watch, 극장, 날짜)에 추가 회차가 나중에 더 열릴 때 재알림 여부 (현재: 최초 1회만)
