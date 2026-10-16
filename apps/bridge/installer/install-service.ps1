<#
.SYNOPSIS
Installs (or updates) the SM Scolers bridge as an auto-starting Windows service using NSSM.

.DESCRIPTION
Creates the install directory, copies the Firebase service-account key into it (ACL restricted
to SYSTEM and Administrators), creates a Python virtual environment, installs the bridge
package from this repository, writes config.json, registers the service with NSSM and starts it.

The service starts automatically at boot and is restarted 5 seconds after any exit. NSSM
captures stdout/stderr into <InstallDir>\logs\service.log (rotated at 1 MiB). The bridge's own
rotating log (bridge.log) is written next to config.json.

The script is idempotent: when the service already exists it is stopped first (the venv files
are in use while it runs), its settings are updated with "nssm set" and it is started again. The script does NOT download NSSM; pass -NssmPath or
put nssm.exe on PATH. The contents of the key file are never printed.

Needs an elevated (Administrator) prompt unless -DryRun is used. Works in Windows PowerShell 5.1
and PowerShell 7.

.PARAMETER ServiceAccountPath
Path to the Firebase/Google service-account JSON key file. Must exist.

.PARAMETER ProjectId
Firebase project id the bridge talks to.

.PARAMETER InstallDir
Where config, key, venv and logs live. Default: %ProgramData%\SMScolersBridge.

.PARAMETER ServiceName
Windows service name. Default: SMScolersBridge.

.PARAMETER PythonExe
Python 3.12+ interpreter used to create the venv. Default: the interpreter reported by
"py -3.13", otherwise "python" from PATH.

.PARAMETER NssmPath
Path to nssm.exe. Default: nssm.exe found on PATH.

.PARAMETER DryRun
Make no changes; print each action and command that would run, prefixed with [dry-run].

.EXAMPLE
.\install-service.ps1 -ServiceAccountPath C:\keys\sa.json -ProjectId my-firebase-project

.EXAMPLE
.\install-service.ps1 -ServiceAccountPath C:\keys\sa.json -ProjectId my-project -NssmPath C:\tools\nssm.exe -DryRun
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateScript({ Test-Path -LiteralPath $_ -PathType Leaf })]
    [string]$ServiceAccountPath,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$ProjectId,

    [string]$InstallDir = (Join-Path $env:ProgramData 'SMScolersBridge'),
    [string]$ServiceName = 'SMScolersBridge',
    [string]$PythonExe,
    [string]$NssmPath,
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
    # Runs a native command (or just prints it under -DryRun). Throws on non-zero exit.
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

function Invoke-Action([string]$Description, [scriptblock]$Action) {
    if ($DryRun) { Write-Host "[dry-run] $Description"; return }
    Write-Host $Description
    & $Action
}

function Test-Elevated {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    return ([Security.Principal.WindowsPrincipal]$id).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-PythonVersion([string]$Exe) {
    try {
        $v = & $Exe -c "import sys; print('{}.{}'.format(*sys.version_info[:2]))" 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $v) { return $null }
        return [version]("$v".Trim())
    } catch { return $null }
}

function Resolve-PythonExe {
    if ($PythonExe) { return $PythonExe }
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        try {
            $found = & $py.Source -3.13 -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $found -and (Test-Path -LiteralPath "$found".Trim())) { return "$found".Trim() }
        } catch { }
    }
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) { return $python.Source }
    return $null
}

