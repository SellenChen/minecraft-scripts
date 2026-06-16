$ErrorActionPreference = "Stop"

$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Here

python -m PyInstaller --onedir --noconsole --name "MC-Cleaner-GUI" --distpath "dist-onedir" --workpath "build-onedir" "mc_cleaner_gui.py"
python -m PyInstaller --onefile --console --name "MC-Cleaner-Lite" "mc_cleaner_lite.py"

$ReleaseDir = Join-Path $Here "releases"
New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null

$GuiZip = Join-Path $ReleaseDir "MC-Cleaner-GUI-portable.zip"
if (Test-Path -LiteralPath $GuiZip) {
    Remove-Item -LiteralPath $GuiZip -Force
}
Compress-Archive -LiteralPath (Join-Path $Here "dist-onedir\MC-Cleaner-GUI") -DestinationPath $GuiZip -Force

Copy-Item -LiteralPath (Join-Path $Here "dist\MC-Cleaner-Lite.exe") -Destination (Join-Path $ReleaseDir "MC-Cleaner-Lite.exe") -Force

Write-Host "Build output:"
Get-ChildItem -LiteralPath $ReleaseDir | Where-Object { $_.Name -like "*.exe" -or $_.Name -like "*.zip" } | Select-Object FullName, Length
