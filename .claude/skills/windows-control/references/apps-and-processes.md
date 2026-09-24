# Apps and processes

## Installing, updating and removing apps: winget

winget ships with Windows 10 (1809+) and 11. Always search first: IDs are exact, and names are
ambiguous ("Discord" could be several packages).

```powershell
winget search discord
winget show Discord.Discord                         # publisher, version, homepage: check it's the real one
winget install --id Discord.Discord -e --accept-source-agreements --accept-package-agreements
winget install --id Python.Python.3.12 -e --scope user   # per-user install, no admin prompt
winget list                                         # everything installed, including non-winget apps
winget list --upgrade-available
winget upgrade --id Google.Chrome -e
winget upgrade --all --accept-source-agreements --accept-package-agreements   # confirm first: it touches everything
winget uninstall --id Spotify.Spotify -e
winget export -o $HOME\apps.json ; winget import -i apps.json                  # move an app set to a new PC
```

Gotchas:
- `-e` (exact) stops `winget install vlc` from matching a different package.
- Some installers still show UAC or their own window. Tell the user to expect it.
- `winget` isn't found → the App Installer package is missing or outdated. Install it from the
  Microsoft Store (`ms-windows-store://pdp/?productid=9NBLGGH4NNS1`).
- After installing a CLI tool, the current terminal doesn't see the new PATH. See
  `troubleshooting.md` → "Refresh PATH without reopening".
- Microsoft Store apps also install through winget: `winget install 9NCBCSZSJRSB` (Spotify's
  Store ID) with `--source msstore`.

Other package managers, if the user already uses them: `choco install x -y` (admin) and
`scoop install x` (per-user, good for dev tools).

**Uninstalling without winget** (old apps):

```powershell
Get-ItemProperty HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*,
                 HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*,
                 HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\* |
  Where-Object DisplayName -like '*Zoom*' | Select-Object DisplayName, DisplayVersion, UninstallString, QuietUninstallString
# Run QuietUninstallString if present; otherwise UninstallString (which usually opens a wizard).
Get-AppxPackage *xbox* | Remove-AppxPackage       # built-in Store apps, for the current user
```

Removing built-in apps can break things (Store, Photos, Calculator are fine to remove;
anything with "Framework", "Runtime", "VCLibs" or "UI.Xaml" is a dependency, so leave it).

## Launching apps

```powershell
Start-Process notepad
Start-Process 'C:\Program Files\App\app.exe' -ArgumentList '--flag', 'value' -WorkingDirectory 'C:\work'
Start-Process chrome 'https://example.com'
Start-Process powershell -Verb RunAs                  # elevated (UAC prompt)
Start-Process .\setup.exe -ArgumentList '/S' -Wait    # wait for it to finish
```

**Can't find the exe?** Find it the way the Start menu does:

```powershell
Get-StartApps | Where-Object Name -like '*spotify*'        # Name + AppID for every Start menu entry
Start-Process explorer.exe "shell:AppsFolder\$((Get-StartApps | Where-Object Name -eq 'Spotify').AppID)"   # launch it, including Store apps
Get-Command code, git, python -ErrorAction SilentlyContinue | Select-Object Name, Source
(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe').'(default)'
```

**Protocol links** open apps directly, often to a specific place:

| Link | Opens |
|---|---|
| `ms-settings:<page>` | a Settings page (list in `settings-and-personalization.md`) |
| `spotify:` / `spotify:search:lofi` | Spotify |
| `steam://rungameid/730` / `steam://open/library` | Steam game or library |
| `discord://` | Discord |
| `mailto:someone@x.com?subject=Hi` | default mail app |
| `ms-windows-store://pdp/?productid=<id>` | a Store page |
| `calculator:` / `ms-clock:` / `ms-screenclip:` | Calculator, Clock, Snipping Tool |
| `ms-photos:` / `microsoft-edge:https://…` | Photos, Edge |
| `outlookmail:` / `msteams:` | New Outlook, Teams |

Launch any of them with `Start-Process '<link>'`. For app-specific control beyond launching
(Steam, Spotify, Blender, Minecraft), the `app-launcher-control` skill has the details.

## What's running, and closing things

```powershell
Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 15 Name, Id,
  @{n='RAM_MB';e={[math]::Round($_.WorkingSet64/1MB)}}, @{n='CPU_s';e={[math]::Round($_.CPU)}}
Get-Process chrome | Measure-Object WorkingSet64 -Sum     # total for multi-process apps
Get-Process | Where-Object MainWindowTitle | Select-Object Name, Id, MainWindowTitle   # apps with windows
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Select-Object ProcessId, CommandLine   # which script is it?

Stop-Process -Name notepad                 # asks nothing; unsaved work is lost
(Get-Process notepad).CloseMainWindow()    # polite close: the app can ask to save. Prefer this.
taskkill /IM chrome.exe /T /F              # kill a whole process tree
Get-Process | Where-Object { $_.Responding -eq $false }   # "Not responding" apps
```

Close apps with `CloseMainWindow()` (or `window.ps1 close`) first, and force-kill only if that
fails or the app is hung. Force-killing an editor or Office app loses unsaved work, so say so.
Never kill `csrss`, `wininit`, `winlogon`, `lsass`, `smss` or `services`: killing any of these
bluescreens or logs the user out.

**Which process locks a file or port?**

```powershell
Get-NetTCPConnection -LocalPort 8080 -State Listen | ForEach-Object { Get-Process -Id $_.OwningProcess }
# Files: Resource Monitor (resmon.exe) > CPU > Associated Handles > search the name.
# CLI: winget install Microsoft.Sysinternals.Handle ; handle.exe -accepteula C:\path\file.docx
```

## Startup apps

```powershell
Get-CimInstance Win32_StartupCommand | Select-Object Name, Command, Location, User
# Enabled/disabled state (what Task Manager > Startup shows):
Get-ItemProperty HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run
```

Disabling is safest from **Task Manager → Startup apps**, or with `Start-Process ms-settings:startupapps`,
because both flip the same "StartupApproved" flag and are easy to undo. To add your own
startup item, drop a shortcut in `shell:startup`:

```powershell
$startup = [Environment]::GetFolderPath('Startup')
$s = (New-Object -ComObject WScript.Shell).CreateShortcut("$startup\MyTool.lnk"); $s.TargetPath = 'C:\Tools\tool.exe'; $s.Save()
```

For scripts that must run at logon with arguments, hidden, or with a delay, a scheduled task
is better (see `automation-and-ui.md`).

## Default apps

Windows 10 and 11 block setting default apps from scripts (a hash protects the choice). Open
the right Settings page and let the user click:

```powershell
Start-Process 'ms-settings:defaultapps'
# Windows 11 deep link for one app:
Start-Process 'ms-settings:defaultapps?registeredAppUser=Google Chrome'
# Read the current default for a file type or protocol:
(Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice').ProgId
(Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.pdf\UserChoice').ProgId
```
