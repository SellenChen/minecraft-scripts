$ErrorActionPreference = "Stop"

$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Here

python -m PyInstaller --onefile --noconsole --name "MC-Cleaner-GUI" "mc_cleaner_gui.py"
python -m PyInstaller --onefile --console --name "MC-Cleaner-Lite" "mc_cleaner_lite.py"

$ReleaseDir = Join-Path $Here "releases"
New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
Copy-Item -LiteralPath (Join-Path $Here "dist\MC-Cleaner-GUI.exe") -Destination (Join-Path $ReleaseDir "MC-Cleaner-GUI.exe") -Force
Copy-Item -LiteralPath (Join-Path $Here "dist\MC-Cleaner-Lite.exe") -Destination (Join-Path $ReleaseDir "MC-Cleaner-Lite.exe") -Force

Write-Host "Build output:"
Get-ChildItem -LiteralPath $ReleaseDir -Filter "*.exe" | Select-Object FullName, Length
