@echo off
chcp 65001 >nul 2>&1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

REM "start_arena.bat check" runs the read-only pre-flight report and exits.
if /i "%~1"=="check" goto :check

echo ============================================================
echo   Prediction Arena - on-site launcher
echo ============================================================
echo.
where python >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python not found in PATH. Install Python 3 first.
  pause
  exit /b 1
)

echo [1/3] Pre-flight check...
python preflight.py
if errorlevel 1 (
  echo.
  echo [STOP] Blocking errors found. Fix them before starting.
  pause
  exit /b 1
)

echo.
echo [2/3] Starting server in a NEW window - DO NOT CLOSE IT.
start "Prediction Arena - DO NOT CLOSE" cmd /k "python app.py"

echo [3/3] Opening organizer dashboard...
timeout /t 3 >nul
start "" http://127.0.0.1:5000/dashboard

echo.
echo   Read the Phone URL printed in the server window and show it to the audience.
echo   Dashboard : http://127.0.0.1:5000/dashboard
echo   CSV export: only from 127.0.0.1 on this notebook.
echo   After the event: close the server window, then copy arena.db to keep the data.
echo.
pause
exit /b 0

:check
python preflight.py
exit /b %errorlevel%
