# movie-reservation-agent

CGV 영화 예매 자동화 에이전트.

## 단계별 목표

1. **오픈일 추측** — CGV 개봉예정작을 주기적으로 수집하고, 예매 오픈 시점을 추측
2. **오픈 감지 + 알림** — 사용자가 원하는 영화/영화관/시간대를 등록하면, 해당 조건의 예매가 오픈될 때 알림
3. **자동 예매** — 오픈 감지 즉시 예매까지 자동 진행

## 기술 스택

- Python 3.12
- Playwright (CGV는 Cloudflare 뒤에 있어 실제 브라우저 필요)
- 데이터 저장: JSON 스냅샷 (`data/`)

## 사용법

```bash
pip install -r requirements.txt
playwright install chromium

# 개봉예정작 수집 + 오픈일 추측
python -m src.main upcoming

# 극장명/siteNo 검색
python -m src.main theaters 강남

# 감시 루프 (watchlist 기반, 텔레그램 알림) — 상시 실행 PC에서
python -m src.main watch              # 기본 10분 주기, 오픈 임박 시 2분으로 단축
python -m src.main watch --once       # 1사이클만 (테스트용)
```

### 텔레그램 설정 (최초 1회)

1. 텔레그램에서 `@BotFather`에게 `/newbot` → 봇 생성, 토큰 복사
2. `.env.example`을 `.env`로 복사하고 `TELEGRAM_BOT_TOKEN`에 토큰 입력
3. 생성한 봇에게 아무 메시지나 1개 전송
4. `python -m src.main telegram-chat-id` → 출력된 chat_id를 `.env`의 `TELEGRAM_CHAT_ID`에 입력
5. `python -m src.main telegram-test` → 텔레그램으로 테스트 메시지 도착하면 완료

### watchlist 설정

`config/watchlist.example.yaml`을 `config/watchlist.yaml`로 복사해 원하는 영화/극장/날짜/시간대를 등록합니다.

### 상시 실행 (Windows)

- 수동 시작: `scripts\run_watch.bat` 더블클릭 (로그: `data\watch.log`)
- **로그온 시 자동 시작 등록**: `Win+R` → `shell:startup` 입력 → 열린 폴더에 `scripts\run_watch.bat`의 **바로가기**를 복사해 넣기

### 알림 동작

- **예매 오픈**: 등록한 영화가 CGV에서 예매 가능 상태가 되면 즉시 알림
- **회차 발견**: 원하는 극장/날짜/시간대에 상영 회차가 열리면 회차·잔여석 상세와 함께 알림
- 같은 내용은 한 번만 발송 (`data/alert_state.json`에 이력 기록)
- 수집 3회 연속 실패 시 자체 경고 알림

## 디렉토리

```
src/
├── cgv/            # CGV 크롤러 (Playwright)
├── predictor.py    # 예매 오픈일 추측 로직
├── storage.py      # 스냅샷 저장/이력 관리
└── main.py         # CLI 진입점
config/             # 사용자 관심 영화 설정 (watchlist)
data/               # 크롤링 스냅샷 (git 제외)
_pm/                # 프로젝트 관리 문서
```
