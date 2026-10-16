<#
.SYNOPSIS
Stops and removes the SM Scolers bridge Windows service.

.DESCRIPTION
Stops the service and removes it with NSSM. By default the install directory (config, key,
logs, venv) is left in place so it can be reinstalled or inspected; pass -RemoveData to delete
it as well. Needs an elevated prompt unless -DryRun is used. Works in Windows PowerShell 5.1
and PowerShell 7.

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

function Test-Elevated {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    return ([Security.Principal.WindowsPrincipal]$id).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
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
    if ($DryRun) { Write-Warning $msg; $nssm = 'nssm.exe' } else { throw $msg }
}

$InstallDir = [System.IO.Path]::GetFullPath($InstallDir)

$existing = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($existing) {
    if ($existing.Status -ne 'Stopped') {
        Invoke-Native $nssm @('stop', $ServiceName)
    }
    Invoke-Native $nssm @('remove', $ServiceName, 'confirm')
} else {
    Write-Host "Service '$ServiceName' is not installed; nothing to remove."
}

if ($RemoveData) {
    $root = [System.IO.Path]::GetPathRoot($InstallDir).TrimEnd('\')
    $programData = [System.IO.Path]::GetFullPath($env:ProgramData).TrimEnd('\')
    $target = $InstallDir.TrimEnd('\')
    if ($target -eq $root -or $target -eq $programData) {
        throw "Refusing to delete '$InstallDir': not a dedicated install directory."
    }
    if (Test-Path -LiteralPath $InstallDir) {
        if ($DryRun) {
            Write-Host "[dry-run] Remove directory $InstallDir (config, key, logs, venv)"
        } else {
            Write-Host "Removing $InstallDir"
            Remove-Item -LiteralPath $InstallDir -Recurse -Force
        }
    } else {
        Write-Host "$InstallDir does not exist; no data to remove."
    }
} else {
    Write-Host "Data left in place at $InstallDir (config, key, logs, venv). Re-run with -RemoveData to delete it."
}

if ($DryRun) { Write-Host '[dry-run] Done. Nothing was changed.' }
