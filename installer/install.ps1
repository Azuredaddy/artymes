# Artymes - ARTY AI Employee Installer
# Run with: iwr -useb https://raw.githubusercontent.com/Azuredaddy/artymes/main/installer/install.ps1 | iex

$ErrorActionPreference = "Stop"
$ArtyVersion = "1.0.0"
$InstallDir = "$env:USERPROFILE\Artymes"

function Write-Header {
    Clear-Host
    Write-Host ""
    Write-Host "  +------------------------------------------+" -ForegroundColor Cyan
    Write-Host "  |     Project Artymes - ARTY Installer     |" -ForegroundColor Cyan
    Write-Host "  |              Version $ArtyVersion                |" -ForegroundColor Cyan
    Write-Host "  +------------------------------------------+" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Step($msg) { Write-Host "  [>>] $msg" -ForegroundColor Yellow }
function Write-OK($msg)   { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Fail($msg) { Write-Host "  [!!] $msg" -ForegroundColor Red }
function Test-Command($cmd) { return [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }

Write-Header

# -- Check / Install Python ---------------------------------------------------
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

# -- Check / Install ffmpeg ---------------------------------------------------
Write-Step "Checking ffmpeg..."
if (-not (Test-Command "ffmpeg")) {
    Write-Step "Installing ffmpeg..."
    $ffmpegOk = $false

    # Try winget user scope first
    try {
        $result = winget install Gyan.FFmpeg --scope user --silent --accept-package-agreements --accept-source-agreements 2>&1
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        if (Test-Command "ffmpeg") { $ffmpegOk = $true; Write-OK "ffmpeg installed." }
    } catch {}

    # Try manual download if winget failed
    if (-not $ffmpegOk) {
        Write-Step "Winget failed - downloading ffmpeg directly..."
        try {
            $ffmpegZip = "$env:TEMP\ffmpeg.zip"
            $ffmpegDir = "$env:USERPROFILE\ffmpeg"
            Invoke-WebRequest -Uri "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" -OutFile $ffmpegZip
            Expand-Archive -Path $ffmpegZip -DestinationPath $ffmpegDir -Force
            $ffmpegBin = (Get-ChildItem -Path $ffmpegDir -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1).DirectoryName
            $currentPath = [System.Environment]::GetEnvironmentVariable("Path","User")
            [System.Environment]::SetEnvironmentVariable("Path", "$currentPath;$ffmpegBin", "User")
            $env:Path += ";$ffmpegBin"
            $ffmpegOk = $true
            Write-OK "ffmpeg installed to $ffmpegBin"
        } catch {
            Write-Fail "ffmpeg install failed: $_"
            Write-Fail "ARTY will still work but voice transcription may not function."
        }
    }
} else {
    Write-OK "ffmpeg found."
}

# -- Create install directory -------------------------------------------------
Write-Step "Creating install directory at $InstallDir..."
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
New-Item -ItemType Directory -Force -Path "$InstallDir\data" | Out-Null
Write-OK "Directory ready."

# -- Download Artymes files ---------------------------------------------------
Write-Step "Downloading Artymes files..."
$RepoBase = "https://raw.githubusercontent.com/Azuredaddy/artymes/main"
$files = @(
    "main.py", "config.py", "requirements.txt", ".env.example",
    "brain/__init__.py", "brain/claude_client.py", "brain/memory.py", "brain/personality.py",
    "voice/__init__.py", "voice/stt.py", "voice/tts.py"
)
foreach ($file in $files) {
    $dir = Split-Path "$InstallDir\$file" -Parent
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    Invoke-WebRequest -Uri "$RepoBase/$file" -OutFile "$InstallDir\$file"
}
Write-OK "Files downloaded."

# -- Virtual environment ------------------------------------------------------
Write-Step "Creating Python virtual environment..."
Set-Location $InstallDir
python -m venv venv
Write-OK "Virtual environment created."

# -- Install dependencies -----------------------------------------------------
Write-Step "Installing PyTorch (CPU) - this takes a few minutes..."
& "$InstallDir\venv\Scripts\pip.exe" install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu --quiet

Write-Step "Installing ARTY dependencies..."
& "$InstallDir\venv\Scripts\pip.exe" install -r "$InstallDir\requirements.txt" --quiet
Write-OK "Dependencies installed."

# -- API Key Setup ------------------------------------------------------------
Write-Host ""
Write-Host "  +------------------------------------------+" -ForegroundColor Cyan
Write-Host "  |           ARTY API Key Setup             |" -ForegroundColor Cyan
Write-Host "  +------------------------------------------+" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Enter your API keys below." -ForegroundColor White
Write-Host "  Press Enter to skip any key (you can edit .env later)." -ForegroundColor DarkGray
Write-Host ""

$anthropicKey  = Read-Host "  Anthropic API Key"
$elevenKey     = Read-Host "  ElevenLabs API Key"
$voiceId       = Read-Host "  ElevenLabs Voice ID"

if (-not $anthropicKey)  { $anthropicKey  = "YOUR_ANTHROPIC_KEY_HERE" }
if (-not $elevenKey)     { $elevenKey     = "YOUR_ELEVENLABS_KEY_HERE" }
if (-not $voiceId)       { $voiceId       = "YOUR_VOICE_ID_HERE" }

$envContent = @"
ANTHROPIC_API_KEY=$anthropicKey
ELEVENLABS_API_KEY=$elevenKey
ARTY_VOICE_ID=$voiceId
PUSH_TO_TALK=false
WAKE_WORD=hey arty
MEMORY_DB_PATH=./data/arty_memory.db
CHROMA_PATH=./data/chroma
"@
$envContent | Set-Content "$InstallDir\.env" -Encoding UTF8
Write-OK ".env written with your API keys."

# -- Desktop shortcut ---------------------------------------------------------
Write-Step "Creating desktop shortcut..."
$launchScript = "@echo off`r`ncd /d `"$InstallDir`"`r`ncall venv\Scripts\activate.bat`r`npython main.py`r`npause"
$launchScript | Out-File -FilePath "$InstallDir\Run ARTY.bat" -Encoding ASCII

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\ARTY.lnk")
$Shortcut.TargetPath = "$InstallDir\Run ARTY.bat"
$Shortcut.IconLocation = "shell32.dll,13"
$Shortcut.Description = "Launch ARTY AI Employee"
$Shortcut.Save()
Write-OK "Desktop shortcut created."

# -- Done ---------------------------------------------------------------------
Write-Host ""
Write-Host "  +------------------------------------------+" -ForegroundColor Green
Write-Host "  |        ARTY is ready to launch!          |" -ForegroundColor Green
Write-Host "  |   Double-click ARTY on your Desktop      |" -ForegroundColor Green
Write-Host "  +------------------------------------------+" -ForegroundColor Green
Write-Host ""
Read-Host "  Press Enter to finish"
