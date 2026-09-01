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
```

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
