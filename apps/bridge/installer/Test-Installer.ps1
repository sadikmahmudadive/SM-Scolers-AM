<#
.SYNOPSIS
Self-test for the installer scripts: parse check plus -DryRun behaviour. Changes nothing.

.DESCRIPTION
Runs the full check set in child processes against every PowerShell host found (PowerShell 7
"pwsh" and Windows PowerShell 5.1 "powershell.exe", plus the current host):
  - both scripts parse with zero errors;
  - install-service.ps1 -DryRun prints the expected commands, every output line is prefixed
    [dry-run], key contents are never echoed, nothing is created in the install directory;
  - spaces in -ServiceAccountPath / -InstallDir are quoted correctly in the NSSM --config argument;
  - a relative -InstallDir resolves against the PowerShell location, not the process directory;
  - uninstall-service.ps1 -RemoveData refuses a directory that does not look like an install and
    a junction, and prints "Remove directory" for a genuine install layout (dry-run only);
  - when the Spooler service exists, the dry-runs print the stop-before-venv / remove commands
    (read-only: the dry-run never touches the service).
Exits 0 when every check passes, 1 otherwise. Never installs, starts, stops or removes a service
and never needs elevation.

.EXAMPLE
pwsh -File .\Test-Installer.ps1

.EXAMPLE
powershell.exe -File .\Test-Installer.ps1
#>
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:failures = New-Object System.Collections.Generic.List[string]
$script:currentHost = ''
function Assert-That([bool]$Condition, [string]$Message) {
    $label = "[$script:currentHost] $Message"
    if ($Condition) { Write-Host "  PASS  $label" }
    else { Write-Host "  FAIL  $label"; $script:failures.Add($label) }
}

$installScript = Join-Path $PSScriptRoot 'install-service.ps1'
$uninstallScript = Join-Path $PSScriptRoot 'uninstall-service.ps1'

function Invoke-Child([string]$HostExe, [string[]]$ArgList) {
    # Native stderr must not become a terminating error here (Windows PowerShell 5.1).
    $old = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $out = (& $HostExe @ArgList 2>&1 | Out-String)
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $old }
    return [pscustomobject]@{ Out = $out; Exit = $code }
}

