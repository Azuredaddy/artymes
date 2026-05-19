@echo off
echo ============================================
echo  Project Artymes - ARTY Setup (Windows)
echo ============================================
echo.

:: Check Python 3.11+
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found.
    echo Download and install Python 3.11 from https://python.org
    echo Make sure to tick "Add Python to PATH" during install.
    pause
    exit /b 1
)

echo [OK] Python found.

:: Check ffmpeg (needed by Whisper)
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [WARNING] ffmpeg not found. Whisper needs it to process audio.
    echo.
    echo Install it now:
    echo   1. Go to https://www.gyan.dev/ffmpeg/builds/
    echo   2. Download ffmpeg-release-essentials.zip
    echo   3. Extract to C:\ffmpeg
    echo   4. Add C:\ffmpeg\bin to your Windows PATH
    echo   5. Restart this script
    echo.
    echo OR run this in PowerShell as Admin:
    echo   winget install Gyan.FFmpeg
    echo.
    pause
    exit /b 1
)
echo [OK] ffmpeg found.

:: Create virtual environment
echo.
echo Creating virtual environment...
python -m venv venv
call venv\Scripts\activate.bat

:: Upgrade pip
python -m pip install --upgrade pip setuptools wheel

:: Install PyTorch CPU (needed for Whisper)
echo.
echo Installing PyTorch (CPU version)...
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

:: Install all requirements
echo.
echo Installing ARTY requirements...
pip install -r requirements.txt

:: Create data directory
if not exist data mkdir data

:: Set up .env
if not exist .env (
    copy .env.example .env
    echo.
    echo ============================================
    echo  ACTION REQUIRED: Fill in your API keys
    echo ============================================
    echo.
    echo Opening .env in Notepad...
    echo Fill in:
    echo   ANTHROPIC_API_KEY  - from console.anthropic.com
    echo   ELEVENLABS_API_KEY - from elevenlabs.io/app/settings/api-keys
    echo   ARTY_VOICE_ID      - see instructions below
    echo.
    echo To find ARTY's Voice ID:
    echo   1. Go to elevenlabs.io
    echo   2. Pick or create a voice you like
    echo   3. Click the voice, copy the Voice ID
    echo   4. Paste it into ARTY_VOICE_ID in .env
    echo.
    notepad .env
) else (
    echo [OK] .env already exists.
)

echo.
echo ============================================
echo  Setup complete!
echo  Run ARTY by double-clicking run_arty.bat
echo ============================================
pause
