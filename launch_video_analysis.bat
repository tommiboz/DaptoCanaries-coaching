@echo off
title Dapto Canaries — Video Analysis Tool
cd /d "%~dp0"

echo ============================================================
echo   Dapto Canaries Video Analysis
echo ============================================================
echo.

:: Check Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.10+.
    pause
    exit /b 1
)

:: Check key dependencies
python -c "import PyQt6" >nul 2>&1
if errorlevel 1 (
    echo PyQt6 not found. Installing dependencies...
    pip install -r requirements_video.txt
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies.
        pause
        exit /b 1
    )
)

echo Starting Video Analysis tool...
echo.

python -m video_analysis.app

if errorlevel 1 (
    echo.
    echo The application exited with an error.
    pause
)
