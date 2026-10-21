# Sets up Windows for building and testing Define. Windows Setup runs this once,
# as Administrator, at the first logon. It shuts Windows down only when every
# step succeeds, which is how create_windows_vm.py knows that setup finished.
# A failure leaves Windows running with the error in C:\define-setup.log.

$ErrorActionPreference = 'Stop'
# Progress bars make Invoke-WebRequest many times slower.
$ProgressPreference = 'SilentlyContinue'
Start-Transcript -Path C:\define-setup.log

function Invoke-Checked([string]$Path, [string[]]$Arguments) {
    & $Path @Arguments
    # Windows PowerShell does not stop on a failing native command.
    if ($LASTEXITCODE -ne 0) {
        throw "$Path exited with $LASTEXITCODE"
    }
}

# Start-Process waits for installers that run detached from the console.
function Invoke-Installer([string]$Path, [string[]]$Arguments) {
    $process = Start-Process -FilePath $Path -ArgumentList $Arguments -Wait -PassThru
    # 3010 means that the install succeeded and needs a restart, which the
    # final shutdown provides.
    if ($process.ExitCode -notin 0, 3010) {
        throw "$Path exited with $($process.ExitCode)"
    }
}

function Get-LatestReleaseAsset([string]$Repository, [string]$Pattern) {
    $release = Invoke-RestMethod "https://api.github.com/repos/$Repository/releases/latest"
    return ($release.assets | Where-Object name -Match $Pattern).browser_download_url
}

function Save-Download([string]$Url, [string]$Name) {
    $path = Join-Path $env:TEMP $Name
    Invoke-WebRequest -Uri $Url -OutFile $path
    return $path
}

# Windows Setup keeps copies of the answer file, which holds the Administrator
# password in plain text.
Get-ChildItem C:\Windows\Panther -Filter unattend*.xml -Recurse | Remove-Item

$virtioDrive = (Get-Volume | Where-Object FileSystemLabel -Like 'virtio-win*').DriveLetter
Invoke-Installer msiexec.exe @('/i', "${virtioDrive}:\virtio-win-gt-x64.msi", '/qn', '/norestart')
Invoke-Installer msiexec.exe @('/i', "${virtioDrive}:\guest-agent\qemu-ga-x86_64.msi", '/qn', '/norestart')
# extend_evaluation.ps1 starts the guest agent after sshd, so that the host can
# wait for the agent to know when SSH is ready.
Set-Service -Name QEMU-GA -StartupType Manual

# GitHub's Windows runners have PowerShell 7, so SSH sessions use it too.
$powerShellInstaller = Save-Download (Get-LatestReleaseAsset PowerShell/PowerShell '^PowerShell-[0-9.]+-win-x64\.msi$') powershell.msi
Invoke-Installer msiexec.exe @('/i', $powerShellInstaller, '/qn', '/norestart', 'ADD_PATH=1')

# SSH logs in with a key, so an expired password would only lock the console.
Set-LocalUser -Name Administrator -PasswordNeverExpires $true

# extend_evaluation.ps1 starts sshd at each startup, once it knows that Windows
# will not restart. Starting it now creates C:\ProgramData\ssh.
Set-Service -Name sshd -StartupType Manual
Start-Service -Name sshd
$authorizedKeys = 'C:\ProgramData\ssh\administrators_authorized_keys'
Copy-Item (Join-Path $PSScriptRoot administrators_authorized_keys) $authorizedKeys
# sshd ignores the file unless only Administrators and SYSTEM can access it.
Invoke-Checked icacls.exe @($authorizedKeys, '/inheritance:r', '/grant', 'Administrators:F', '/grant', 'SYSTEM:F')
# The Banner line must precede the Match block at the end of the default
# configuration, or it would apply only to that block.
$sshdConfig = 'C:\ProgramData\ssh\sshd_config'
Set-Content -Path $sshdConfig -Value (@('Banner __PROGRAMDATA__/ssh/define_banner.txt') + (Get-Content -Path $sshdConfig))
New-ItemProperty -Path HKLM:\SOFTWARE\OpenSSH -Name DefaultShell -Value 'C:\Program Files\PowerShell\7\pwsh.exe' -PropertyType String -Force | Out-Null
New-NetFirewallRule -Name DefineSsh -DisplayName 'OpenSSH Server (Define)' -Direction Inbound -Protocol TCP -LocalPort 22 -Action Allow -Profile Any | Out-Null

# Bazel output paths are longer than the traditional Windows path limit.
New-ItemProperty -Path HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem -Name LongPathsEnabled -Value 1 -PropertyType DWord -Force | Out-Null
# Developer Mode lets unelevated processes create the symbolic links that Bazel
# and the repository's tracked symbolic links need.
New-Item -Path HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock -Force | Out-Null
New-ItemProperty -Path HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock -Name AllowDevelopmentWithoutDevLicense -Value 1 -PropertyType DWord -Force | Out-Null
# Defender scanning every file that Bazel writes makes builds much slower.
Add-MpPreference -ExclusionPath C:\src, "C:\Users\Administrator\_bazel_Administrator"

$gitInstaller = Save-Download (Get-LatestReleaseAsset git-for-windows/git '^Git-[0-9.]+-64-bit\.exe$') git-installer.exe
Invoke-Installer $gitInstaller @('/VERYSILENT', '/NORESTART', '/SUPPRESSMSGBOXES', '/SP-')
$git = 'C:\Program Files\Git\cmd\git.exe'
Invoke-Checked $git @('config', '--system', 'core.symlinks', 'true')
Invoke-Checked $git @('config', '--system', 'core.longpaths', 'true')
# Bazel runs shell actions with Git's bash.
[Environment]::SetEnvironmentVariable('BAZEL_SH', 'C:\Program Files\Git\usr\bin\bash.exe', 'Machine')

$buildTools = Save-Download https://aka.ms/vs/17/release/vs_BuildTools.exe vs_BuildTools.exe
Invoke-Installer $buildTools @('--quiet', '--wait', '--norestart', '--nocache', '--add', 'Microsoft.VisualStudio.Workload.VCTools', '--includeRecommended')

New-Item -ItemType Directory -Path C:\tools -Force | Out-Null
Invoke-WebRequest -Uri (Get-LatestReleaseAsset bazelbuild/bazelisk '^bazelisk-windows-amd64\.exe$') -OutFile C:\tools\bazelisk.exe
$machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
[Environment]::SetEnvironmentVariable('Path', "$machinePath;C:\tools", 'Machine')

Copy-Item (Join-Path $PSScriptRoot extend_evaluation.ps1) C:\tools\extend_evaluation.ps1
# Files copied from a CD are read-only, which would block updating the script.
Set-ItemProperty -Path C:\tools\extend_evaluation.ps1 -Name IsReadOnly -Value $false
$extendEvaluation = New-ScheduledTaskAction -Execute powershell.exe -Argument '-NoProfile -ExecutionPolicy Bypass -File C:\tools\extend_evaluation.ps1'
$extendEvaluationTriggers = @(
    New-ScheduledTaskTrigger -AtStartup
    New-ScheduledTaskTrigger -Daily -At 3am
)
$system = New-ScheduledTaskPrincipal -UserId SYSTEM -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName 'Extend Windows Server evaluation' -Action $extendEvaluation -Trigger $extendEvaluationTriggers -Principal $system | Out-Null

Stop-Transcript
Stop-Computer -Force
