@echo off
rem 감시 루프 실행 + 로그 기록. 시작프로그램(로그온 시)에서 호출됨.
cd /d c:\Users\ghs12\OneDrive\.claude\project\movie-reservation-agent
set PYTHONUNBUFFERED=1
set PYTHONIOENCODING=utf-8
python -m src.main watch >> data\watch.log 2>&1
