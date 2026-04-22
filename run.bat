@echo off
chcp 65001 >nul
echo ====================================
echo SchoolInfoSearch - Startup
echo ====================================
echo.

cd /d "%~dp0"

REM Check Python environment priority: portable > system
set "PYTHON_EXE="

REM Check vendor/python first
if exist "%~dp0vendor\python\python.exe" (
    set "PYTHON_EXE=%~dp0vendor\python\python.exe"
    goto :check_meilisearch
)

REM Check system Python
where python >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%i in ('where python') do set "PYTHON_EXE=%%i"
    goto :check_meilisearch
)

echo [Error] Python not found.
echo [Info] Please run scripts\setup.bat first to create the environment.
echo.
pause
exit /b 1

:check_meilisearch
REM Check if Meilisearch exists
if not exist "%~dp0vendor\meilisearch.exe" (
    echo [Warning] Meilisearch not found!
    echo [Info] Please run setup.bat to download it.
    echo.
)

REM Check if frontend is built
if not exist "backend\assets\frontend\index.html" (
    echo [Warning] Frontend not built.
    echo [Info] Please run: scripts\build.bat
    echo.
)

REM Set environment variables
if exist "%~dp0vendor\python\python.exe" (
    set "PYTHONPATH=%~dp0backend"
    set "PYTHONHOME=%~dp0vendor\python"
)

REM Start Meilisearch (if exists)
if exist "%~dp0vendor\meilisearch.exe" (
    echo [Starting] Meilisearch on port 7700...
    start "" "%~dp0vendor\meilisearch.exe" --http-addr 127.0.0.1:7700 --db-path "%~dp0data\meilisearch"
    timeout /t 2 /nobreak >nul
)

REM Start Qdrant (if exists)
if exist "%~dp0vendor\qdrant.exe" (
    echo [Starting] Qdrant on port 6333...
    start "" "%~dp0vendor\qdrant.exe" --config-path "%~dp0config\qdrant.yaml"
    timeout /t 2 /nobreak >nul
)

REM Start backend server (serves both API and frontend)
echo [Starting] FastAPI backend (port 8000, serves frontend)...
cd backend
start "SchoolInfoSearch-Backend" "%PYTHON_EXE%" -u -m uvicorn search_service.main:app --reload --port 8000 --host 127.0.0.1

REM Wait for backend to start
timeout /t 3 /nobreak >nul

REM Open browser
start http://localhost:8000

echo.
echo ====================================
echo System started!
echo Frontend:  http://localhost:8000
echo API Docs:  http://localhost:8000/docs
echo Meilisearch: http://localhost:7700
echo ====================================
echo.
echo Press any key to close this window...
pause >nul
