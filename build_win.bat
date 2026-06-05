@echo off
setlocal

set SCRIPT_DIR=%~dp0
set VENV_DIR=%SCRIPT_DIR%.venv
set PYTHON=%VENV_DIR%\Scripts\python.exe
set PIP=%VENV_DIR%\Scripts\pip.exe

:: Bootstrap venv if needed
if not exist "%PYTHON%" (
    echo Creating virtual environment...
    python -m venv "%VENV_DIR%"
    "%PIP%" install --quiet -r "%SCRIPT_DIR%requirements.txt"
)

:: Install PyInstaller if missing
"%PYTHON%" -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo Installing PyInstaller...
    "%PIP%" install --quiet pyinstaller
)

echo Building for Windows...

cd /d "%SCRIPT_DIR%"

"%PYTHON%" -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name "AudioLatencyDetector" ^
    --clean ^
    audio_latency_detector.py

:: Clean up build artefacts, keep only dist/
if exist build rmdir /s /q build
del /q *.spec 2>nul

echo.
echo Done: dist\AudioLatencyDetector.exe
endlocal
