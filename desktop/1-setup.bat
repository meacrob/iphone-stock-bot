@echo off
cd /d "%~dp0"
echo Installing the bot (takes 1-3 minutes)...
where python >nul 2>nul && (set PY=python) || (set PY=py)
%PY% -m pip install --upgrade pip
%PY% -m pip install playwright requests
%PY% -m playwright install chromium
echo.
echo Done! Next: open config.ini, paste your Telegram token, save. Then run 2-login.bat
pause
