# Automation and UI control

## Scheduled tasks: "run this every day / at login / every 15 minutes"

Save the work as a `.ps1` file first (for example `$HOME\Scripts\backup.ps1`), then register a
task that runs it. That keeps the task definition short, and the script easy to edit and test.

```powershell
$script = "$HOME\Scripts\backup.ps1"
$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
  -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`"" -WorkingDirectory "$HOME\Scripts"

# Pick one trigger:
$trigger = New-ScheduledTaskTrigger -Daily -At 8am
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday, Thursday -At 7:30pm
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 15)
$trigger = New-ScheduledTaskTrigger -Once -At '2026-10-01 09:00'           # one-off reminder

$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -ExecutionTimeLimit (New-TimeSpan -Hours 2)      # add -WakeToRun to wake the PC from sleep
Register-ScheduledTask -TaskName 'Daily backup' -TaskPath '\MyTasks\' -Action $action -Trigger $trigger -Settings $settings `
  -Description 'Created by Claude: copies Documents to D:\Backup'
```

This runs as the current user, only while they're signed in, with no admin needed. Variants:
- **Run even when signed out:** add `-User $env:USERNAME -Password '<their password>'`. That
  needs the password, so ask; don't store it anywhere else.
- **System-level work** (admin): `-User 'SYSTEM' -RunLevel Highest`. SYSTEM has no desktop,
  mapped drives or user profile, so GUI and `$HOME` paths won't work.
- **`-WindowStyle Hidden` still flashes a console briefly.** On Windows 11 22H2+, use
  `-Execute 'conhost.exe' -Argument '--headless powershell.exe -NoProfile -File "..."'` for no flash.

Manage tasks:

```powershell
Get-ScheduledTask -TaskPath '\MyTasks\' | Get-ScheduledTaskInfo   # LastRunTime, LastTaskResult (0 = success), NextRunTime
Start-ScheduledTask -TaskPath '\MyTasks\' -TaskName 'Daily backup'  # test it now
Disable-ScheduledTask ... ; Unregister-ScheduledTask -TaskName 'Daily backup' -Confirm:$false
```

Keep user tasks in their own folder (`\MyTasks\`) so they're easy to find and never mixed up
with Windows' own tasks. Test with `Start-ScheduledTask` and check `LastTaskResult` before
saying it works. Common failures: a relative path (tasks start in System32 unless
`-WorkingDirectory` is set), and a mapped drive letter (use the `\\server\share` path instead).

**Reminders** combine a one-off task with `scripts/notify.ps1` (and optionally `speak.ps1`):
action `powershell.exe -NoProfile -File "<skill>\scripts\notify.ps1" -Title "Call Mom" -Message "It's 6pm"`.

## Services

```powershell
Get-Service | Where-Object Status -eq Running | Sort-Object DisplayName
Get-Service -DisplayName '*print*'
Get-CimInstance Win32_Service -Filter "Name='Spooler'" | Select-Object Name, StartMode, State, PathName   # what it runs
Restart-Service Spooler                              # (admin)
Set-Service -Name 'SysMain' -StartupType Manual      # (admin) Automatic | AutomaticDelayedStart (PowerShell 7) | Manual | Disabled
```

Before disabling a service, note its current start type so it can be restored, and explain
what stops working. Never disable these: `RpcSs`, `DcomLaunch`, `LSM`, `Winmgmt`,
`EventLog`, `Dhcp`, `Dnscache`, `BFE`, `mpssvc` (firewall), `WinDefend`, `wuauserv`
(disabling Update leaves the PC unpatched), `CryptSvc`, `ProfSvc`.

## Registry

```powershell
Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced'
Get-ItemPropertyValue 'HKCU:\Control Panel\Desktop' -Name WallPaper
Set-ItemProperty 'HKCU:\Software\MyApp' -Name Enabled -Value 1 -Type DWord   # -Type: String, DWord, QWord, Binary, MultiString, ExpandString
New-Item 'HKCU:\Software\MyApp' -Force | Out-Null                            # create a key (Set-ItemProperty needs the key to exist)
Remove-ItemProperty 'HKCU:\Software\MyApp' -Name Enabled
reg export 'HKCU\Software\MyApp' "$HOME\Desktop\MyApp-backup.reg" /y          # back up a key before editing it
reg import "$HOME\Desktop\MyApp-backup.reg"                                  # restore
```

Export the key before changing anything under HKLM or a key you haven't touched before.
Keys that don't exist under `HKCR:` / `HKU:` need a PSDrive (`New-PSDrive HKU Registry HKEY_USERS`).
32-bit apps on 64-bit Windows read `HKLM:\SOFTWARE\WOW6432Node\...`.

## Environment variables and PATH

```powershell
$env:PATH -split ';'                                                         # this session
[Environment]::GetEnvironmentVariable('PATH', 'User') -split ';'             # persisted, per user
[Environment]::SetEnvironmentVariable('MY_API_BASE', 'http://localhost:8000', 'User')

