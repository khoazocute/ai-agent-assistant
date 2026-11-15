@echo off
rem Double-click this file to start the web app + Telegram bot + background jobs.
rem Keep this window OPEN while using the app. Close it (or Ctrl+C) to stop the server.
rem IMPORTANT: this file is kept 100%% plain ASCII on purpose - Vietnamese accents in a
rem .bat file can corrupt how cmd.exe parses later lines before "chcp 65001" takes effect.
set PYTHONIOENCODING=utf-8
cd /d "%~dp0backend"
title AI Agent server - http://localhost:8000
echo ============================================================
echo  Starting... open http://localhost:8000 in your browser
echo  Keep this window open. Close it (or Ctrl+C) to stop the server.
echo ============================================================
"%~dp0.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000

echo.
echo Server stopped. Press any key to close this window.
pause >nul
