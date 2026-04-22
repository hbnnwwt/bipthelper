@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo SchoolInfoSearch - Environment Setup
echo ========================================
echo.

set "PROJECT_DIR=%~dp0"
set "PYTHON_DIR=%PROJECT_DIR%vendor\python"
set "PYTHON_EXE=%PYTHON_DIR%\python.exe"
set "PYTHONDIR_WAS_SET=

REM =============================================
REM Step 1: Python Setup
REM =============================================
echo [Step 1] Python Setup
echo.

if exist "%PYTHON_EXE%" (
    echo [Info] Portable Python found: %PYTHON_DIR%
    goto :check_python_configured
)

echo [Info] Portable Python not found.
echo [Downloading] Python 3.12.4 embeddable (this may take a while)...
echo.

set "PYTHON_VERSION=3.12.4"
set "PYTHON_ZIP=python-3.12.4-embed-amd64.zip"
set "DOWNLOAD_URL=https://www.python.org/ftp/python/%PYTHON_VERSION%/%PYTHON_ZIP%"

powershell -Command "& { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%DOWNLOAD_URL%' -OutFile '%PROJECT_DIR%%PYTHON_ZIP%' -UseBasicParsing }"
if %errorlevel% neq 0 (
    echo [Error] Failed to download Python.
    pause
    exit /b 1
)

echo [Extracting] Python...
if exist "%PYTHON_DIR%" rmdir /s /q "%PYTHON_DIR%"
mkdir "%PYTHON_DIR%"
powershell -Command "Expand-Archive -Path '%PROJECT_DIR%%PYTHON_ZIP%' -DestinationPath '%PYTHON_DIR%' -Force"
del "%PROJECT_DIR%%PYTHON_ZIP%"

if not exist "%PYTHON_EXE%" (
    echo [Error] Failed to extract Python.
    pause
    exit /b 1
)

echo [OK] Python extracted.

:check_python_configured
REM Check if python is configured (has site-packages enabled)
set "PTH_FILE=%PYTHON_DIR%\python312._pth"
set "NEEDS_CONFIG=0"

findstr /R /C:"^[^#]*import site" "%PTH_FILE%" >nul 2>&1
if errorlevel 1 (
    set "NEEDS_CONFIG=1"
)

if "%NEEDS_CONFIG%"=="1" (
    echo [Configuring] Python to support site-packages...
    powershell -Command "(Get-Content '%PTH_FILE%') -replace '#import site', 'import site' | Set-Content '%PTH_FILE%'"
    echo [OK] Python configured.
) else (
    echo [Info] Python already configured.
)

REM Install pip for embeddable Python
if not exist "%PYTHON_DIR%\Scripts\pip.exe" (
    echo [Downloading] pip...
    powershell -Command "& { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%PYTHON_DIR%\get-pip.py' -UseBasicParsing }"
    if exist "%PYTHON_DIR%\get-pip.py" (
        echo [Installing] pip...
        "%PYTHON_EXE%" "%PYTHON_DIR%\get-pip.py" --no-warn-script-location -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn
        del "%PYTHON_DIR%\get-pip.py"
    )
)

REM Upgrade pip
echo [Upgrading] pip...
"%PYTHON_EXE%" -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn >nul 2>&1

echo.

REM =============================================
REM Step 2: VC++ Runtime DLLs
REM =============================================
echo [Step 2] VC++ Runtime DLLs
echo.

REM Create vendor/runtime directory
if not exist "%PROJECT_DIR%vendor\runtime" mkdir "%PROJECT_DIR%vendor\runtime"

REM Copy vcruntime DLLs from System32 to vendor/runtime
if exist "%SystemRoot%\System32\vcruntime140.dll" (
    copy /Y "%SystemRoot%\System32\vcruntime140.dll" "%PROJECT_DIR%vendor\runtime\vcruntime140.dll" >nul
    echo [Info] Copied vcruntime140.dll
)

if exist "%SystemRoot%\System32\vcruntime140_1.dll" (
    copy /Y "%SystemRoot%\System32\vcruntime140_1.dll" "%PROJECT_DIR%vendor\runtime\vcruntime140_1.dll" >nul
    echo [Info] Copied vcruntime140_1.dll
)