# Append to the user PATH without duplicates (never use setx for PATH: it truncates at 1024 characters)
$dir = 'C:\Tools\bin'
$user = [Environment]::GetEnvironmentVariable('PATH', 'User')
if (($user -split ';') -notcontains $dir) { [Environment]::SetEnvironmentVariable('PATH', ($user.TrimEnd(';') + ";$dir"), 'User') }
$env:PATH += ";$dir"                                                          # also for the current session
```

New values reach newly started programs only. Terminals and editors that are already open
keep the old environment until restarted.

## Clipboard

```powershell
Get-Clipboard ; Set-Clipboard 'text' ; Get-Clipboard -Format FileDropList
'a','b' | Set-Clipboard
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.Clipboard]::GetImage().Save("$env:TEMP\clip.png")   # image on the clipboard → file (5.1 / STA)
```

## Driving GUI apps (when there's no CLI or API)

The bundled scripts cover the mechanics:

- `window.ps1 list | focus | minimize | maximize | move | close`
- `input.ps1 type "text" | keys "ctrl+s" | click -X -Y | scroll`
- `screenshot.ps1` (then read the PNG to see the screen)

A reliable loop: **focus the window → screenshot → read the image → act → screenshot again
to verify.** Prefer keyboard shortcuts to clicking coordinates, because coordinates break
when windows move or DPI changes. For example, `ctrl+l` then typing a URL beats clicking a
browser's address bar.

**UI Automation** can click buttons by name, which survives layout changes. It's worth it
when repeating a GUI task:

```powershell
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
$root = [Windows.Automation.AutomationElement]::RootElement
$win = $root.FindFirst('Children', (New-Object Windows.Automation.PropertyCondition ([Windows.Automation.AutomationElement]::NameProperty), 'Calculator'))
$btn = $win.FindFirst('Descendants', (New-Object Windows.Automation.PropertyCondition ([Windows.Automation.AutomationElement]::NameProperty), 'Seven'))
$btn.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern).Invoke()
# Discover element names with Accessibility Insights (winget install Microsoft.AccessibilityInsights) or inspect.exe
```

Limits to tell the user about: input can't reach apps running as Administrator from a
non-elevated script, the lock screen, UAC prompts (secure desktop), or most games that use
raw input or anti-cheat.

## Hotkeys and text expansion

Windows has no built-in custom global hotkeys. AutoHotkey v2 is the standard tool
(`winget install AutoHotkey.AutoHotkey`):

```autohotkey
; save as $HOME\Scripts\hotkeys.ahk and double-click (or put a shortcut in shell:startup)
#Requires AutoHotkey v2.0
^!t::Run "wt.exe"                         ; Ctrl+Alt+T opens Windows Terminal
^!v::Send "{Volume_Down 5}"               ; Ctrl+Alt+V: volume down
::@@::me@example.com                      ; typing @@ expands to the email address
```

PowerToys (`winget install Microsoft.PowerToys`) covers key remapping, window layouts
(FancyZones), a color picker and bulk rename without scripting.

## React to changes: file watchers

```powershell
$w = New-Object IO.FileSystemWatcher "$HOME\Downloads", '*.pdf' -Property @{ IncludeSubdirectories = $false; EnableRaisingEvents = $true }
Register-ObjectEvent $w Created -SourceIdentifier NewPdf -Action {
  Move-Item $Event.SourceEventArgs.FullPath "$HOME\Documents\PDFs\" -Force
}
# Runs while this PowerShell stays open. To make it permanent, put it in a script started by an at-logon scheduled task and end the script with: while ($true) { Wait-Event -Timeout 3600 }
```

## Notifications and speech

- `scripts/notify.ps1 -Title "Done" -Message "Render finished"`: a toast notification.
- `scripts/speak.ps1 "Render finished"`: reads text aloud. Also works with `-OutFile x.wav`.
- Long jobs: chain one onto the end of the command, e.g. `...; & notify.ps1 -Title 'Backup finished'`.
