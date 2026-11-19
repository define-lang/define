# Installs every pending Windows update. A scheduled task runs it as SYSTEM
# daily at 3:00, when an agent is least likely to be using the VM, and with
# -Restart, so that Windows restarts when an update needs it. Windows Update
# installs nothing remotely, so this runs as a scheduled task rather than over
# SSH. first_logon.ps1 also runs it once, without -Restart, before setup's
# final shutdown.

param([switch]$Restart)

$ErrorActionPreference = 'Stop'

$session = New-Object -ComObject Microsoft.Update.Session
$pending = $session.CreateUpdateSearcher().Search("IsInstalled=0 and Type='Software' and IsHidden=0").Updates
if ($pending.Count -eq 0) {
    return
}
$updates = New-Object -ComObject Microsoft.Update.UpdateColl
foreach ($update in $pending) {
    if (-not $update.EulaAccepted) {
        $update.AcceptEula()
    }
    $updates.Add($update) | Out-Null
}
$downloader = $session.CreateUpdateDownloader()
$downloader.Updates = $updates
$downloader.Download() | Out-Null
$installer = $session.CreateUpdateInstaller()
$installer.Updates = $updates
$installation = $installer.Install()
if ($Restart -and $installation.RebootRequired) {
    Restart-Computer -Force
}