function Resolve-Nssm {
    if ($NssmPath) {
        if (Test-Path -LiteralPath $NssmPath -PathType Leaf) { return (Resolve-Path -LiteralPath $NssmPath).Path }
        return $null
    }
    $cmd = Get-Command nssm.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

# ---- preflight --------------------------------------------------------------------------------
if (-not $DryRun -and -not (Test-Elevated)) {
    throw 'This script must run from an elevated (Administrator) PowerShell. Re-run as Administrator, or use -DryRun to preview.'
}
if ($DryRun) { Write-Host '[dry-run] No changes will be made. Commands below are what WOULD run.' }

$bridgeDir = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
if (-not (Test-Path -LiteralPath (Join-Path $bridgeDir 'pyproject.toml'))) {
    throw "Cannot find the bridge package (pyproject.toml) in $bridgeDir."
}

$nssm = Resolve-Nssm
if (-not $nssm) {
    $msg = 'nssm.exe was not found. Install NSSM (https://nssm.cc) and put nssm.exe on PATH, or pass -NssmPath <path to nssm.exe>. This script does not download it.'
    if ($DryRun) { Write-Warn $msg; $nssm = 'nssm.exe' } else { throw $msg }
}

$python = Resolve-PythonExe
if (-not $python) {
    $msg = 'No Python found. Install Python 3.12 or newer (the "py" launcher or python.exe on PATH), or pass -PythonExe <path>.'
    if ($DryRun) { Write-Warn $msg; $python = 'python.exe' } else { throw $msg }
} else {
    $ver = Get-PythonVersion $python
    if (-not $ver -or $ver -lt [version]'3.12') {
        $msg = "Python 3.12 or newer is required; '$python' reports version '$ver'. Pass -PythonExe <path to Python 3.12+>."
        if ($DryRun) { Write-Warn $msg } else { throw $msg }
    }
}

# Resolve against the PowerShell location (not the .NET process directory) so relative paths mean what the user typed.
$InstallDir = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($InstallDir)
$sourceKey = (Resolve-Path -LiteralPath $ServiceAccountPath).Path
$keyPath = Join-Path $InstallDir 'serviceAccountKey.json'
$configPath = Join-Path $InstallDir 'config.json'
$venvDir = Join-Path $InstallDir 'venv'
$logsDir = Join-Path $InstallDir 'logs'
$serviceLog = Join-Path $logsDir 'service.log'
$venvPython = Join-Path $venvDir 'Scripts\python.exe'
$bridgeExe = Join-Path $venvDir 'Scripts\sm-scolers-bridge.exe'
$appParameters = '--config ' + (Format-Arg $configPath)

# ---- stop a running service first (its venv files are in use) ----------------------------------
$existing = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($existing -and [string]$existing.Status -ne 'Stopped') {
    Write-Info "Service '$ServiceName' exists (status: $($existing.Status)); stopping it before touching the venv."
    if ([string]$existing.Status -ne 'StopPending') {
        Invoke-Native $nssm @('stop', $ServiceName)
    }
    if ($DryRun) {
        Write-Host '[dry-run] would wait up to 30 s for the service to reach Stopped'
    } elseif (-not (Wait-ServiceStatus $ServiceName 'Stopped' 30)) {
        throw "Service '$ServiceName' did not stop within 30 s. Stop it manually (nssm stop $ServiceName) and re-run."
    }
} elseif ($DryRun) {
    Write-Host '[dry-run] would stop existing service first if running'
}

# ---- files ------------------------------------------------------------------------------------
# *S-1-5-18 = SYSTEM, *S-1-5-32-544 = Administrators (SIDs, so this works on any Windows language).
# The directory is locked down BEFORE the key is copied in, so the key is never readable by others.
Invoke-Action "Create directories $InstallDir and $logsDir" {
    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
    New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
}
Invoke-Native 'icacls.exe' @($InstallDir, '/inheritance:r')
Invoke-Native 'icacls.exe' @($InstallDir, '/grant:r', '*S-1-5-18:(OI)(CI)F', '*S-1-5-32-544:(OI)(CI)F')

if ($sourceKey -ne $keyPath) {
    Invoke-Action "Copy service-account key to $keyPath" {
        Copy-Item -LiteralPath $sourceKey -Destination $keyPath -Force
    }
} else {
    Write-Info "Service-account key is already at $keyPath."
}
Invoke-Native 'icacls.exe' @($keyPath, '/inheritance:r')
Invoke-Native 'icacls.exe' @($keyPath, '/grant:r', '*S-1-5-18:(F)', '*S-1-5-32-544:(F)')

# ---- venv + package ---------------------------------------------------------------------------
if ($DryRun -or -not (Test-Path -LiteralPath $venvPython)) {
    Invoke-Native $python @('-m', 'venv', $venvDir)
} else {
    Write-Info "Virtual environment already exists at $venvDir."
}
# pip always rebuilds and reinstalls a local directory requirement, so source changes are picked up.
Invoke-Native $venvPython @('-m', 'pip', 'install', '--upgrade', $bridgeDir)

# ---- config.json ------------------------------------------------------------------------------
$configJson = ([ordered]@{ service_account_path = $keyPath; project_id = $ProjectId } | ConvertTo-Json)
Invoke-Action "Write $configPath with: $(($configJson -replace '\s+', ' '))" {
    # UTF-8 without BOM so Python's json.load reads it cleanly on PowerShell 5.1 and 7.
    [System.IO.File]::WriteAllText($configPath, $configJson, (New-Object System.Text.UTF8Encoding($false)))
}

# ---- service ----------------------------------------------------------------------------------
if ($existing) {
    Write-Info "Service '$ServiceName' already exists; updating its settings."
    Invoke-Native $nssm @('set', $ServiceName, 'Application', $bridgeExe)
    Invoke-Native $nssm @('set', $ServiceName, 'AppParameters', $appParameters)
} else {
    Invoke-Native $nssm @('install', $ServiceName, $bridgeExe, $appParameters)
}

Invoke-Native $nssm @('set', $ServiceName, 'AppDirectory', $InstallDir)
Invoke-Native $nssm @('set', $ServiceName, 'DisplayName', 'SM Scolers Bridge')
Invoke-Native $nssm @('set', $ServiceName, 'Description', 'ZKTeco punches to Firestore, attendance SMS and website commands')
Invoke-Native $nssm @('set', $ServiceName, 'Start', 'SERVICE_AUTO_START')
Invoke-Native $nssm @('set', $ServiceName, 'AppExit', 'Default', 'Restart')
Invoke-Native $nssm @('set', $ServiceName, 'AppRestartDelay', '5000')
Invoke-Native $nssm @('set', $ServiceName, 'AppStopMethodConsole', '15000')
Invoke-Native $nssm @('set', $ServiceName, 'AppStdout', $serviceLog)
Invoke-Native $nssm @('set', $ServiceName, 'AppStderr', $serviceLog)
Invoke-Native $nssm @('set', $ServiceName, 'AppRotateFiles', '1')
Invoke-Native $nssm @('set', $ServiceName, 'AppRotateOnline', '1')
Invoke-Native $nssm @('set', $ServiceName, 'AppRotateBytes', '1048576')

Invoke-Native $nssm @('start', $ServiceName)

if ($DryRun) {
    Write-Host '[dry-run] would wait up to 10 s for the service to reach Running'
    Write-Host '[dry-run] Done. Nothing was changed.'
} else {
    if (Wait-ServiceStatus $ServiceName 'Running' 10) {
        Write-Host "Service '$ServiceName' is Running."
    } else {
        Write-Warning "Service '$ServiceName' is not Running after 10 s. Check $serviceLog and $(Join-Path $InstallDir 'bridge.log')."
    }
    Write-Host "Check it with: Get-Service $ServiceName"
    Write-Host "Logs: $serviceLog (service output) and $(Join-Path $InstallDir 'bridge.log') (bridge log)."
}
