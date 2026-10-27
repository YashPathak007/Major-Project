@echo off
REM Touchless Controller v1.0.0 — run on Windows 10/11.
REM First run creates .venv and installs requirements.txt; later runs
REM just launch. To force a reinstall, delete the .venv folder first.
setlocal
cd /d %~dp0
if not exist .venv\Scripts\python.exe (
  echo Creating virtual environment...
  py -3 -m venv .venv
  if errorlevel 1 python -m venv .venv
  .venv\Scripts\python.exe -m pip install -q -U pip
  .venv\Scripts\python.exe -m pip install -q -r requirements.txt
)
set PYTHONPATH=%~dp0src
.venv\Scripts\python.exe -m touchless %*
