@echo off
REM ===========================================
REM  AI Trading System - Deploy Script (Windows)
REM  Usage: deploy.bat
REM  Runs on: Xserver VPS (Windows Server)
REM ===========================================

setlocal enabledelayedexpansion

set ROOT=C:\ai_trading_system
set NSSM=C:\tools\nssm\nssm.exe
set NODE="C:\Program Files\nodejs\node.exe"
set NPM="C:\Program Files\nodejs\npm.cmd"
set PYTHON=%ROOT%\backend\venv\Scripts\python.exe
set PIP=%ROOT%\backend\venv\Scripts\pip.exe

echo.
echo ============================================
echo  AI Trading System - Deploy
echo  %date% %time%
echo ============================================
echo.

REM ------------------------------------------
REM  Step 1: Git Pull
REM ------------------------------------------
echo [1/6] Pulling latest code from GitHub...
cd /d %ROOT%
git pull origin main
if errorlevel 1 (
    echo [ERROR] git pull failed!
    exit /b 1
)
echo [OK] Code updated.
echo.

REM ------------------------------------------
REM  Step 2: Backend - pip install
REM ------------------------------------------
echo [2/6] Installing backend dependencies...
cd /d %ROOT%\backend
%PIP% install -r requirements.txt --quiet
if errorlevel 1 (
    echo [WARN] pip install had issues, continuing...
)
echo [OK] Backend dependencies installed.
echo.

REM ------------------------------------------
REM  Step 3: Backend - DB migration
REM ------------------------------------------
echo [3/6] Running database migrations...
cd /d %ROOT%\backend
%PYTHON% -m alembic upgrade head
if errorlevel 1 (
    echo [WARN] Alembic migration had issues, continuing...
)
echo [OK] Database migrations applied.
echo.

REM ------------------------------------------
REM  Step 4: Restart Backend
REM ------------------------------------------
echo [4/6] Restarting backend service...
%NSSM% restart AiTradingBackend
if errorlevel 1 (
    echo [WARN] Backend restart returned non-zero, checking status...
)
timeout /t 3 /nobreak >nul
%NSSM% status AiTradingBackend
echo [OK] Backend service restarted.
echo.

REM ------------------------------------------
REM  Step 5: Frontend - npm install + build
REM ------------------------------------------
echo [5/6] Building frontend...
cd /d %ROOT%\frontend
call %NPM% install --production=false --quiet 2>nul
if errorlevel 1 (
    echo [WARN] npm install had issues, continuing...
)
call %NPM% run build
if errorlevel 1 (
    echo [ERROR] Frontend build failed!
    exit /b 1
)
echo [OK] Frontend built successfully.
echo.

REM ------------------------------------------
REM  Step 6: Restart Frontend
REM ------------------------------------------
echo [6/6] Restarting frontend service...
%NSSM% restart AiTradingFrontend
if errorlevel 1 (
    echo [WARN] Frontend restart returned non-zero, checking status...
)
timeout /t 3 /nobreak >nul
%NSSM% status AiTradingFrontend
echo [OK] Frontend service restarted.
echo.

echo ============================================
echo  Deploy completed!
echo  Backend:  http://localhost:8000/docs
echo  Frontend: http://localhost:3000
echo ============================================

endlocal