function Invoke-ScriptFile([string]$HostExe, [string]$Script, [string[]]$ScriptArgs) {
    return Invoke-Child $HostExe (@('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $Script) + $ScriptArgs)
}

function Get-UnprefixedLines([string]$Out) {
    return @($Out -split "`r?`n" | Where-Object { $_.Trim() -and $_ -notlike '[[]dry-run]*' })
}

function Test-Host([string]$HostExe, [string]$Work) {
    $script:currentHost = Split-Path $HostExe -Leaf
    Write-Host "`n=== Host: $HostExe ==="
    $dummyKey = Join-Path $Work 'dummy-sa.json'
    $fakeNssm = Join-Path $Work 'nssm.exe'
    $svc = 'SMScolersBridgeSelfTest'

    # ---- parse check (in a child of this host) ----
    foreach ($script in @($installScript, $uninstallScript)) {
        $cmd = '$e=$null;$t=$null;[void][System.Management.Automation.Language.Parser]::ParseFile(''@@P@@'',[ref]$t,[ref]$e);''ERRORS='' + @($e).Count'.Replace('@@P@@', $script)
        $r = Invoke-Child $HostExe @('-NoProfile', '-Command', $cmd)
        Assert-That ($r.Out -match 'ERRORS=0') "$(Split-Path $script -Leaf) parses with 0 errors"
    }

    # ---- install dry-run ----
    $installDir = Join-Path $Work "InstallDir-$([guid]::NewGuid().ToString('N'))"
    $r = Invoke-ScriptFile $HostExe $installScript @('-ServiceAccountPath', $dummyKey, '-ProjectId', 'test-project',
        '-InstallDir', $installDir, '-ServiceName', $svc, '-NssmPath', $fakeNssm, '-DryRun')
    $out = $r.Out
    Assert-That ($r.Exit -eq 0) 'install dry-run exits 0'
    Assert-That (@(Get-UnprefixedLines $out).Count -eq 0) 'every install dry-run output line is prefixed [dry-run]'
    Assert-That ($out -match 'pip install') 'has pip install line'
    Assert-That ($out -notmatch '--force-reinstall') 'pip install does not force-reinstall'
    Assert-That ($out -match 'AppExit Default Restart') 'has AppExit Default Restart'
    Assert-That ($out -match 'AppRestartDelay 5000') 'has AppRestartDelay 5000'
    Assert-That ($out -match 'AppStopMethodConsole 15000') 'has AppStopMethodConsole 15000'
    Assert-That ($out -match 'SERVICE_AUTO_START') 'has SERVICE_AUTO_START'
    Assert-That ($out -match '--config') 'has --config argument'
    Assert-That ($out -match 'AppRotateFiles 1' -and $out -match 'AppRotateBytes 1048576') 'has log rotation settings'
    Assert-That ($out -match 'icacls\S*\s.*serviceAccountKey\.json /inheritance:r') 'has icacls /inheritance:r on the key'
    Assert-That ($out -match '\(OI\)\(CI\)F') 'has directory-level icacls grant (OI)(CI)F'
    Assert-That ($out.IndexOf('(OI)(CI)F') -ge 0 -and $out.IndexOf('(OI)(CI)F') -lt $out.IndexOf('Copy service-account key')) 'directory ACL is applied before the key is copied'
    Assert-That ($out -match 'would stop existing service first if running') 'has stop-first dry-run line'
    Assert-That ($out -notmatch 'DUMMY-SECRET-DO-NOT-ECHO') 'does not echo key contents'
    Assert-That (-not (Test-Path -LiteralPath $installDir)) 'install dry-run created nothing under InstallDir'

    # ---- spaces in paths ----
    $spaceKeyDir = Join-Path $Work 'key dir'
    New-Item -ItemType Directory -Force -Path $spaceKeyDir | Out-Null
    $spaceKey = Join-Path $spaceKeyDir 'sa key.json'
    Set-Content -LiteralPath $spaceKey -Value '{"type":"service_account","private_key":"DUMMY-SECRET-DO-NOT-ECHO"}'
    $spaceInstall = Join-Path $Work 'install dir with spaces'
    $r = Invoke-ScriptFile $HostExe $installScript @('-ServiceAccountPath', $spaceKey, '-ProjectId', 'test-project',
        '-InstallDir', $spaceInstall, '-ServiceName', $svc, '-NssmPath', $fakeNssm, '-DryRun')
    $expected = '"--config \"' + $spaceInstall + '\config.json\""'
    Assert-That ($r.Exit -eq 0) 'spaces: install dry-run exits 0'
    Assert-That ($r.Out.Contains($expected)) 'spaces: --config NSSM argument is quoted correctly'
    Assert-That ($r.Out.Contains('icacls.exe "' + $spaceInstall + '" /inheritance:r')) 'spaces: icacls directory argument is quoted'
    Assert-That ($r.Out.Contains('"' + (Join-Path $spaceInstall 'venv') + '"')) 'spaces: venv path is quoted'
    Assert-That (@(Get-UnprefixedLines $r.Out).Count -eq 0) 'spaces: every output line is prefixed [dry-run]'
    Assert-That (-not (Test-Path -LiteralPath $spaceInstall)) 'spaces: nothing created'

    # ---- relative InstallDir resolves against the PowerShell location ----
    $loc = Join-Path $Work 'cwd-test'
    New-Item -ItemType Directory -Force -Path $loc | Out-Null
    $cmd = "Set-Location -LiteralPath '$loc'; & '$installScript' -ServiceAccountPath '$dummyKey' -ProjectId p -InstallDir .\rel -ServiceName $svc -NssmPath '$fakeNssm' -DryRun"
    $r = Invoke-Child $HostExe @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', $cmd)
    Assert-That ($r.Out.Contains((Join-Path $loc 'rel'))) 'relative InstallDir (install) is resolved under the current PowerShell location'
    $cmd = "Set-Location -LiteralPath '$loc'; & '$uninstallScript' -ServiceName $svc -InstallDir .\rel -NssmPath '$fakeNssm' -DryRun"
    $r = Invoke-Child $HostExe @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', $cmd)
    Assert-That ($r.Out.Contains((Join-Path $loc 'rel'))) 'relative InstallDir (uninstall) is resolved under the current PowerShell location'
    Assert-That (-not (Test-Path -LiteralPath (Join-Path $loc 'rel'))) 'relative dry-run created nothing'

    # ---- uninstall dry-runs ----
    $r = Invoke-ScriptFile $HostExe $uninstallScript @('-ServiceName', $svc, '-InstallDir', $installDir, '-NssmPath', $fakeNssm, '-DryRun')
    Assert-That ($r.Exit -eq 0) 'uninstall dry-run exits 0'
    Assert-That (@(Get-UnprefixedLines $r.Out).Count -eq 0) 'every uninstall dry-run output line is prefixed [dry-run]'
    Assert-That ($r.Out -match 'Data left in place') 'uninstall without -RemoveData says data is left'

    $fakeInstall = Join-Path $Work 'fake install'
    New-Item -ItemType Directory -Force -Path (Join-Path $fakeInstall 'logs') | Out-Null
    Set-Content -LiteralPath (Join-Path $fakeInstall 'config.json') -Value '{}'
    $r = Invoke-ScriptFile $HostExe $uninstallScript @('-ServiceName', $svc, '-InstallDir', $fakeInstall, '-NssmPath', $fakeNssm, '-RemoveData', '-DryRun')
    Assert-That ($r.Exit -eq 0) 'uninstall -RemoveData dry-run exits 0 for an install-like directory'
    Assert-That ($r.Out.Contains("[dry-run] Remove directory $fakeInstall")) 'uninstall -RemoveData dry-run prints [dry-run] Remove directory <path>'
    Assert-That (@(Get-UnprefixedLines $r.Out).Count -eq 0) 'every uninstall -RemoveData dry-run line is prefixed [dry-run]'
    Assert-That (Test-Path -LiteralPath $fakeInstall) 'dry-run left the directory in place'

    $notInstall = Join-Path $Work 'not-an-install'
    New-Item -ItemType Directory -Force -Path $notInstall | Out-Null
    Set-Content -LiteralPath (Join-Path $notInstall 'other.txt') -Value 'keep me'
    $r = Invoke-ScriptFile $HostExe $uninstallScript @('-ServiceName', $svc, '-InstallDir', $notInstall, '-NssmPath', $fakeNssm, '-RemoveData', '-DryRun')
    Assert-That ($r.Exit -ne 0) 'uninstall -RemoveData refuses a directory without config.json (non-zero exit)'
    Assert-That (($r.Out -replace '\s+', ' ') -match 'does not look like a bridge install') 'refusal explains why'
    Assert-That (Test-Path -LiteralPath (Join-Path $notInstall 'other.txt')) 'refused directory is untouched'

    $real = Join-Path $Work 'real-install'
    $junction = Join-Path $Work 'junction-install'
    New-Item -ItemType Directory -Force -Path (Join-Path $real 'logs') | Out-Null
    Set-Content -LiteralPath (Join-Path $real 'config.json') -Value '{}'
    $null = & cmd.exe /c mklink /J "$junction" "$real"
    Assert-That (Test-Path -LiteralPath $junction) 'test junction was created'
    $r = Invoke-ScriptFile $HostExe $uninstallScript @('-ServiceName', $svc, '-InstallDir', $junction, '-NssmPath', $fakeNssm, '-RemoveData', '-DryRun')
    Assert-That ($r.Exit -ne 0) 'uninstall -RemoveData refuses a junction (non-zero exit)'
    Assert-That (($r.Out -replace '\s+', ' ') -match 'junction') 'junction refusal explains why'
    Assert-That (Test-Path -LiteralPath (Join-Path $real 'config.json')) 'junction target is untouched'
    $null = & cmd.exe /c rmdir "$junction"

    # ---- existing service (read-only): Spooler exists on every normal Windows install ----
    $spooler = Get-Service -Name Spooler -ErrorAction SilentlyContinue
    if ($spooler -and [string]$spooler.Status -ne 'Stopped') {
        $r = Invoke-ScriptFile $HostExe $installScript @('-ServiceAccountPath', $dummyKey, '-ProjectId', 'p',
            '-InstallDir', $installDir, '-ServiceName', 'Spooler', '-NssmPath', $fakeNssm, '-DryRun')
        $iStop = $r.Out.IndexOf('nssm.exe stop Spooler')
        $iVenv = $r.Out.IndexOf('-m venv')
        Assert-That ($iStop -ge 0 -and $iStop -lt $iVenv) 'existing running service: stop is printed before the venv step'
        Assert-That ($r.Out -match 'nssm\.exe set Spooler Application') 'existing service: settings are updated with nssm set'
        Assert-That (@(Get-UnprefixedLines $r.Out).Count -eq 0) 'existing service: every line is prefixed [dry-run]'
        $r = Invoke-ScriptFile $HostExe $uninstallScript @('-ServiceName', 'Spooler', '-InstallDir', $installDir, '-NssmPath', $fakeNssm, '-DryRun')
        Assert-That ($r.Out -match 'nssm\.exe stop Spooler' -and $r.Out -match 'nssm\.exe remove Spooler confirm') 'existing service: uninstall dry-run prints stop and remove'
    } else {
        Write-Host '  SKIP  Spooler service not running; existing-service dry-run checks skipped'
    }
}

# ---- hosts ------------------------------------------------------------------------------------
$hosts = New-Object System.Collections.Generic.List[string]
$currentHostExe = (Get-Process -Id $PID).Path
$hosts.Add($currentHostExe)
foreach ($name in @('pwsh.exe', 'powershell.exe')) {
    $c = Get-Command $name -ErrorAction SilentlyContinue
    if ($c -and -not ($hosts | Where-Object { $_ -ieq $c.Source })) { $hosts.Add($c.Source) }
}
Write-Host "Running under PowerShell $($PSVersionTable.PSVersion); hosts under test: $($hosts -join ', ')"

$work = Join-Path ([System.IO.Path]::GetTempPath()) ('bridge-installer-test-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $work | Out-Null
try {
    Set-Content -LiteralPath (Join-Path $work 'dummy-sa.json') -Value '{"type":"service_account","private_key":"DUMMY-SECRET-DO-NOT-ECHO"}'
    Set-Content -LiteralPath (Join-Path $work 'nssm.exe') -Value 'not a real nssm'
    foreach ($h in $hosts) { Test-Host $h $work }
}
finally {
    # remove any leftover junction link first so recursion can never follow it
    Get-ChildItem -LiteralPath $work -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Attributes -band [System.IO.FileAttributes]::ReparsePoint } |
        ForEach-Object { & cmd.exe /c rmdir "$($_.FullName)" | Out-Null }
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}

if ($script:failures.Count -gt 0) {
    Write-Host "`n$($script:failures.Count) check(s) FAILED"
    $script:failures | ForEach-Object { Write-Host "  - $_" }
    exit 1
}
Write-Host "`nAll checks passed."
exit 0
