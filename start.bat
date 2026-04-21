@echo off
title SmartCompare Launcher
echo.
echo  ============================================
echo   SmartCompare -- AI Grocery Price Comparison
echo   CSCE 5200 - Group 7
echo  ============================================
echo.

REM ── Check Python ──────────────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+
    pause & exit /b 1
)

REM ── Check Node ────────────────────────────────────────────────────────────
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found. Please install Node.js 18+
    pause & exit /b 1
)

REM ── Install Python deps (first time only) ─────────────────────────────────
echo [1/3] Checking Python dependencies...
pip install -r requirements.txt -q

REM ── Install Node deps (first time only) ──────────────────────────────────
echo [2/3] Checking frontend dependencies...
cd frontend
if not exist node_modules (
    echo       Installing npm packages...
    npm install --silent
)
cd ..

REM ── Start Backend API ─────────────────────────────────────────────────────
echo [3/3] Starting servers...
start "SmartCompare API (port 8000)" cmd /k ^
    "cd /d "%~dp0api" && uvicorn server:app --reload --host 127.0.0.1 --port 8000"

REM ── Wait for API to boot ──────────────────────────────────────────────────
timeout /t 3 /nobreak >nul

REM ── Start Frontend ────────────────────────────────────────────────────────
start "SmartCompare Frontend (port 5173)" cmd /k ^
    "cd /d "%~dp0frontend" && npm run dev"

REM ── Wait for Vite to boot ─────────────────────────────────────────────────
timeout /t 4 /nobreak >nul

REM ── Open browser ─────────────────────────────────────────────────────────
echo.
echo  [OK] Servers started!
echo       API:      http://127.0.0.1:8000
echo       Frontend: http://localhost:5173
echo.
echo  Opening browser...
start "" "http://localhost:5173"
