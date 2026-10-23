@echo off
cd /d "%~dp0"
title Duo auto-checkout bot - keep this window open
where python >nul 2>nul && (set PY=python) || (set PY=py)
:loop
%PY% duo_bot.py
echo Bot stopped, restarting in 10s...
timeout /t 10 >nul
goto loop
