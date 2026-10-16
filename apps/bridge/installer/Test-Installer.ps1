<#
.SYNOPSIS
Self-test for the installer scripts: parse check plus -DryRun output check. Changes nothing.

.DESCRIPTION
1. Parses install-service.ps1 and uninstall-service.ps1 and fails on any syntax error.
2. Runs both with -DryRun against a temporary install directory and a dummy service-account
   file, asserts the expected [dry-run] lines are printed, and asserts nothing was created
   in the temporary install directory.
Exits 0 when every check passes, 1 otherwise. Never installs, starts or removes a service.

.EXAMPLE
pwsh -File .\Test-Installer.ps1

.EXAMPLE
powershell.exe -File .\Test-Installer.ps1
#>
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$failures = New-Object System.Collections.Generic.List[string]
function Assert-That([bool]$Condition, [string]$Message) {
    if ($Condition) { Write-Host "  PASS  $Message" }
    else { Write-Host "  FAIL  $Message"; $script:failures.Add($Message) }
}

$installScript = Join-Path $PSScriptRoot 'install-service.ps1'
$uninstallScript = Join-Path $PSScriptRoot 'uninstall-service.ps1'
$hostExe = (Get-Process -Id $PID).Path
Write-Host "Host: $hostExe (PowerShell $($PSVersionTable.PSVersion))"

# ---- (a) parse check --------------------------------------------------------------------------
Write-Host 'Parse check'
foreach ($script in @($installScript, $uninstallScript)) {
    $tokens = $null
    $errors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($script, [ref]$tokens, [ref]$errors)
    $count = if ($errors) { @($errors).Count } else { 0 }
    Assert-That ($count -eq 0) "$(Split-Path $script -Leaf) parses with 0 errors"
    if ($count -gt 0) { $errors | ForEach-Object { Write-Host "    $($_.Message) (line $($_.Extent.StartLineNumber))" } }
}

# ---- (b) dry runs -----------------------------------------------------------------------------
$work = Join-Path ([System.IO.Path]::GetTempPath()) ('bridge-installer-test-' + [guid]::NewGuid().ToString('N'))
$installDir = Join-Path $work 'InstallDir'
$dummyKey = Join-Path $work 'dummy-sa.json'
New-Item -ItemType Directory -Path $work | Out-Null
try {
    Set-Content -LiteralPath $dummyKey -Value '{"type":"service_account","private_key":"DUMMY-SECRET-DO-NOT-ECHO"}'
    $fakeNssm = Join-Path $work 'nssm.exe'
    Set-Content -LiteralPath $fakeNssm -Value 'not a real nssm'

    Write-Host 'install-service.ps1 -DryRun'
    $out = (& $hostExe -NoProfile -ExecutionPolicy Bypass -File $installScript `
            -ServiceAccountPath $dummyKey -ProjectId test-project -InstallDir $installDir `
            -ServiceName SMScolersBridgeSelfTest -NssmPath $fakeNssm -DryRun 2>&1 | Out-String)
    $exit = $LASTEXITCODE
    Write-Host $out
    Assert-That ($exit -eq 0) 'install dry-run exits 0'
    $lines = @($out -split "`r?`n" | Where-Object { $_.Trim() })
    $dry = @($lines | Where-Object { $_ -like '[[]dry-run]*' })
    Assert-That ($dry.Count -gt 10) "install dry-run printed [dry-run] lines ($($dry.Count))"
    Assert-That (@($lines | Where-Object { $_ -notlike '[[]dry-run]*' -and $_ -notmatch '^\s*$' -and $_ -notmatch 'WARNING' }).Count -eq 0) 'every non-warning output line is prefixed [dry-run]'
    Assert-That ($out -match 'pip install') 'has pip install line'
    Assert-That ($out -match 'AppExit Default Restart') 'has AppExit Default Restart'
    Assert-That ($out -match 'AppRestartDelay 5000') 'has AppRestartDelay 5000'
    Assert-That ($out -match 'AppStopMethodConsole 15000') 'has AppStopMethodConsole 15000'
    Assert-That ($out -match 'SERVICE_AUTO_START') 'has SERVICE_AUTO_START'
    Assert-That ($out -match '--config') 'has --config argument'
    Assert-That ($out -match 'AppRotateFiles 1' -and $out -match 'AppRotateBytes 1048576') 'has log rotation settings'
    Assert-That ($out -match 'icacls\S*\s.*/inheritance:r') 'has icacls /inheritance:r'
    Assert-That ($out -notmatch 'DUMMY-SECRET-DO-NOT-ECHO') 'does not echo key contents'

    Write-Host 'uninstall-service.ps1 -DryRun -RemoveData'
    $uout = (& $hostExe -NoProfile -ExecutionPolicy Bypass -File $uninstallScript `
            -ServiceName SMScolersBridgeSelfTest -InstallDir $installDir -NssmPath $fakeNssm -DryRun 2>&1 | Out-String)
    $uexit = $LASTEXITCODE
    Write-Host $uout
    Assert-That ($uexit -eq 0) 'uninstall dry-run exits 0'
    Assert-That ($uout -match '\[dry-run\]') 'uninstall dry-run printed [dry-run] lines'
    Assert-That ($uout -match 'Data left in place') 'uninstall without -RemoveData says data is left'

    $uout2 = (& $hostExe -NoProfile -ExecutionPolicy Bypass -File $uninstallScript `
            -ServiceName SMScolersBridgeSelfTest -InstallDir $installDir -NssmPath $fakeNssm -RemoveData -DryRun 2>&1 | Out-String)
    Assert-That ($LASTEXITCODE -eq 0) 'uninstall -RemoveData dry-run exits 0'

    Assert-That (-not (Test-Path -LiteralPath $installDir)) 'nothing was created under the temp InstallDir'
}
finally {
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}

if ($failures.Count -gt 0) {
    Write-Host "`n$($failures.Count) check(s) FAILED"
    exit 1
}
Write-Host "`nAll checks passed."
exit 0
