# Extends the Windows Server evaluation shortly before it expires, so that
# Windows never starts shutting itself down every hour. Its scheduled task runs
# it as SYSTEM at every startup, because the VM is usually shut down, and daily,
# for a VM that stays running. It starts sshd only when Windows will not
# restart, so that no SSH session starts work that a restart would interrupt.

$ErrorActionPreference = 'Stop'

$windowsApplicationId = '55c92734-d682-4d71-983e-d6ec3f16059f'
$product = Get-CimInstance -ClassName SoftwareLicensingProduct -Filter "ApplicationID = '$windowsApplicationId' AND PartialProductKey IS NOT NULL"
$licensingService = Get-CimInstance -ClassName SoftwareLicensingService
# GracePeriodRemaining is in minutes.
$daysRemaining = $product.GracePeriodRemaining / 1440
# sshd shows this file before every session, on stderr, so that nobody is
# surprised when an evaluation that cannot be extended expires.
$banner = 'C:\ProgramData\ssh\define_banner.txt'
$bannerText = ''
if ($daysRemaining -lt 14) {
    if ($licensingService.RemainingWindowsReArmCount -gt 0) {
        Invoke-CimMethod -InputObject $licensingService -MethodName ReArmWindows | Out-Null
        # The extension takes effect only after a restart.
        Restart-Computer -Force
        return
    }
    $expiry = (Get-Date).AddMinutes($product.GracePeriodRemaining).ToString('yyyy-MM-dd')
    $bannerText = "The Windows evaluation ends on $expiry and cannot be extended. Recreate the VM; see tools/windows_vm/README.md.`r`n"
}
[IO.File]::WriteAllText($banner, $bannerText)
Start-Service -Name sshd
