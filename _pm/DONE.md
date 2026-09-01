# DONE

### 2026-09-01 — 1단계: 예매 오픈일 추측 구현
CGV 무비차트 수집 + 예매 오픈일 추측 CLI 완성 (`python -m src.main upcoming`)
- **배경**: 영화 예매 자동화 프로젝트 1단계. CGV 예매 오픈 시점을 미리 알아야 2단계(알림)·3단계(자동 예매)가 가능
- **변경**: Playwright로 CGV 무비차트 페이지 접근(Cloudflare 우회, curl/requests는 403), 내부 API `searchScrDspCpotDtl` 응답 캡처 → 영화 104편(예매 미오픈 36편) 파싱. 스냅샷/오픈 이력 저장, 규칙 기반 오픈일 추측(일반 D-14, 대작 D-21, 이력 5건+ 쌓이면 중앙값 학습으로 자동 전환)
- **파일**: `src/cgv/browser.py`, `src/cgv/upcoming.py`, `src/predictor.py`, `src/storage.py`, `src/main.py`
