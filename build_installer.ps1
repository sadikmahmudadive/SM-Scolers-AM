# SM Scolers Attendance - Full Build & Installer Script
# Usage: .\build_installer.ps1
# Requires: Python 3.x, PyInstaller, WiX Toolset v3.x

param(
    [switch]$SkipPyInstaller,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$DistDir     = Join-Path $ProjectRoot "dist\app"
$InstallerDir = Join-Path $ProjectRoot "installer"
$OutputMsi   = Join-Path $InstallerDir "SM_Scolers.msi"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  SM Scolers Attendance - Build Pipeline"     -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# --- Step 0: Clean old artifacts ---
if ($Clean) {
    Write-Host "[Clean] Removing old build artifacts..." -ForegroundColor Yellow
    Remove-Item (Join-Path $InstallerDir "*.wixobj") -Force -ErrorAction SilentlyContinue
    Remove-Item (Join-Path $InstallerDir "*.wixpdb") -Force -ErrorAction SilentlyContinue
    Remove-Item $OutputMsi -Force -ErrorAction SilentlyContinue
}

# --- Step 1: Build with PyInstaller ---
if (-not $SkipPyInstaller) {
    Write-Host "[1/4] Building app with PyInstaller..." -ForegroundColor Green
    Push-Location $ProjectRoot
    try {
        python -m PyInstaller --clean -y app.spec 2>&1 | ForEach-Object { $_.ToString() } | Select-String "ERROR|WARNING|completed successfully|Build complete" | ForEach-Object { Write-Host "       $_" }
        if (-not (Test-Path (Join-Path $DistDir "app.exe"))) {
            throw "PyInstaller build failed - app.exe not found in $DistDir"
        }
        Write-Host "       PyInstaller build completed." -ForegroundColor Green
    } finally {
        Pop-Location
    }
} else {
    Write-Host "[1/4] Skipping PyInstaller (using existing dist)..." -ForegroundColor Yellow
    if (-not (Test-Path (Join-Path $DistDir "app.exe"))) {
        throw "No existing build found at $DistDir. Run without -SkipPyInstaller."
    }
}

# --- Step 2: Harvest files with heat.exe ---
Write-Host "[2/4] Harvesting dist files with heat.exe..." -ForegroundColor Green
$PayloadWxs = Join-Path $InstallerDir "AppPayload.wxs"

heat.exe dir $DistDir `
    -cg AppPayload `
    -gg -scom -sreg -sfrag -srd `
    -dr INSTALLFOLDER `
    -var var.DistDir `
    -out $PayloadWxs 2>&1 | Out-Null

if (-not (Test-Path $PayloadWxs)) {
    throw "heat.exe failed to generate $PayloadWxs"
}
$lineCount = (Get-Content $PayloadWxs).Count
Write-Host "       Generated AppPayload.wxs ($lineCount lines)" -ForegroundColor Green

# --- Step 3: Compile with candle.exe ---
Write-Host "[3/4] Compiling WiX sources with candle.exe..." -ForegroundColor Green
Push-Location $InstallerDir
try {
    candle.exe -nologo `
        -dDistDir="$DistDir" `
        SM_Scolers.wxs `
        AppPayload.wxs `
        -ext WixUIExtension `
        -out "$InstallerDir\\" 2>&1 | ForEach-Object { Write-Host "       $_" }

    if (-not (Test-Path (Join-Path $InstallerDir "SM_Scolers.wixobj")) -or
        -not (Test-Path (Join-Path $InstallerDir "AppPayload.wixobj"))) {
        throw "candle.exe compilation failed"
    }
    Write-Host "       Compiled successfully." -ForegroundColor Green
} finally {
    Pop-Location
}

# --- Step 4: Link with light.exe ---
Write-Host "[4/4] Linking MSI with light.exe..." -ForegroundColor Green
Push-Location $InstallerDir
try {
    light.exe -nologo `
        SM_Scolers.wixobj `
        AppPayload.wixobj `
        -ext WixUIExtension `
        -out $OutputMsi `
        -b "$DistDir" 2>&1 | ForEach-Object { Write-Host "       $_" }

    if (-not (Test-Path $OutputMsi)) {
        throw "light.exe linking failed - MSI not created"
    }

    $msiSize = [math]::Round((Get-Item $OutputMsi).Length / 1MB, 1)
    Write-Host "" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host "  Build Complete!" -ForegroundColor Green
    Write-Host "  Output: $OutputMsi" -ForegroundColor Green
    Write-Host "  Size:   ${msiSize} MB" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Cyan
} finally {
    Pop-Location
}
