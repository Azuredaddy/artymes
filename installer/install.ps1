# Artymes - ARTY AI Employee Installer
# Run with: iwr -useb <url>/install.ps1 | iex

$ErrorActionPreference = "Stop"
$ArtyVersion = "1.0.0"
$InstallDir = "$env:USERPROFILE\Artymes"

function Write-Header {
    Clear-Host
    Write-Host ""
    Write-Host "  ╔══════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "  ║     Project Artymes - ARTY Installer     ║" -ForegroundColor Cyan
    Write-Host "  ║              Version $ArtyVersion                ║" -ForegroundColor Cyan
    Write-Host "  ╚══════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Step($msg) {
    Write-Host "  [>>] $msg" -ForegroundColor Yellow
}

function Write-OK($msg) {
    Write-Host "  [OK] $msg" -ForegroundColor Green
}

function Write-Fail($msg) {
    Write-Host "  [!!] $msg" -ForegroundColor Red
}

function Test-Command($cmd) {
    return [bool](Get-Command $cmd -ErrorAction SilentlyContinue)
}

Write-Header

# ── Check / Install Python ────────────────────────────────────────────────────
Write-Step "Checking Python..."
if (-not (Test-Command "python")) {
    Write-Step "Python not found. Installing Python 3.11..."
    $pythonUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
    $pythonInstaller = "$env:TEMP\python_installer.exe"
    Invoke-WebRequest -Uri $pythonUrl -OutFile $pythonInstaller
    Start-Process -FilePath $pythonInstaller -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1" -Wait
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    Write-OK "Python installed."
} else {
    Write-OK "Python found: $(python --version)"
}

# ── Check / Install ffmpeg ────────────────────────────────────────────────────
Write-Step "Checking ffmpeg..."
if (-not (Test-Command "ffmpeg")) {
    Write-Step "Installing ffmpeg via winget..."
    try {
        winget install Gyan.FFmpeg --silent --accept-package-agreements --accept-source-agreements
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        Write-OK "ffmpeg installed."
    } catch {
        Write-Fail "winget failed. Please install ffmpeg manually from https://www.gyan.dev/ffmpeg/builds/"
        Write-Fail "Then re-run this installer."
        Read-Host "Press Enter to exit"
        exit 1
    }
} else {
    Write-OK "ffmpeg found."
}

# ── Create install directory ──────────────────────────────────────────────────
Write-Step "Creating install directory at $InstallDir..."
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
New-Item -ItemType Directory -Force -Path "$InstallDir\data" | Out-Null
Write-OK "Directory ready."

# ── Download Artymes files ────────────────────────────────────────────────────
Write-Step "Downloading Artymes files..."
$RepoBase = "https://raw.githubusercontent.com/Azuredaddy/artymes/main"

$files = @(
    "main.py",
    "config.py",
    "requirements.txt",
    ".env.example",
    "brain/__init__.py",
    "brain/claude_client.py",
    "brain/memory.py",
    "brain/personality.py",
    "voice/__init__.py",
    "voice/stt.py",
    "voice/tts.py"
)

foreach ($file in $files) {
    $dir = Split-Path "$InstallDir\$file" -Parent
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    Invoke-WebRequest -Uri "$RepoBase/$file" -OutFile "$InstallDir\$file"
}
Write-OK "Files downloaded."

# ── Create virtual environment ────────────────────────────────────────────────
Write-Step "Creating Python virtual environment..."
Set-Location $InstallDir
python -m venv venv
Write-OK "Virtual environment created."

# ── Install dependencies ──────────────────────────────────────────────────────
Write-Step "Installing PyTorch (CPU)..."
& "$InstallDir\venv\Scripts\pip.exe" install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu --quiet

Write-Step "Installing ARTY dependencies..."
& "$InstallDir\venv\Scripts\pip.exe" install -r "$InstallDir\requirements.txt" --quiet
Write-OK "Dependencies installed."

# ── .env setup ───────────────────────────────────────────────────────────────
if (-not (Test-Path "$InstallDir\.env")) {
    Copy-Item "$InstallDir\.env.example" "$InstallDir\.env"
}

# ── Create desktop shortcut ───────────────────────────────────────────────────
Write-Step "Creating desktop shortcut..."
$launchScript = @"
@echo off
cd /d "$InstallDir"
call venv\Scripts\activate.bat
python main.py
pause
"@
$launchScript | Out-File -FilePath "$InstallDir\Run ARTY.bat" -Encoding ASCII

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\ARTY.lnk")
$Shortcut.TargetPath = "$InstallDir\Run ARTY.bat"
$Shortcut.IconLocation = "shell32.dll,13"
$Shortcut.Description = "Launch ARTY AI Employee"
$Shortcut.Save()
Write-OK "Desktop shortcut created."

# ── Done ──────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  ╔══════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "  ║         ARTY is ready to install!        ║" -ForegroundColor Green
Write-Host "  ╚══════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "  Next step: add your API keys to .env" -ForegroundColor White
Write-Host "  Opening .env now..." -ForegroundColor White
Write-Host ""
Start-Process notepad "$InstallDir\.env"
Write-Host "  Fill in:" -ForegroundColor Yellow
Write-Host "    ANTHROPIC_API_KEY  = your Anthropic key" -ForegroundColor White
Write-Host "    ELEVENLABS_API_KEY = your ElevenLabs key" -ForegroundColor White
Write-Host "    ARTY_VOICE_ID      = your chosen voice ID" -ForegroundColor White
Write-Host ""
Write-Host "  Then double-click ARTY on your Desktop." -ForegroundColor Cyan
Write-Host ""
Read-Host "  Press Enter to finish"
