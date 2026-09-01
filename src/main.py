"""CLI 진입점.

사용법:
  python -m src.main upcoming            # 수집 + 오픈일 추측 리포트
  python -m src.main upcoming --json     # JSON 출력
  python -m src.main watch               # 감시 루프 (텔레그램 알림)
  python -m src.main watch --once        # 1사이클만 실행
  python -m src.main theaters 강남        # 극장명 검색 (siteNo 확인)
  python -m src.main telegram-test       # 텔레그램 설정 확인
  python -m src.main telegram-chat-id    # 봇이 받은 메시지에서 chat_id 확인
"""
import argparse
import json
import sys
from datetime import datetime

from src.cgv.browser import cgv_page
from src.cgv.upcoming import CgvStructureError, fetch_movie_chart, parse_movies
from src.predictor import predict_open
from src.storage import load_history, load_latest, save_snapshot, update_history


def cmd_upcoming(as_json: bool) -> int:
    now = datetime.now()
    try:
        with cgv_page() as page:
            chart = fetch_movie_chart(page)
        movies = parse_movies(chart)
    except CgvStructureError as e:
        print(f"[오류] {e}", file=sys.stderr)
        return 2

    prev = load_latest()
    snapshot_path = save_snapshot(movies, now)
    newly_opened = update_history(movies, prev, now)
    history = load_history()
    today = now.date()

    results = []
    for m in movies:
        pred = predict_open(m, history, today)
        results.append({**m, "prediction": pred})

    if as_json:
        print(json.dumps(results, ensure_ascii=False, indent=1, default=str))
        return 0

    print(f"수집 완료: 영화 {len(movies)}편 → {snapshot_path.name}")
    if newly_opened:
        print("\n★ 이번 수집에서 예매 오픈 감지:")
        for m in newly_opened:
            print(f"  - {m['title']} (개봉 {m['release_ymd']})")

    pending = [r for r in results if r["prediction"]["status"] == "predicted"]
    pending.sort(key=lambda r: r["prediction"]["predicted_open"])
    print(f"\n예매 미오픈 {len(pending)}편 — 오픈 예상일 순:")
    print(f"{'오픈예상':<12}{'D-day':>6}  {'개봉일':<12}{'신뢰도':<6}제목")
    for r in pending:
        p = r["prediction"]
        rel = p["release"].isoformat() if p["release_exact"] else p["release"].strftime("%Y-%m-??")
        dday = p["days_until_open"]
        dday_s = f"D-{dday}" if dday > 0 else ("오늘!" if dday == 0 else f"D+{-dday}")
        print(f"{p['predicted_open'].isoformat():<12}{dday_s:>6}  {rel:<12}{p['confidence']:<6}{r['title']}")

    stale = [r for r in results if r["prediction"]["status"] == "stale"]
    if stale:
        print(f"\n개봉일 경과(재개봉/특별상영) {len(stale)}편: " + ", ".join(r["title"] for r in stale))

    unknown = [r for r in results if r["prediction"]["status"] == "unknown"]
    if unknown:
        print(f"\n개봉일 미상 {len(unknown)}편: " + ", ".join(r["title"] for r in unknown))
    return 0


def cmd_theaters(query: str) -> int:
    from src.cgv.api import CgvApi

    with cgv_page() as page:
        page.goto("https://cgv.co.kr/cnm/movieBook", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2000)
        theaters = CgvApi(page).theaters()
    q = (query or "").strip()
    hits = [t for t in theaters if q in t["siteNm"]] if q else theaters
    for t in hits:
        print(f"{t['siteNo']}  {t['siteNm']}")
    if not hits:
        print(f"'{q}' 매칭 극장 없음")
    return 0


def cmd_telegram_test() -> int:
    from src.notify import send_telegram

    send_telegram("✅ movie-reservation-agent 텔레그램 연결 테스트 성공!")
    print("발송 완료 — 텔레그램을 확인해 주세요.")
    return 0


def cmd_telegram_chat_id() -> int:
    from src.notify import get_updates

    updates = get_updates()
    if not updates:
        print("수신 메시지 없음 — 텔레그램에서 봇에게 아무 메시지나 먼저 보내주세요.")
        return 1
    for u in updates[-5:]:
        msg = u.get("message") or u.get("edited_message") or {}
        chat = msg.get("chat", {})
        print(f"chat_id={chat.get('id')}  이름={chat.get('first_name', '')} {chat.get('username', '')}")
    print("\n위 chat_id를 .env의 TELEGRAM_CHAT_ID에 넣어주세요.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="movie-reservation-agent")
    sub = parser.add_subparsers(dest="command", required=True)

    up = sub.add_parser("upcoming", help="개봉예정작 수집 + 오픈일 추측")
    up.add_argument("--json", action="store_true", help="JSON 출력")

    watch = sub.add_parser("watch", help="watchlist 감시 루프 (텔레그램 알림)")
    watch.add_argument("--interval", type=int, default=600, help="기본 주기(초), 기본 600")
    watch.add_argument("--once", action="store_true", help="1사이클만 실행")

    th = sub.add_parser("theaters", help="극장명 검색 (siteNo 확인)")
    th.add_argument("query", nargs="?", default="", help="극장명 일부 (생략 시 전체)")

    sub.add_parser("telegram-test", help="텔레그램 발송 테스트")
    sub.add_parser("telegram-chat-id", help="봇 수신 메시지에서 chat_id 확인")

    args = parser.parse_args()

    if args.command == "upcoming":
        return cmd_upcoming(args.json)
    if args.command == "watch":
        from src.watcher import run_watch

        return run_watch(args.interval, args.once)
    if args.command == "theaters":
        return cmd_theaters(args.query)
    if args.command == "telegram-test":
        return cmd_telegram_test()
    if args.command == "telegram-chat-id":
        return cmd_telegram_chat_id()
    return 1


if __name__ == "__main__":
    sys.exit(main())
