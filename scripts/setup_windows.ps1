# Loupe setup for Windows (NVIDIA GPU). Run from the repo root in PowerShell:
#   powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$desktop = Join-Path $root "desktop"

function Need($cmd, $wingetId, $label) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        Write-Host "Installing $label with winget..."
        winget install --id $wingetId -e --accept-source-agreements --accept-package-agreements
        $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
    }
}

Need "python" "Python.Python.3.12" "Python 3.12"
Need "ollama" "Ollama.Ollama" "Ollama"

Write-Host "Creating the Python environment in desktop\.venv ..."
python -m venv (Join-Path $desktop ".venv")
$py = Join-Path $desktop ".venv\Scripts\python.exe"
& $py -m pip install --upgrade pip
& $py -m pip install -r (Join-Path $desktop "requirements.txt") platformio

$envFile = Join-Path $desktop ".env"
if (-not (Test-Path $envFile)) {
    Copy-Item (Join-Path $desktop ".env.example") $envFile
    Write-Host "Created desktop\.env. Fill it in before the next step."
}

Push-Location $desktop
$model = & $py -c "from glasses_agent import hardware as h; print(h.recommend(h.detect()))"
Pop-Location
Write-Host "Best model for this PC: $model. Downloading it (about 6 GB for qwen3-vl:8b)..."
ollama pull $model

Write-Host ""
Write-Host "Done. Next:"
Write-Host "  1. Fill in desktop\.env"
Write-Host "  2. cd desktop; .venv\Scripts\python -m glasses_agent login"
Write-Host "  3. .venv\Scripts\python -m glasses_agent        (opens the dashboard)"
