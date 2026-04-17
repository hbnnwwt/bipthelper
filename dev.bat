@echo off
chcp 65001 >nul
echo ====================================
echo SchoolInfoSearch - Development Mode
echo ====================================
echo.

cd /d "%~dp0"

REM Check Python environment priority: portable > system
set "PYTHON_EXE="

REM Check vendor/python first
if exist "%~dp0vendor\python\python.exe" (
    set "PYTHON_EXE=%~dp0vendor\python\python.exe"
    goto :check_node
)

REM Check system Python
where python >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%i in ('where python') do set "PYTHON_EXE=%%i"
    goto :check_node
)

echo [Error] Python not found.
echo [Info] Please run scripts\setup.bat first to create the environment.
echo.
pause
exit /b 1

:check_node
REM Check Node.js
set "NODE_FOUND=0"
where node >nul 2>&1
if not errorlevel 1 set "NODE_FOUND=1"
if exist "C:\Program Files\nodejs\node.exe" set "NODE_FOUND=1"

if "%NODE_FOUND%"=="0" (
    echo [Error] Node.js not found. Please install Node.js 18+ from https://nodejs.org/
    echo.
    pause
    exit /b 1
)

REM Set Python environment
if exist "%~dp0vendor\python\python.exe" (
    set "PYTHONPATH=%~dp0backend"
    set "PYTHONHOME=%~dp0vendor\python"
)

REM Start Meilisearch (if exists)
if exist "%~dp0vendor\meilisearch.exe" (
    echo [Starting] Meilisearch on port 7700...
    start "" "%~dp0vendor\meilisearch.exe" --http-addr 127.0.0.1:7700 --db-path "%~dp0data\meilisearch"
    timeout /t 2 /nobreak >nul
) else (
    echo [Warning] Meilisearch not found!
    echo [Info] Please run scripts\setup.bat to download it.
    echo.
)

REM Start Qdrant (if exists)
if exist "%~dp0vendor\qdrant.exe" (
    echo [Starting] Qdrant on port 6333...
    start "" "%~dp0vendor\qdrant.exe" --config-path "%~dp0config\qdrant.yaml"
    timeout /t 2 /nobreak >nul
)

REM Start backend (in new window)
echo [Starting] Backend server (port 8000)...
start "SchoolInfoSearch-Backend" "%PYTHON_EXE%" -m uvicorn main:app --reload --port 8000 --host 127.0.0.1

timeout /t 3 /nobreak >nul

REM Start frontend dev server
echo [Starting] Frontend dev server (port 3000)...
cd frontend

REM Check node_modules
if not exist "node_modules" (
    echo [Installing] Frontend dependencies...
    npm install
)

npm run dev

pause
