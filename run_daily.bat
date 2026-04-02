@echo off
setlocal

cd /d D:\Projects\aav-research-agent

if not exist logs mkdir logs

echo [%date% %time%] Starting daily pipeline >> logs\daily_run.log

call .venv\Scripts\activate.bat
python main.py >> logs\daily_run.log 2>&1

echo [%date% %time%] Finished daily pipeline >> logs\daily_run.log
echo. >> logs\daily_run.log

endlocal