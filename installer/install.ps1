# Artymes - ARTY AI Employee Installer
# Run with: iwr -useb https://raw.githubusercontent.com/Azuredaddy/artymes/main/installer/install.ps1 | iex

$ErrorActionPreference = "Stop"
$ArtyVersion = "1.4.3"
$InstallDir = "C:\Artymes"

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

# -- Safe temp dir (avoids pip failures with special chars in username) --------
if (-not (Test-Path "C:\Temp")) { New-Item -ItemType Directory -Force -Path "C:\Temp" | Out-Null }
$env:TEMP = "C:\Temp"
$env:TMP  = "C:\Temp"

# -- Check / Install Python ---------------------------------------------------
Write-Step "Checking Python..."
if (-not (Test-Command "python")) {
    Write-Step "Python not found. Installing Python 3.11..."
    $pythonUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
    $pythonInstaller = "C:\Temp\python_installer.exe"
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

    try {
        winget install Gyan.FFmpeg --scope user --silent --accept-package-agreements --accept-source-agreements 2>&1 | Out-Null
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        if (Test-Command "ffmpeg") { $ffmpegOk = $true; Write-OK "ffmpeg installed." }
    } catch {}

    if (-not $ffmpegOk) {
        Write-Step "Winget failed - downloading ffmpeg directly..."
        try {
            $ffmpegZip = "C:\Temp\ffmpeg.zip"
            $ffmpegDir = "$env:USERPROFILE\ffmpeg"
            Invoke-WebRequest -Uri "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" -OutFile $ffmpegZip
            Expand-Archive -Path $ffmpegZip -DestinationPath $ffmpegDir -Force
            $ffmpegBin = (Get-ChildItem -Path $ffmpegDir -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1).DirectoryName
            $currentPath = [System.Environment]::GetEnvironmentVariable("Path","User")
            [System.Environment]::SetEnvironmentVariable("Path", "$currentPath;$ffmpegBin", "User")
            $env:Path += ";$ffmpegBin"
            Write-OK "ffmpeg installed to $ffmpegBin"
        } catch {
            Write-Fail "ffmpeg install failed: $_"
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
    "main.py", "config.py", "requirements.txt", ".env.example", "version.txt",
    "run_arty.bat", "setup_windows.bat",
    "brain/__init__.py", "brain/claude_client.py", "brain/memory.py", "brain/personality.py", "brain/context.py",
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
Write-Step "Installing ARTY dependencies (this takes a few minutes)..."
Write-Step "Upgrading pip first..."
$ErrorActionPreference = "Continue"
& "$InstallDir\venv\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
Write-Step "Installing packages..."
& "$InstallDir\venv\Scripts\pip.exe" install -r "$InstallDir\requirements.txt"
$pipExit = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if ($pipExit -ne 0) {
    Write-Host ""
    Write-Fail "Dependency install failed — see errors above."
    Write-Fail "Python 3.13 may not be supported by faster-whisper or chromadb yet."
    Write-Fail "Fix: install Python 3.11 from python.org then re-run this installer."
    exit 1
}
Write-OK "Dependencies installed."

# -- Collect API keys ---------------------------------------------------------
Write-Host ""
Write-Host "  +------------------------------------------+" -ForegroundColor Yellow
Write-Host "  |           API Keys Required              |" -ForegroundColor Yellow
Write-Host "  +------------------------------------------+" -ForegroundColor Yellow
Write-Host ""
Write-Host "  You need two API keys to run ARTY:" -ForegroundColor White
Write-Host "    Anthropic: https://console.anthropic.com/settings/keys" -ForegroundColor Cyan
Write-Host "    ElevenLabs: your ElevenLabs account > Profile > API Key" -ForegroundColor Cyan
Write-Host ""

# Check if .env already exists with valid keys (upgrade scenario)
$existingAnthropicKey = ""
$existingElevenLabsKey = ""
$existingVoiceId = ""
$envFile = "$InstallDir\.env"
if (Test-Path $envFile) {
    $existingAnthropicKey = (Get-Content $envFile | Where-Object { $_ -match "^ANTHROPIC_API_KEY=" }) -replace "^ANTHROPIC_API_KEY=", ""
    $existingElevenLabsKey = (Get-Content $envFile | Where-Object { $_ -match "^ELEVENLABS_API_KEY=" }) -replace "^ELEVENLABS_API_KEY=", ""
    $existingVoiceId = (Get-Content $envFile | Where-Object { $_ -match "^ARTY_VOICE_ID=" }) -replace "^ARTY_VOICE_ID=", ""
}

# Anthropic key
if ($existingAnthropicKey -and $existingAnthropicKey.StartsWith("sk-")) {
    Write-Host "  Anthropic key already set. Press Enter to keep it, or paste a new one:" -ForegroundColor DarkGray
    $inputAnthropicKey = Read-Host "  Anthropic API Key"
    if (-not $inputAnthropicKey) { $inputAnthropicKey = $existingAnthropicKey }
} else {
    do {
        $inputAnthropicKey = Read-Host "  Anthropic API Key (starts with sk-ant-)"
    } while (-not $inputAnthropicKey.StartsWith("sk-"))
}

# ElevenLabs key
if ($existingElevenLabsKey -and $existingElevenLabsKey.Length -gt 10) {
    Write-Host "  ElevenLabs key already set. Press Enter to keep it, or paste a new one:" -ForegroundColor DarkGray
    $inputElevenLabsKey = Read-Host "  ElevenLabs API Key"
    if (-not $inputElevenLabsKey) { $inputElevenLabsKey = $existingElevenLabsKey }
} else {
    $inputElevenLabsKey = Read-Host "  ElevenLabs API Key"
}

# Voice ID
$defaultVoiceId = if ($existingVoiceId) { $existingVoiceId } else { "UgBBYS2sOqTuMpoF3BR0" }
Write-Host "  ARTY Voice ID (press Enter to keep default: $defaultVoiceId):" -ForegroundColor DarkGray
$inputVoiceId = Read-Host "  ElevenLabs Voice ID"
if (-not $inputVoiceId) { $inputVoiceId = $defaultVoiceId }

# -- Write configuration ------------------------------------------------------
Write-Step "Writing configuration..."
$envContent = @"
ANTHROPIC_API_KEY=$inputAnthropicKey
ELEVENLABS_API_KEY=$inputElevenLabsKey
ARTY_VOICE_ID=$inputVoiceId
PUSH_TO_TALK=false
WAKE_WORD=hey arty
MEMORY_DB_PATH=./data/arty_memory.db
CHROMA_PATH=./data/chroma
"@
# Write without BOM — PowerShell 5 Set-Content UTF8 adds BOM which breaks python-dotenv
[System.IO.File]::WriteAllText("$InstallDir\.env", $envContent, (New-Object System.Text.UTF8Encoding $false))
Write-OK "Configuration written."

# -- Desktop shortcut ---------------------------------------------------------
Write-Step "Creating desktop shortcut..."
$launchScript = "@echo off`r`ncd /d `"$InstallDir`"`r`ncall venv\Scripts\activate.bat`r`npython main.py`r`npause"
$launchScript | Out-File -FilePath "$InstallDir\Run ARTY.bat" -Encoding ASCII

$desktopPath = [System.Environment]::GetFolderPath("Desktop")
if (-not (Test-Path $desktopPath)) {
    $desktopPath = "$env:USERPROFILE\Desktop"
    New-Item -ItemType Directory -Force -Path $desktopPath | Out-Null
}

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$desktopPath\ARTY.lnk")
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
