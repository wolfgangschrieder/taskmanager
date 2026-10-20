@echo off
setlocal
cd /d "%~dp0"
echo Installing dependencies...
py -m pip install -r requirements.txt
if errorlevel 1 goto error
echo Starting Manager Helper v1.1 preview...
py ui2.py
if errorlevel 1 goto error
exit /b 0
:error
echo.
echo Manager Helper v1.1 could not start. Please copy the error above.
pause
exit /b 1
