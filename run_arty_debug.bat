@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
set ARTY_DEBUG=1
python main.py
pause
