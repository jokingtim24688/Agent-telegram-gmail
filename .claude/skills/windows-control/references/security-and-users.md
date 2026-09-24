# Security and user accounts

This area is about protecting the user's own machine. Keep security features on, make targeted
exceptions rather than turning things off, and don't help get into accounts, data or machines
that aren't the user's own.

## Microsoft Defender

```powershell
Get-MpComputerStatus | Select-Object AMRunningMode, RealTimeProtectionEnabled, AntivirusSignatureLastUpdated, QuickScanEndTime, FullScanEndTime
Update-MpSignature                                        # update definitions
Start-MpScan -ScanType QuickScan                          # minutes;  FullScan takes hours
Start-MpScan -ScanType CustomScan -ScanPath "$HOME\Downloads"
Get-MpThreatDetection | Select-Object InitialDetectionTime, ThreatID, ActionSuccess, Resources   # what was found
Get-MpThreat                                              # threat names and severity
Start-MpWDOScan                                           # offline scan: reboots into a scanner for stubborn malware (confirm first)
```

`AMRunningMode` = "Passive" or "EDR Block Mode" means another antivirus is the primary one.
Check `Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntivirusProduct`.

**Exclusions** (admin) make a folder invisible to scanning. Add them only for a specific,
explained need (a dev build folder that Defender slows down), keep them narrow, and never
exclude Downloads, the user profile or a whole drive:

```powershell
Add-MpPreference -ExclusionPath 'C:\Projects\bigrepo\node_modules'
Get-MpPreference | Select-Object ExclusionPath, ExclusionProcess ; Remove-MpPreference -ExclusionPath '...'
```

If Defender blocks a file the user trusts, look at *what* was detected first
(`Get-MpThreatDetection`). Quarantined items are restored from Windows Security → Protection
history (`Start-Process windowsdefender://threat`). Don't restore anything flagged as a trojan,
stealer or ransomware without warning the user plainly.

**Controlled folder access** (ransomware protection) silently blocks apps from writing to
Documents, Desktop and Pictures. If a program "can't save" there:
`(Get-MpPreference).EnableControlledFolderAccess` (1 = on). Allow that one app with
`Add-MpPreference -ControlledFolderAccessAllowedApplications 'C:\path\app.exe'` rather than
turning the feature off.

## Is something suspicious running?

```powershell
# Running processes whose files aren't signed, or that run from temp/user folders
Get-Process | Where-Object Path | ForEach-Object {
  $sig = Get-AuthenticodeSignature $_.Path
  if ($sig.Status -ne 'Valid' -or $_.Path -match '\\AppData\\Local\\Temp\\|\\Users\\Public\\') {
    [pscustomobject]@{ Name = $_.Name; Pid = $_.Id; Path = $_.Path; Signature = $sig.Status }
  }
}
# Everything that starts automatically: Sysinternals Autoruns (winget install Microsoft.Sysinternals.Autoruns)
Get-CimInstance Win32_StartupCommand | Select-Object Name, Command, Location
Get-ScheduledTask | Where-Object { $_.TaskPath -notlike '\Microsoft\*' } | Select-Object TaskPath, TaskName, State
Get-NetTCPConnection -State Established | Select-Object RemoteAddress, RemotePort, @{n='Process';e={(Get-Process -Id $_.OwningProcess).Path}}
```

Unsigned doesn't mean malicious (many small tools are unsigned). Present findings as "worth a
look", with the path and the reason. If something looks genuinely bad, run a Defender custom
scan on it, and suggest a second opinion by uploading the file hash (not the file) to
VirusTotal.

## BitLocker / device encryption

```powershell
Get-BitLockerVolume | Select-Object MountPoint, VolumeStatus, ProtectionStatus, EncryptionPercentage   # admin
manage-bde -status
(Get-BitLockerVolume -MountPoint C:).KeyProtector | Where-Object KeyProtectorType -eq RecoveryPassword   # the recovery key (admin)
```

Before any BIOS/UEFI update, TPM change or disk move, make sure the user has their recovery
key saved. It's usually at <https://aka.ms/myrecoverykey> for Microsoft-account PCs.
Suspending (`Suspend-BitLocker -MountPoint C: -RebootCount 1`) is the safe way to update
firmware. Never decrypt or turn BitLocker off unless asked.

## Local users and groups

```powershell
whoami ; whoami /groups | Select-String 'Administrators'
Get-LocalUser | Select-Object Name, Enabled, LastLogon, PasswordRequired
Get-LocalGroupMember Administrators
New-LocalUser -Name 'kid' -Password (Read-Host -AsSecureString 'Password') -FullName 'Kid'   # admin; the user types the password
Add-LocalGroupMember -Group Users -Member 'kid'
Disable-LocalUser -Name 'olduser'                                        # safer than Remove-LocalUser; keeps the profile
Start-Process ms-settings:family-group                                  # family accounts and parental controls
```

Don't lock the user out: never remove the last administrator, disable the account the
session runs as, or change a password without the user typing it themselves.

## Passwords and secrets for scripts

Never put passwords in plain text in scripts or scheduled tasks.

```powershell
cmdkey /list                                              # Windows Credential Manager entries (names only)
Get-Credential | Export-Clixml "$HOME\.secrets\nas.xml"   # encrypted with DPAPI: only this user on this PC can read it
$cred = Import-Clixml "$HOME\.secrets\nas.xml"
# Cross-platform vault: Install-Module Microsoft.PowerShell.SecretManagement, Microsoft.PowerShell.SecretStore -Scope CurrentUser
```

## UAC, SmartScreen, "Windows protected your PC"

- Don't lower UAC or turn off SmartScreen. For a trusted downloaded file, `Unblock-File`
  clears the mark of the web. The user can also click **More info → Run anyway** once.
- A "Windows protected your PC" prompt on an unsigned download is normal. Check the
  publisher and hash (`files-and-search.md`) and tell the user what you found.

## Privacy quick wins (user-level, reversible)

```powershell
Start-Process ms-settings:privacy                          # hub: location, camera, mic, activity history
Start-Process ms-settings:privacy-general                  # advertising ID, tailored experiences
Get-AppxPackage | Where-Object Name -match 'Bing|Xbox|Clipchamp|Solitaire' | Select-Object Name   # candidates to remove (see apps-and-processes.md)
```

Avoid "debloat" scripts from the internet. They often disable Update, Defender or the Store,
and break things months later. Remove specific apps the user names instead.
