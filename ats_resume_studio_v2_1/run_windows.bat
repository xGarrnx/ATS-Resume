@echo off
cd /d "%~dp0"
set PY=python
where py >nul 2>nul && set PY=py
%PY% app.py
if errorlevel 1 (
  echo.
  echo The app closed with an error. Did you run install_requirements.bat first?
  pause
)
