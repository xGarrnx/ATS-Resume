@echo off
cd /d "%~dp0"
set PY=python
where py >nul 2>nul && set PY=py
echo Installing Python packages...
%PY% -m pip install --upgrade pip
%PY% -m pip install -r requirements.txt
echo.
echo Installing the backup browser used for job import...
%PY% -m playwright install chromium
echo.
echo Done. Now double-click run_windows.bat
pause
