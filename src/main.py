"""CLI 진입점.

사용법:
  python -m src.main upcoming          # 수집 + 오픈일 추측 리포트
  python -m src.main upcoming --json   # JSON 출력
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


def main() -> int:
    parser = argparse.ArgumentParser(prog="movie-reservation-agent")
    sub = parser.add_subparsers(dest="command", required=True)
    up = sub.add_parser("upcoming", help="개봉예정작 수집 + 오픈일 추측")
    up.add_argument("--json", action="store_true", help="JSON 출력")
    args = parser.parse_args()

    if args.command == "upcoming":
        return cmd_upcoming(args.json)
    return 1


if __name__ == "__main__":
    sys.exit(main())
