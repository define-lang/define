# Serves remote execution for the Windows tests job until that job sends its
# status, and fails unless the status is success. Failing whenever the tests
# fail makes "Re-run failed jobs" rerun this job too, since the tests need it.
#
# The tests job waits for this machine to take the name $ReadyHostname, so it
# takes that name only once rbe serves and the status listener is up.

param(
    [Parameter(Mandatory)] [string] $Rbe,
    [Parameter(Mandatory)] [string] $Root,
    [Parameter(Mandatory)] [long] $MaxCasBytes,
    [Parameter(Mandatory)] [int] $Port,
    [Parameter(Mandatory)] [int] $StatusPort,
    [Parameter(Mandatory)] [string] $ReadyHostname
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true

# Defender scanning every file that rbe writes makes uploads many times slower.
Add-MpPreference -ExclusionPath $Root
$null = New-NetFirewallRule -Name rbe -DisplayName rbe -Direction Inbound -Protocol TCP -LocalPort $Port, $StatusPort -Action Allow

$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Any, $StatusPort)
$listener.Start()

$startInfo = [System.Diagnostics.ProcessStartInfo]::new($Rbe, "--root `"$Root`" --listen :$Port --max_cas_bytes $MaxCasBytes")
$startInfo.RedirectStandardError = $true
$rbeProcess = [System.Diagnostics.Process]::Start($startInfo)
do {
    $line = $rbeProcess.StandardError.ReadLine()
    if ($null -eq $line) {
        $rbeProcess.WaitForExit()
        throw "rbe exited with code $($rbeProcess.ExitCode) before serving."
    }
    Write-Host $line
} until ($line.Contains('serving on'))
# rbe would block once its log filled the pipe.
$rbeLog = $rbeProcess.StandardError.ReadToEndAsync()

tailscale set "--hostname=$ReadyHostname"

$connection = $listener.AcceptTcpClientAsync()
$null = [System.Threading.Tasks.Task]::WaitAny($connection, $rbeProcess.WaitForExitAsync())
if ($rbeProcess.HasExited) {
    Write-Host $rbeLog.Result
    throw "rbe exited with code $($rbeProcess.ExitCode)."
}
$status = [System.IO.StreamReader]::new($connection.Result.GetStream()).ReadLine()
# A later step saves the store, so rbe must not be writing to it.
$rbeProcess.Kill()
$rbeProcess.WaitForExit()
if ($status -ne 'success') {
    throw "The Windows tests job finished with status '$status'."
}
