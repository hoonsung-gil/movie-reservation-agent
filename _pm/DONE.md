# DONE

### 2026-09-02 — 2단계: 오픈 감지 + 텔레그램 알림
텔레그램 연동 완료, 감시 루프 상시 가동 시작 (`scripts\run_watch.bat`)
- **배경**: 1단계 완료 후 사용자 결정(텔레그램 알림, 상시 실행 PC, 자동 예매는 보류)에 따라 진행
- **변경**: CGV 예매 API(극장 목록/날짜/상영시간표) 확보, watchlist 기반 감시 루프(오픈 알림 + 회차 발견 알림, 중복 방지, 임박 시 120초 주기), 텔레그램 발송(.env), CLI 커맨드 4종 추가. 봇 @movie_reservate_bot 연동·실발송 확인
- **파일**: `src/cgv/api.py`, `src/watcher.py`, `src/watchlist.py`, `src/notify.py`, `src/main.py`, `scripts/run_watch.bat`, `config/watchlist.example.yaml`, `.env.example`

### 2026-09-01 — 1단계: 예매 오픈일 추측 구현
CGV 무비차트 수집 + 예매 오픈일 추측 CLI 완성 (`python -m src.main upcoming`)
- **배경**: 영화 예매 자동화 프로젝트 1단계. CGV 예매 오픈 시점을 미리 알아야 2단계(알림)·3단계(자동 예매)가 가능
- **변경**: Playwright로 CGV 무비차트 페이지 접근(Cloudflare 우회, curl/requests는 403), 내부 API `searchScrDspCpotDtl` 응답 캡처 → 영화 104편(예매 미오픈 36편) 파싱. 스냅샷/오픈 이력 저장, 규칙 기반 오픈일 추측(일반 D-14, 대작 D-21, 이력 5건+ 쌓이면 중앙값 학습으로 자동 전환)
- **파일**: `src/cgv/browser.py`, `src/cgv/upcoming.py`, `src/predictor.py`, `src/storage.py`, `src/main.py`
