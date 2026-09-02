"""감시 루프: watchlist 조건 충족 시 텔레그램 알림.

알림 이벤트:
  movie_open    — 영화가 예매 가능 상태로 확인됨 (영화 단위, 최초 1회)
  session_found — 원하는 극장/날짜/시간대에 상영 회차 등장 (극장+날짜 단위, 최초 1회)
"""
import json
import time
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path

from src.cgv.api import CgvApi
from src.cgv.browser import cgv_page
from src.cgv.upcoming import fetch_movie_chart, parse_movies
from src.notify import send_telegram, telegram_config
from src.predictor import predict_open
from src.storage import DATA_DIR, load_history, load_latest, save_snapshot, update_history
from src.watchlist import load_watchlist, normalize_title, session_matches, title_matches

STATE_PATH = DATA_DIR / "alert_state.json"
MAX_DATES_PER_THEATER = 16
WEEKDAYS_KO = ["월", "화", "수", "목", "금", "토", "일"]
FAST_INTERVAL = 120       # 오픈 예상일 임박 / 원하는 회차가 아직 안 열린 날짜가 남아있을 때
NEAR_OPEN_DAYS = 3
HORIZON_MARGIN_DAYS = 7   # 예매창 끝단 너머 이만큼까지를 "곧 열릴 날짜"로 보고 감시
CONSECUTIVE_FAIL_ALERT = 3


def _load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {}


def _save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def _fmt_time(hhmm: str) -> str:
    return f"{hhmm[:2]}:{hhmm[2:]}" if len(hhmm) == 4 else hhmm


def _ymd_to_date(ymd: str) -> date:
    return date(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:8]))


def _fmt_date(ymd: str) -> str:
    d = _ymd_to_date(ymd)
    return f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:]} ({WEEKDAYS_KO[d.weekday()]})"


def _target_dates(watch: dict, today: date, avail: list[str]) -> list[str]:
    """감시 대상 날짜(YYYYMMDD) 목록.

    오늘(또는 date_from)부터 '예매창 끝단 + margin'까지의 날짜 중 요일/날짜 조건에 맞는 것.
    예매창에 아직 없는(=곧 열릴) 날짜도 포함되므로, 이를 통해 '미오픈 잔여 날짜'를 감지한다.
    open-ended(날짜 미지정) watch도 예매창을 따라 horizon이 자동으로 굴러간다.
    """
    max_avail = max((_ymd_to_date(x) for x in avail), default=today)
    horizon_end = max_avail + timedelta(days=HORIZON_MARGIN_DAYS)

    d0 = max(watch["date_from"] or today, today)
    d1 = watch["date_to"] or horizon_end
    d1 = min(d1, horizon_end)  # open-ended는 horizon으로, 먼 미래 date_to도 horizon으로 캡

    out = []
    d = d0
    while d <= d1:
        if not watch.get("days") or d.weekday() in watch["days"]:
            out.append(d.strftime("%Y%m%d"))
        d += timedelta(days=1)
    return out[:MAX_DATES_PER_THEATER]


