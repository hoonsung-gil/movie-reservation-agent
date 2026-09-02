"""로그인 세션 유효기간(타임아웃) 확인.

전용 프로필의 CGV/CJ ONE 인증 쿠키 만료시각을 읽어,
'언제까지 재로그인 없이 예매 가능한지'를 추정한다.

주의: 쿠키 만료(절대 만료) 외에 서버측 '유휴 타임아웃'이 따로 있을 수 있음.
쿠키 만료는 상한선(그 전에 유휴로 끊길 수도 있음)으로 이해할 것.
"""
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

PROFILE_DIR = Path(__file__).resolve().parent.parent / "data" / "browser_profile"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
AUTH_HINTS = ("sso", "token", "auth", "login", "jsession", "access", "refresh",
              "cjone", "oidc", "sid", "mbr", "session")


def main():
    if not PROFILE_DIR.exists():
        print("프로필 없음 — 먼저 python scripts/login_setup.py 로 로그인하세요.")
        return 1
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR), headless=True, user_agent=UA,
            locale="ko-KR", args=["--disable-blink-features=AutomationControlled"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://cgv.co.kr/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1500)
        sso = page.evaluate("""async () => {
            try { const r = await fetch('https://oidc.cgv.co.kr/cjone/getCjssoq?ssoCheck=Y',{credentials:'include'}); return await r.json(); }
            catch(e){ return {err:''+e}; }
        }""")
        mbr = (sso.get("data") or {}).get("ssoMbrNo")
        print("로그인 상태:", "✅ 로그인됨 (회원번호 %s)" % mbr if mbr else "❌ 미로그인 — 먼저 로그인하세요")

        cookies = ctx.cookies()
        now = datetime.now(timezone.utc)
        print(f"\n총 쿠키 {len(cookies)}개. 인증 관련/만료 있는 쿠키:")
        rows = []
        for c in cookies:
            name = c.get("name", "")
            exp = c.get("expires", -1)
            is_auth = any(h in name.lower() or h in c.get("domain", "").lower() for h in AUTH_HINTS)
            if exp and exp > 0:
                dt = datetime.fromtimestamp(exp, tz=timezone.utc)
                left = dt - now
                rows.append((dt, name, c.get("domain"), left, is_auth))
            elif is_auth:
                rows.append((None, name, c.get("domain"), None, is_auth))

        rows.sort(key=lambda r: (r[0] is None, r[0] or now))
        for dt, name, dom, left, is_auth in rows:
            mark = "🔑" if is_auth else "  "
            if dt is None:
                print(f"  {mark} {name} @{dom} — 세션쿠키(브라우저 종료 시 만료 가능)")
            else:
                hrs = left.total_seconds() / 3600
                loc = dt.astimezone()
                print(f"  {mark} {name} @{dom} — 만료 {loc:%Y-%m-%d %H:%M} (약 {hrs:.1f}시간 후)")

        auth_exp = [r[0] for r in rows if r[4] and r[0]]
        if auth_exp:
            earliest = min(auth_exp)
            loc = earliest.astimezone()
            hrs = (earliest - now).total_seconds() / 3600
            print(f"\n▶ 인증 쿠키 최단 만료: {loc:%Y-%m-%d %H:%M} (약 {hrs:.1f}시간 후)")
            print("  = 늦어도 이 시각 전에 로그인돼 있어야 안전 (유휴 타임아웃은 더 짧을 수 있음)")
        else:
            print("\n▶ 만료시각이 있는 인증 쿠키를 못 찾음 — 세션쿠키 위주일 수 있음(브라우저 유지 필요)")
        ctx.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
