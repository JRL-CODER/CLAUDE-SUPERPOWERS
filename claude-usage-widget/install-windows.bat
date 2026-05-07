@echo off
title Claude Usage Widget - Windows Installer
echo ================================================
echo   Claude Usage Widget - Windows Build ^& Install
echo ================================================
echo.

:: Check Node.js
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js not found.
    echo Please install Node.js 18+ from https://nodejs.org
    echo Then re-run this script.
    pause
    exit /b 1
)

echo [1/3] Installing dependencies...
npm install
if %errorlevel% neq 0 (
    echo [ERROR] npm install failed.
    pause
    exit /b 1
)

echo.
echo [2/3] Building Windows installer...
npm run build:win
if %errorlevel% neq 0 (
    echo [ERROR] Build failed.
    pause
    exit /b 1
)

echo.
echo [3/3] Done!
echo.
echo Installer location: dist\Claude-Usage-Widget-Setup.exe
echo Portable exe:       dist\Claude-Usage-Widget-*-win-portable.exe
echo.
echo Run the installer to complete installation.
echo.
start "" "dist"
pause