def run_cycle(verbose: bool = True) -> dict:
    """1회 수집+판정. 반환: {'alerts': [...], 'next_interval_hint': ...}"""
    now = datetime.now()
    alerts: list[str] = []
    state = _load_state()
    watches = load_watchlist()

    with cgv_page() as page:
        chart = fetch_movie_chart(page)
        movies = parse_movies(chart)
        api = CgvApi(page)

        prev = load_latest()
        save_snapshot(movies, now)
        update_history(movies, prev, now)
        history = load_history()
        today = now.date()

        theaters = {t["siteNm"]: t["siteNo"] for t in api.theaters()}
        near_open = False
        pending_future = False   # 원하는 조건의 회차가 아직 안 열린 날짜가 남아있음

        for watch in watches:
            wkey = normalize_title(watch["title"])
            matched = [m for m in movies if title_matches(watch["title"], m["title"])]
            if not matched:
                if verbose:
                    print(f"[{watch['title']}] 아직 차트에 없음")
                continue

            site_nos = {}
            for name in watch["theaters"]:
                site_no = theaters.get(name) or theaters.get(name.replace("CGV", "").strip())
                if site_no:
                    site_nos[name] = site_no
                else:
                    print(f"[경고] 극장명 매칭 실패: {name!r} — `theaters` 커맨드로 정확한 이름 확인")

            for m in matched:
                pred = predict_open(m, history, today)
                if not m["bookable"]:
                    if verbose:
                        p = pred.get("predicted_open")
                        print(f"[{watch['title']}] {m['title']}: 예매 미오픈 (예상 {p})")
                    if pred.get("days_until_open") is not None and pred["days_until_open"] <= NEAR_OPEN_DAYS:
                        near_open = True
                    continue

                key_open = f"movie_open:{wkey}:{m['mov_no']}"
                if key_open not in state:
                    alerts.append(
                        f"🎬 예매 오픈!\n"
                        f"영화: {m['title']}\n"
                        f"개봉일: {m['release_ymd']}\n"
                        f"CGV 전체 기준 예매 가능 상태입니다. 원하는 극장 회차를 확인 중..."
                    )
                    state[key_open] = now.isoformat(timespec="seconds")

                for name, site_no in site_nos.items():
                    try:
                        avail = api.available_dates(site_no)
                    except Exception as e:
                        print(f"[경고] {name} 날짜 조회 실패: {e}")
                        pending_future = True  # 확인 실패 → 계속 감시
                        continue
                    avail_set = set(avail)
                    new_days: list[tuple[str, list[dict]]] = []
                    for ymd in _target_dates(watch, today, avail):
                        key_sess = f"session_found:{wkey}:{site_no}:{ymd}"
                        if key_sess in state:
                            continue  # 이미 열려서 알림 보낸 날짜
                        if ymd not in avail_set:
                            pending_future = True  # 예매창에 아직 없는 날짜(곧 열림)
                            continue
                        try:
                            sessions = api.schedule(site_no, ymd)
                        except Exception as e:
                            print(f"[경고] {name} {ymd} 시간표 조회 실패: {e}")
                            pending_future = True
                            continue
                        hits = [
                            s for s in sessions
                            if s.get("movNo") == m["mov_no"] and session_matches(watch, s)
                        ]
                        if hits:
                            new_days.append((ymd, hits))
                            state[key_sess] = now.isoformat(timespec="seconds")
                        else:
                            pending_future = True  # 예매창엔 있으나 원하는 회차 아직 없음
                    if new_days:
                        blocks = []
                        for ymd, hits in new_days:
                            lines = [
                                f"  {_fmt_time(s['scnsrtTm'])} {s['scnsNm']} "
                                f"(잔여 {s['frSeatCnt']}/{s['stcnt']}석, {s.get('movkndDsplNm', '')})"
                                for s in hits[:6]
                            ]
                            blocks.append(f"📅 {_fmt_date(ymd)}\n" + "\n".join(lines))
                        alerts.append(
                            f"🍿 원하는 조건의 상영 회차 발견!\n"
                            f"영화: {m['title']}\n"
                            f"극장: CGV {name}\n"
                            + "\n".join(blocks)
                            + "\n예매: https://cgv.co.kr/cnm/movieBook"
                        )

    for msg in alerts:
        send_telegram(msg)
        if verbose:
            print("--- 알림 발송 ---")
            print(msg)
    _save_state(state)

    hint = FAST_INTERVAL if (near_open or pending_future) else None
    if verbose and hint:
        reason = "오픈 임박" if near_open else "미오픈 잔여 날짜 있음"
        print(f"[주기] 빠른 감시({FAST_INTERVAL}초) — {reason}")
    return {"alerts": alerts, "next_interval_hint": hint}


def run_watch(interval: int, once: bool = False) -> int:
    telegram_config()  # 설정 누락이면 시작 전에 바로 실패
    fails = 0
    while True:
        started = datetime.now()
        sleep_s = interval
        try:
            result = run_cycle()
            fails = 0
            if result["next_interval_hint"]:
                sleep_s = min(interval, result["next_interval_hint"])
        except KeyboardInterrupt:
            return 0
        except Exception:
            fails += 1
            print(f"[오류] 사이클 실패 ({fails}회 연속):")
            traceback.print_exc()
            if fails == CONSECUTIVE_FAIL_ALERT:
                try:
                    send_telegram(f"⚠️ movie-reservation-agent: 수집 {fails}회 연속 실패. PC/네트워크/사이트 구조 확인 필요.")
                except Exception:
                    pass
        if once:
            return 0
        print(f"[{started:%H:%M:%S}] 사이클 완료 — {sleep_s}초 대기")
        time.sleep(sleep_s)
