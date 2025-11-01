@echo off
setlocal
echo Starting RPG Game...

REM Try to activate virtual environment if present
if exist .venv\Scripts\activate.bat (
  echo Activating virtual environment...
  call .venv\Scripts\activate.bat
) else if exist venv\Scripts\activate.bat (
  echo Activating virtual environment...
  call venv\Scripts\activate.bat
)

REM Install dependencies (no-op if already installed)
if exist requirements.txt (
  where py >nul 2>nul && py -m pip install -r requirements.txt >nul 2>nul || (
    where python >nul 2>nul && python -m pip install -r requirements.txt >nul 2>nul
  )
)

echo Launching game...
where py >nul 2>nul && py Main.py || python Main.py

pause
endlocal