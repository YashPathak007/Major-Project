@echo off
REM Rebuild the distributable zip (..\touchless-v1-1.0.0.zip) from this
REM folder. Excludes __pycache__ and any .venv. Requires PowerShell.
setlocal
cd /d %~dp0
if exist .build-stage rmdir /s /q .build-stage
mkdir .build-stage
robocopy src .build-stage\src /E /XD __pycache__ >nul
if errorlevel 8 goto :fail
robocopy models .build-stage\models /E >nul
if errorlevel 8 goto :fail
robocopy tests .build-stage\tests /E /XD __pycache__ >nul
if errorlevel 8 goto :fail
copy /Y README.md .build-stage\ >nul
copy /Y BUILD_NOTES.md .build-stage\ >nul
copy /Y TEST_REPORT.md .build-stage\ >nul
copy /Y requirements.txt .build-stage\ >nul
copy /Y requirements-dev.txt .build-stage\ >nul
copy /Y run.bat .build-stage\ >nul
copy /Y run.sh .build-stage\ >nul
copy /Y build.bat .build-stage\ >nul
if exist ..\touchless-v1-1.0.0.zip del ..\touchless-v1-1.0.0.zip
powershell -NoProfile -Command "Compress-Archive -Path .build-stage\* -DestinationPath ..\touchless-v1-1.0.0.zip"
rmdir /s /q .build-stage
echo Built ..\touchless-v1-1.0.0.zip
goto :eof
:fail
echo Build failed (robocopy error).
rmdir /s /q .build-stage 2>nul
exit /b 1
