@echo off
setlocal
title PythonRPG Launcher
echo Starting RPG Game...

REM Change to script directory
cd /d "%~dp0"

REM Ensure Python is installed, try winget first
where py >nul 2>nul || where python >nul 2>nul
if errorlevel 1 (
  echo Python not found. Attempting installation via winget...
  winget --version >nul 2>nul
  if errorlevel 1 (
    echo winget is not available. Please install Python 3 from https://www.python.org/downloads/
    pause
    exit /b 1
  )
  winget install -e --id Python.Python.3 --accept-source-agreements --accept-package-agreements
)

REM Re-detect Python
set PYEXE=
where py >nul 2>nul && set PYEXE=py
if "%PYEXE%"=="" (
  where python >nul 2>nul && set PYEXE=python
)
if "%PYEXE%"=="" (
  echo Could not locate Python after installation. Please install manually.
  pause
  exit /b 1
)

REM Create or activate virtual environment
if exist .venv\Scripts\activate.bat (
  echo Activating virtual environment...
  call .venv\Scripts\activate.bat
) else if exist venv\Scripts\activate.bat (
  echo Activating virtual environment...
  call venv\Scripts\activate.bat
) else (
  echo Creating virtual environment...
  %PYEXE% -m venv .venv
  if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat
)

REM Ensure pip is present and updated
%PYEXE% -m ensurepip >nul 2>nul
%PYEXE% -m pip install --upgrade pip >nul 2>nul

REM Install requirements
if exist requirements.txt (
  echo Installing dependencies...
  %PYEXE% -m pip install -r requirements.txt || (
    echo Failed to install dependencies. Try manually: %PYEXE% -m pip install -r requirements.txt
    pause
    exit /b 1
  )
)

echo Launching game...
%PYEXE% Main.py

pause
endlocal