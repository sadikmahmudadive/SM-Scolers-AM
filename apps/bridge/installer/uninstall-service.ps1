<#
.SYNOPSIS
Stops and removes the SM Scolers bridge Windows service.

.DESCRIPTION
Stops the service and removes it with NSSM. By default the install directory (config, key,
logs, venv) is left in place so it can be reinstalled or inspected; pass -RemoveData to delete
it as well, but only when the directory looks like a bridge install (config.json plus a venv
or logs folder) and is not a junction/symlink; otherwise it refuses with a non-zero exit.
Needs an elevated prompt unless -DryRun is used. Works in Windows PowerShell 5.1 and PowerShell 7.

.PARAMETER ServiceName
Windows service name. Default: SMScolersBridge.

.PARAMETER InstallDir
Install directory used by install-service.ps1. Default: %ProgramData%\SMScolersBridge.

.PARAMETER NssmPath
Path to nssm.exe. Default: nssm.exe found on PATH.

.PARAMETER RemoveData
Also delete InstallDir (config, service-account key copy, logs and venv).

.PARAMETER DryRun
Make no changes; print each action and command that would run, prefixed with [dry-run].

.EXAMPLE
.\uninstall-service.ps1

.EXAMPLE
.\uninstall-service.ps1 -RemoveData -NssmPath C:\tools\nssm.exe
#>
[CmdletBinding()]
param(
    [string]$ServiceName = 'SMScolersBridge',
    [string]$InstallDir = (Join-Path $env:ProgramData 'SMScolersBridge'),
    [string]$NssmPath,
    [switch]$RemoveData,
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Format-Arg([string]$Arg) {
    # Quote one argument for a Windows command line (CommandLineToArgvW rules).
    if ($Arg.Length -gt 0 -and $Arg -notmatch '[\s"]') { return $Arg }
    $escaped = $Arg -replace '(\\*)"', '$1$1\"'
    $escaped = $escaped -replace '(\\+)$', '$1$1'
    return '"' + $escaped + '"'
}

function Invoke-Native([string]$Exe, [string[]]$Arguments) {
    $argLine = ($Arguments | ForEach-Object { Format-Arg $_ }) -join ' '
    $line = ((Format-Arg $Exe) + ' ' + $argLine).Trim()
    if ($DryRun) { Write-Host "[dry-run] $line"; return }
    Write-Host "> $line"
    $p = Start-Process -FilePath $Exe -ArgumentList $argLine -NoNewWindow -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw "Command failed with exit code $($p.ExitCode): $line" }
}

function Write-Info([string]$Message) {
    if ($DryRun) { Write-Host "[dry-run] $Message" } else { Write-Host $Message }
}

function Write-Warn([string]$Message) {
    if ($DryRun) { Write-Host "[dry-run] WARNING: $Message" } else { Write-Warning $Message }
}

function Wait-ServiceStatus([string]$Name, [string]$Status, [int]$Seconds) {
    # True once the service reaches $Status (a vanished service counts as Stopped), false on timeout.
    $deadline = (Get-Date).AddSeconds($Seconds)
    do {
        $svc = Get-Service -Name $Name -ErrorAction SilentlyContinue
        if (-not $svc) { return ($Status -eq 'Stopped') }
        if ([string]$svc.Status -eq $Status) { return $true }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)
    return $false
}

function Test-Elevated {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    return ([Security.Principal.WindowsPrincipal]$id).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-ReparsePoint([string]$Path) {
    $item = Get-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
    return [bool]($item -and ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint))
}

