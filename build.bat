@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ====================================
echo SchoolInfoSearch - Build Frontend
echo ====================================
echo.

cd /d "%~dp0"

REM Check Node.js
set "NODE_FOUND=0"
where node >nul 2>&1
if not errorlevel 1 set "NODE_FOUND=1"
if exist "C:\Program Files\nodejs\node.exe" set "NODE_FOUND=1"
if exist "C:\Program Files (x86)\nodejs\node.exe" set "NODE_FOUND=1"

if "%NODE_FOUND%"=="0" (
    echo [Info] Node.js not found.
    echo [Installing] Node.js LTS via winget...
    echo.

    winget install OpenJS.NodeJS.LTS -e --source winget --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo [Error] winget install failed.
        echo [Tip] Make sure winget is available, or install Node.js manually from https://nodejs.org/
        pause
        exit /b 1
    )

    echo [Info] Node.js installed via winget.
    echo [Tip] If node is not found, please restart your terminal and run scripts\build.bat again.
    echo.
)

REM Find node and npm paths
set "NODE_EXE="
set "NPM_EXE="
where node >nul 2>&1
if not errorlevel 1 for /f "delims=" %%i in ('where node') do set "NODE_EXE=%%i"
if "%NODE_EXE%"=="" if exist "C:\Program Files\nodejs\node.exe" set "NODE_EXE=C:\Program Files\nodejs\node.exe"
if "%NODE_EXE%"=="" if exist "C:\Program Files (x86)\nodejs\node.exe" set "NODE_EXE=C:\Program Files (x86)\nodejs\node.exe"

if "%NODE_EXE%"=="" (
    echo [Error] Node.js not found after installation.
    echo [Tip] Please restart your terminal and run scripts\build.bat again.
    pause
    exit /b 1
)

echo [Info] Node.js found: %NODE_EXE%
"%NODE_EXE%" --version
echo.

cd /d "%~dp0frontend"

REM Check node_modules
if not exist "node_modules" (
    echo [Step 1] Installing frontend dependencies...
    if exist "C:\Program Files\nodejs\npm.cmd" (
        call "C:\Program Files\nodejs\npm.cmd" install
    ) else (
        npm install
    )
    if errorlevel 1 (
        echo [Error] Failed to install dependencies
        pause
        exit /b 1
    )
    echo.
)

echo [Step 2] Building frontend...
if exist "C:\Program Files\nodejs\npm.cmd" (
    call "C:\Program Files\nodejs\npm.cmd" run build
) else (
    call npm run build
)
if errorlevel 1 (
    echo [Error] Build failed
    pause
    exit /b 1
)

echo.
echo ====================================
echo [Success] Build completed!
echo [Output] backend/assets/frontend/
echo ====================================
echo.
echo Now you can run scripts\run.bat to start the system
pause
