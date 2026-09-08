@echo off
setlocal
chcp 65001 >nul
if not exist "%~dp0.venv\Scripts\python.exe" (
    echo Python environment not found: %~dp0.venv\Scripts\python.exe
    echo See README.md for setup instructions.
    pause
    exit /b 1
)
"%~dp0.venv\Scripts\python.exe" -B -X utf8 "%~dp0run.py" --interactive %*
if errorlevel 1 (
    echo.
    echo Could not run the test. Check the error above.
    pause
    exit /b 1
)
