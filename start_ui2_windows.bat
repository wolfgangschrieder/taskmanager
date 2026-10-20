@echo off
setlocal
cd /d "%~dp0"
echo Installing dependencies...
py -m pip install -r requirements.txt
if errorlevel 1 goto error
echo Starting APEX UI 2.0 preview...
py ui2.py
if errorlevel 1 goto error
exit /b 0
:error
echo.
echo APEX UI 2.0 could not start. Please copy the error above.
pause
exit /b 1