function Assert-SafeToDelete([string]$Dir) {
    # Throws (non-zero exit) unless $Dir is clearly a bridge install directory that is safe to delete.
    $root = [System.IO.Path]::GetPathRoot($Dir).TrimEnd('\')
    $programData = [System.IO.Path]::GetFullPath($env:ProgramData).TrimEnd('\')
    $target = $Dir.TrimEnd('\')
    if ($target -eq $root -or $target -eq $programData) {
        throw "Refusing to delete '$Dir': not a dedicated install directory."
    }
    if (-not (Test-Path -LiteralPath $Dir)) { return }

    $looksLikeInstall = (Test-Path -LiteralPath (Join-Path $Dir 'config.json') -PathType Leaf) -and
        ((Test-Path -LiteralPath (Join-Path $Dir 'venv\Scripts\sm-scolers-bridge.exe') -PathType Leaf) -or
         (Test-Path -LiteralPath (Join-Path $Dir 'logs') -PathType Container))
    if (-not $looksLikeInstall) {
        throw "Refusing to delete '$Dir': it does not look like a bridge install (needs config.json and venv\Scripts\sm-scolers-bridge.exe or a logs folder). Nothing was removed."
    }

    # The directory and every parent must be a real directory, not a junction/symlink.
    $p = $Dir.TrimEnd('\')
    while ($p) {
        if (Test-ReparsePoint $p) {
            throw "Refusing to delete '$Dir': '$p' is a junction/symlink (reparse point). Nothing was removed."
        }
        $parent = Split-Path -Parent $p
        if (-not $parent -or $parent -eq $p) { break }
        $p = $parent
    }
    $inner = @(Get-ChildItem -LiteralPath $Dir -Recurse -Force -Attributes ReparsePoint -ErrorAction SilentlyContinue)
    if ($inner.Count -gt 0) {
        throw "Refusing to delete '$Dir': it contains a junction/symlink ($($inner[0].FullName)). Nothing was removed."
    }
}

if (-not $DryRun -and -not (Test-Elevated)) {
    throw 'This script must run from an elevated (Administrator) PowerShell. Re-run as Administrator, or use -DryRun to preview.'
}
if ($DryRun) { Write-Host '[dry-run] No changes will be made. Commands below are what WOULD run.' }

$nssm = $null
if ($NssmPath) {
    if (Test-Path -LiteralPath $NssmPath -PathType Leaf) { $nssm = (Resolve-Path -LiteralPath $NssmPath).Path }
} else {
    $cmd = Get-Command nssm.exe -ErrorAction SilentlyContinue
    if ($cmd) { $nssm = $cmd.Source }
}
if (-not $nssm) {
    $msg = 'nssm.exe was not found. Put nssm.exe on PATH or pass -NssmPath <path to nssm.exe>.'
    if ($DryRun) { Write-Warn $msg; $nssm = 'nssm.exe' } else { throw $msg }
}

# Resolve against the PowerShell location (not the .NET process directory).
$InstallDir = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($InstallDir)

# Validate the data deletion up front so a refusal leaves the service untouched.
if ($RemoveData) { Assert-SafeToDelete $InstallDir }

$existing = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($existing) {
    if ($DryRun) {
        if ([string]$existing.Status -ne 'Stopped') { Invoke-Native $nssm @('stop', $ServiceName) }
    } else {
        if ([string]$existing.Status -eq 'StartPending') { [void](Wait-ServiceStatus $ServiceName 'Running' 15) }
        if ([string]$existing.Status -eq 'StopPending') {
            if (-not (Wait-ServiceStatus $ServiceName 'Stopped' 15)) { throw "Service '$ServiceName' is stuck in StopPending." }
        }
        $now = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
        if ($now -and [string]$now.Status -ne 'Stopped') {
            Invoke-Native $nssm @('stop', $ServiceName)
            if (-not (Wait-ServiceStatus $ServiceName 'Stopped' 30)) { throw "Service '$ServiceName' did not stop within 30 s." }
        }
    }
    Invoke-Native $nssm @('remove', $ServiceName, 'confirm')
} else {
    Write-Info "Service '$ServiceName' is not installed; nothing to remove."
}

if ($RemoveData) {
    if (Test-Path -LiteralPath $InstallDir) {
        if ($DryRun) {
            Write-Host "[dry-run] Remove directory $InstallDir (config, key, logs, venv)"
        } else {
            Write-Host "Removing $InstallDir"
            Remove-Item -LiteralPath $InstallDir -Recurse -Force
        }
    } else {
        Write-Info "$InstallDir does not exist; no data to remove."
    }
} else {
    Write-Info "Data left in place at $InstallDir (config, key, logs, venv). Re-run with -RemoveData to delete it."
}

if ($DryRun) { Write-Host '[dry-run] Done. Nothing was changed.' }
