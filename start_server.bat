@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1

set "PROJECT_ROOT=%~dp0"
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"
cd /d "%PROJECT_ROOT%" || (
    echo ERROR: Cannot open project folder:
    echo %PROJECT_ROOT%
    pause
    exit /b 1
)

echo ========================================
echo   WND NeuroConsultant Server
echo ========================================
echo   Project folder:
echo   %PROJECT_ROOT%
echo ========================================
echo.

echo [1/6] Checking port 8011...
set "PORT_BUSY=0"
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8011 ^| findstr LISTENING 2^>nul') do (
    set "PORT_BUSY=1"
    set "PID=%%a"
    echo    Stopping process !PID! on port 8011...
    taskkill /F /PID !PID! >nul 2>&1
    if not !ERRORLEVEL!==0 (
        echo    WARNING: Could not stop process !PID!
        echo    Run kill_port_8011.bat as administrator
    ) else (
        echo    Process !PID! stopped
    )
)
if "!PORT_BUSY!"=="0" echo    Port 8011 is free
ping 127.0.0.1 -n 3 >nul

echo [2/6] Checking project files...
if not exist "%PROJECT_ROOT%\run.py" goto :error_run_py
if not exist "%PROJECT_ROOT%\backend\main.py" goto :error_main_py
if not exist "%PROJECT_ROOT%\frontend\analiz.html" goto :error_analiz_html
echo    Required files found

findstr /C:"federal-refs-panel" "%PROJECT_ROOT%\frontend\analiz.html" >nul 2>&1
if not !ERRORLEVEL!==0 (
    echo    WARNING: federal refs check feature not found in analiz.html
) else (
    echo    federal refs check feature detected in frontend
)

echo [3/6] Checking .env...
if not exist "%PROJECT_ROOT%\.env" goto :error_env
echo    .env found

echo [4/6] Preparing Python environment...
set "VENV_PYTHON=%PROJECT_ROOT%\backend\.venv\Scripts\python.exe"
set "VENV_PIP=%PROJECT_ROOT%\backend\.venv\Scripts\pip.exe"
set "PYTHON_CMD="

if exist "%VENV_PYTHON%" (
    set "PYTHON_CMD=%VENV_PYTHON%"
    goto :python_ready
)

echo    Virtual environment not found, creating...
python -m venv "%PROJECT_ROOT%\backend\.venv"
if not !ERRORLEVEL!==0 goto :error_venv
if not exist "%VENV_PYTHON%" goto :error_venv
set "PYTHON_CMD=%VENV_PYTHON%"
echo    Virtual environment created

:python_ready
echo    Using: !PYTHON_CMD!

"!PYTHON_CMD!" -c "import fastapi, uvicorn, chromadb" >nul 2>&1
if not !ERRORLEVEL!==0 goto :install_deps
echo    Dependencies OK
goto :deps_ready

:install_deps
echo    Installing dependencies - first run may take several minutes...
"!VENV_PIP!" install -r "%PROJECT_ROOT%\backend\requirements.txt"
if not !ERRORLEVEL!==0 (
    echo    WARNING: Could not install all dependencies
) else (
    echo    Dependencies installed
)

:deps_ready
echo [5/6] Checking configuration...
"!PYTHON_CMD!" "%PROJECT_ROOT%\backend\_check_config.py"
if not !ERRORLEVEL!==0 goto :error_config

echo [6/6] Starting server...
echo.
echo ========================================
echo Server URL: http://localhost:8011
echo Analysis:   http://localhost:8011/static/analiz.html
echo Press Ctrl+C to stop
echo ========================================
echo.

"!PYTHON_CMD!" "%PROJECT_ROOT%\run.py"
set "EXIT_CODE=!ERRORLEVEL!"

if not "!EXIT_CODE!"=="0" (
    echo.
    echo ========================================
    echo ERROR starting server! Exit code: !EXIT_CODE!
    echo ========================================
    echo.
    echo Possible causes:
    echo 1. Port 8011 still in use - run kill_port_8011.bat
    echo 2. Invalid .env configuration
    echo 3. Missing Python packages
    echo 4. Server started from a different project folder
    echo.
)

echo.
echo Server stopped.
pause
exit /b !EXIT_CODE!

:error_run_py
echo    ERROR: run.py not found in project root
goto :fatal_error

:error_main_py
echo    ERROR: backend\main.py not found
goto :fatal_error

:error_analiz_html
echo    ERROR: frontend\analiz.html not found
goto :fatal_error

:error_env
echo    ERROR: .env file not found in project root
echo    Copy env_template.txt to .env and configure it
goto :fatal_error

:error_venv
echo    ERROR: Failed to create virtual environment
echo    Install Python 3.10+ and try again
goto :fatal_error

:error_config
echo    ERROR: Could not load backend configuration
echo    Check .env in project root
goto :fatal_error

:fatal_error
echo.
echo Startup failed. Fix the error above and run start_server.bat again.
pause
exit /b 1
