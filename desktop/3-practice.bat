@echo off
cd /d "%~dp0"
where python >nul 2>nul && (set PY=python) || (set PY=py)
%PY% duo_bot.py practice
pause
