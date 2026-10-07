@echo off
setlocal enabledelayedexpansion
title Women Safety Project v2 - Live Stream System
echo ============================================================
echo   Women Safety Project v2 - Live Stream Relay and IoT Cloud
echo ============================================================
echo.

:: 1. Auto-detect Python executable across Anaconda and system
set "PY_CMD="

:: Check developer's Anaconda env if available
if exist "C:\Users\OVIYA\anaconda3\envs\myenv\python.exe" (
    set "PY_CMD=C:\Users\OVIYA\anaconda3\envs\myenv\python.exe"
)

if not defined PY_CMD if exist "C:\Users\OVIYA\anaconda3\envs\espenv\python.exe" (
    set "PY_CMD=C:\Users\OVIYA\anaconda3\envs\espenv\python.exe"
)

if not defined PY_CMD if exist "C:\Users\OVIYA\anaconda3\python.exe" (
    set "PY_CMD=C:\Users\OVIYA\anaconda3\python.exe"
)

if not defined PY_CMD if defined CONDA_PREFIX (
    set "PY_CMD=%CONDA_PREFIX%\python.exe"
)

if not defined PY_CMD (
    python --version >nul 2>&1
    if !errorlevel! equ 0 set "PY_CMD=python"
)

if not defined PY_CMD (
    echo [ERROR] Python was not found on this computer!
    pause
    exit /b 1
)

echo [Environment] Python: !PY_CMD!

:: 2. Auto-verify dependencies (Flask, OpenCV, NumPy)
"!PY_CMD!" -c "import flask, cv2, numpy" >nul 2>&1
if !errorlevel! neq 0 (
    echo.
    echo [Setup] First-time setup detected on this computer!
    echo [Setup] Installing required libraries (Flask, OpenCV, NumPy)...
    "!PY_CMD!" -m pip install -r "%~dp0requirements.txt"
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to install dependencies. Check your internet connection.
        pause
        exit /b 1
    )
    echo [Setup] Dependencies installed successfully!
    echo.
)

echo [System] Starting Auto-Discovery, Cloudflare Tunnel and IoT Uploader...
echo.

:: 3. Launch unified app.py
"!PY_CMD!" "%~dp0app.py"

echo.
echo Application closed.
pause