if not exist "%PROJECT_DIR%vendor\runtime\vcruntime140.dll" (
    echo [Warning] vcruntime140.dll not found. Meilisearch may not work.
)

echo.

REM =============================================
REM Step 3: Meilisearch
REM =============================================
echo [Step 3] Meilisearch
echo.

if exist "%PROJECT_DIR%vendor\meilisearch.exe" (
    echo [Info] Meilisearch already exists.
    goto :install_deps
)

echo [Downloading] Meilisearch (this may take a while)...
set "MEILI_URL=https://github.com/meilisearch/meilisearch/releases/latest/download/meilisearch-windows-amd64.exe"
powershell -Command "& { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%MEILI_URL%' -OutFile '%PROJECT_DIR%vendor\meilisearch.exe' -UseBasicParsing }"

if %errorlevel% neq 0 (
    echo [Warning] Failed to download Meilisearch.
    echo [Info] Please download manually from: https://github.com/meilisearch/meilisearch/releases
) else (
    echo [OK] Meilisearch downloaded.
)
echo.

REM =============================================
REM Step 3.5: Qdrant
REM =============================================
echo [Step 3.5] Qdrant
echo.

if exist "%PROJECT_DIR%vendor\qdrant.exe" (
    echo [Info] Qdrant already exists.
) else (
    echo [Downloading] Qdrant...
    powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://github.com/qdrant/qdrant/releases/download/v1.12.0/qdrant-x86_64-pc-windows-msvc.zip' -OutFile '%PROJECT_DIR%vendor\qdrant.zip' -UseBasicParsing"
    if errorlevel 1 (
        echo [Warning] Failed to download Qdrant.
    ) else (
        echo [Extracting] Qdrant...
        powershell -Command "Expand-Archive -Path '%PROJECT_DIR%vendor\qdrant.zip' -DestinationPath '%PROJECT_DIR%vendor' -Force"
        del "%PROJECT_DIR%vendor\qdrant.zip"
        echo [OK] Qdrant downloaded.
    )
)
echo.

REM =============================================
REM Step 4: Install Python Dependencies
REM =============================================
:install_deps
echo [Step 4] Python Dependencies
echo.

set "PYTHONPATH=%PROJECT_DIR%backend"
set "PYTHONHOME=%PYTHON_DIR%"

if exist "%PROJECT_DIR%backend\requirements.txt" (
    echo [Installing] packages from requirements.txt...
    "%PYTHON_EXE%" -m pip install -r "%PROJECT_DIR%backend\requirements.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn
    if errorlevel 1 (
        echo [Error] Failed to install dependencies.
        pause
        exit /b 1
    )
    echo [OK] Dependencies installed.
) else (
    echo [Error] requirements.txt not found.
    pause
    exit /b 1
)
echo.

REM =============================================
REM Step 5: Create Directories
REM =============================================
echo [Step 5] Create Directories
echo.

if not exist "%PROJECT_DIR%data" mkdir "%PROJECT_DIR%data"
if not exist "%PROJECT_DIR%data\htmls" mkdir "%PROJECT_DIR%data\htmls"
if not exist "%PROJECT_DIR%backend\assets" mkdir "%PROJECT_DIR%backend\assets"
echo [OK] Directories created.
echo.

REM =============================================
REM Step 6: Reset Database (delete old db, create new)
REM =============================================
echo [Step 6] Reset Database
echo.

if exist "%PROJECT_DIR%data\app.db" (
    del /f /q "%PROJECT_DIR%data\app.db"
    echo [Info] Deleted old database.
)
echo [Info] Database will be recreated on first run.
echo [OK] Database reset.
echo.

REM =============================================
REM Complete
REM =============================================
echo ========================================
echo Setup completed successfully!
echo ========================================
echo.
echo Next steps:
echo   build.bat  - Build frontend
echo   run.bat    - Start the system
echo.
echo Initial account: admin / admin123
echo.

pause
