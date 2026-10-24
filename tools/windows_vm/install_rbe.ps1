# Installs or updates the rbe Windows service from rbe.exe.new next to this
# script, then waits until it serves. deploy_rbe.py copies both here and runs
# this over SSH.

param(
    [Parameter(Mandatory)] [string] $Root,
    [Parameter(Mandatory)] [int] $Port,
    [Parameter(Mandatory)] [long] $MaxCasBytes
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
# Progress records reach SSH as CLIXML.
$ProgressPreference = 'SilentlyContinue'

$binary = Join-Path $PSScriptRoot 'rbe.exe'
$commandLine = "`"$binary`" --root $Root --listen :$Port --max_cas_bytes $MaxCasBytes"

if (-not [System.Diagnostics.EventLog]::SourceExists('rbe')) {
    [System.Diagnostics.EventLog]::CreateEventSource('rbe', 'Application')
}
$service = Get-Service rbe -ErrorAction SilentlyContinue
if ($service) {
    Stop-Service rbe
}
# The stopped service's process can hold its binary for a moment.
for ($attempt = 1; ; $attempt++) {
    try {
        Move-Item -Force "$binary.new" $binary
        break
    } catch {
        if ($attempt -ge 50) { throw }
        Start-Sleep -Milliseconds 200
    }
}
if ($service) {
    $null = sc.exe config rbe binPath= $commandLine
} else {
    # The service runs as LocalSystem, which can create the symlinks that
    # actions' input trees have.
    $null = New-Service -Name rbe -DisplayName 'Define remote execution' -BinaryPathName $commandLine -StartupType Automatic
}
# Restart after any failure, including the service stopping with an error.
$null = sc.exe failure rbe reset= 86400 actions= restart/5000/restart/5000/restart/5000
$null = sc.exe failureflag rbe 1
if (-not (Get-NetFirewallRule -Name rbe -ErrorAction SilentlyContinue)) {
    $null = New-NetFirewallRule -Name rbe -DisplayName 'Define remote execution' -Direction Inbound -Protocol TCP -LocalPort $Port -Action Allow
}
Start-Service rbe
for ($attempt = 1; ; $attempt++) {
    if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
        break
    }
    if ($attempt -ge 150) {
        throw 'rbe did not start serving; see its events in the Application log.'
    }
    Start-Sleep -Milliseconds 200
}
