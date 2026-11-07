@echo off
REM One-time setup: let phones on the LAN reach TCP 5000.
REM Self-elevates to administrator. Run once before the event, not every time.
net session >nul 2>&1
if %errorlevel% neq 0 (
  echo Requesting administrator privileges...
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

echo Adding inbound firewall rule for TCP 5000 ...
netsh advfirewall firewall delete rule name="Prediction Arena TCP 5000" >nul 2>&1
netsh advfirewall firewall add rule name="Prediction Arena TCP 5000" dir=in action=allow protocol=TCP localport=5000 profile=any
if %errorlevel% equ 0 (
  echo [OK] Rule added. Run "start_arena.bat check" to confirm.
) else (
  echo [FAIL] Could not add the rule. Right-click this file and Run as administrator.
)
pause
