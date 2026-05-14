# Artymes Updater — run this to pull the latest files from GitHub
# Right-click > Run with PowerShell

$InstallDir = "C:\Artymes"
$RepoBase   = "https://raw.githubusercontent.com/Azuredaddy/artymes/main"

Write-Host ""
Write-Host "  Artymes Updater" -ForegroundColor Cyan
Write-Host "  Downloading latest files..." -ForegroundColor Yellow
Write-Host ""

$files = @(
    "main.py", "config.py", "requirements.txt", "version.txt",
    "run_arty.bat", "run_arty_debug.bat",
    "brain/__init__.py", "brain/claude_client.py", "brain/memory.py",
    "brain/personality.py", "brain/context.py", "brain/trainer.py", "brain/computer_use.py",
    "voice/__init__.py", "voice/stt.py", "voice/tts.py",
    "eyes/__init__.py", "eyes/screen.py",
    "hands/__init__.py", "hands/control.py", "hands/win_control.py"
)

$wc = New-Object System.Net.WebClient
$wc.Headers.Add("Cache-Control", "no-cache, no-store")
$wc.Headers.Add("Pragma", "no-cache")

$ok = 0
$fail = @()
foreach ($file in $files) {
    $dir = Split-Path "$InstallDir\$file" -Parent
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    try {
        $wc.DownloadFile("$RepoBase/$file", "$InstallDir\$file")
        Write-Host "  [OK] $file" -ForegroundColor Green
        $ok++
    } catch {
        Write-Host "  [!!] $file — $_" -ForegroundColor Red
        $fail += $file
    }
}

Write-Host ""
if ($fail.Count -eq 0) {
    Write-Host "  All $ok files updated. You can launch ARTY now." -ForegroundColor Green
} else {
    Write-Host "  $ok files OK. Failed: $($fail -join ', ')" -ForegroundColor Red
}
Write-Host ""
Read-Host "  Press Enter to close"
