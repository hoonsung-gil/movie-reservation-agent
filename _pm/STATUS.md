# STATUS

## Claude 마지막 확인
2026-09-01 22:26:08

## 현재 상태
- 1단계(오픈일 추측) 구현 완료. `python -m src.main upcoming`으로 수집+추측 리포트 출력.
- CGV 신규 사이트(cgv.co.kr/cnm/*)는 Cloudflare 보호 → 단순 HTTP 불가, Playwright 사용.
- 오픈 이력 학습은 주기 실행으로 데이터가 쌓이면(전환 실측 5건+) 자동 활성화.
- 다음: 2단계(watchlist 등록 + 오픈 감지 알림). 알림 수단 결정 필요.

## 최근 변경
### 🔶 1단계 CGV 예매 오픈일 추측 구현 (2026-09-01, 0f68f7a)
- Playwright 기반 CGV 무비차트 수집, 오픈 감지/이력 저장, 규칙+학습 기반 오픈일 추측 CLI
