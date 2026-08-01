$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name "ValorantVODCoach" `
    app.py

Write-Host ""
Write-Host "Build complete: dist\ValorantVODCoach.exe"
