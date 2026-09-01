@echo off
rem 감시 루프 실행 + 로그 기록. Task Scheduler(로그온 시)에서 호출됨.
cd /d c:\Users\ghs12\OneDrive\.claude\project\movie-reservation-agent
python -m src.main watch >> data\watch.log 2>&1
