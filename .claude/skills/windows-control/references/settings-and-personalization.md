# Settings and personalization

## Sound

`scripts/audio.ps1` sets exact volume, mutes, and sends media keys (play-pause, next,
previous). Media keys control whatever app currently owns media playback (Spotify, YouTube in
a browser, and so on).

```powershell
Start-Process ms-settings:sound ; Start-Process mmsys.cpl          # modern / classic sound panels
Start-Process ms-settings:apps-volume                              # per-app volume mixer
```

Switching the **default output device** (speakers ↔ headset) has no built-in command. Use the
`AudioDeviceCmdlets` module (`Install-Module AudioDeviceCmdlets -Scope CurrentUser`, then
`Get-AudioDevice -List` and `Set-AudioDevice -Index 2`), or NirSoft SoundVolumeView.

## Display

`scripts/display.ps1` handles laptop-screen brightness, dark/light mode and wallpaper.

```powershell
Get-CimInstance -Namespace root\wmi -ClassName WmiMonitorBasicDisplayParams      # connected monitors
Start-Process ms-settings:display                                                 # resolution, scale, arrangement, HDR
Start-Process ms-settings:nightlight
DisplaySwitch.exe /extend    # also /clone, /internal, /external: like Win+P
```

Changing **resolution, refresh rate or scaling** from a script needs `ChangeDisplaySettingsEx`
interop and can leave the screen blank if the monitor rejects the mode. Open
`ms-settings:display` (which has a 15-second auto-revert) unless the user insists.
External-monitor brightness needs DDC/CI tools (Monitorian, ControlMyMonitor).

## Theme, colors, taskbar, Explorer

Registry values under HKCU affect only this user and are reversible. Read the old value
first so you can put it back.

```powershell
$adv = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced'
Set-ItemProperty $adv HideFileExt 0          # show file extensions   (1 = hide)
Set-ItemProperty $adv Hidden 1               # show hidden files      (2 = hide)
Set-ItemProperty $adv LaunchTo 1             # Explorer opens to This PC (2 = Home, 3 = Downloads on 11)
Set-ItemProperty $adv TaskbarAl 0            # Windows 11: taskbar icons left (1 = center)
Set-ItemProperty $adv TaskbarDa 0            # Windows 11: hide the Widgets button (may be blocked by policy on newer builds)
Set-ItemProperty $adv ShowTaskViewButton 0
Set-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Search' SearchboxTaskbarMode 1   # 0 hidden, 1 icon, 2 box
# Windows 11 classic (full) right-click menu:
New-Item 'HKCU:\Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50cf03f5f7a3}\InprocServer32' -Force -Value '' | Out-Null
#   undo: Remove-Item 'HKCU:\Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50cf03f5f7a3}' -Recurse
Stop-Process -Name explorer -Force           # apply: Explorer restarts itself in a second or two
```

Accent color and transparency: `HKCU:\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize`
(`EnableTransparency` 0/1, `ColorPrevalence` 0/1). The accent color itself is simplest to set
through `ms-settings:colors`.

Tell the user before restarting Explorer: the taskbar and open Explorer windows disappear for
a moment, but nothing else closes.

## Mouse, keyboard, typing

```powershell
Start-Process ms-settings:mousetouchpad ; Start-Process ms-settings:typing
Set-ItemProperty 'HKCU:\Control Panel\Mouse' MouseSensitivity 10          # 1-20; applies after sign-out
Get-WinUserLanguageList ; $l = Get-WinUserLanguageList; $l.Add('fr-FR'); Set-WinUserLanguageList $l -Force   # add a keyboard layout
# Caps Lock → Ctrl, key remaps: Microsoft PowerToys Keyboard Manager (winget install Microsoft.PowerToys)
```

## Notifications and Focus

```powershell
Start-Process ms-settings:notifications
Start-Process ms-settings:quiethours          # Focus / Do not disturb (no reliable CLI toggle)
```

## Accessibility

```powershell
Start-Process ms-settings:easeofaccess-display    # text size
Start-Process magnify.exe ; Start-Process narrator.exe ; Start-Process osk.exe   # magnifier, narrator, on-screen keyboard
```

## Settings deep links (`Start-Process ms-settings:<page>`)

| Page | Link |
|---|---|
| Display / Night light | `display`, `nightlight` |
| Sound / Volume mixer | `sound`, `apps-volume` |
| Bluetooth & devices / Printers | `bluetooth`, `printers` |
| Wi-Fi / Network status / VPN / Proxy | `network-wifi`, `network-status`, `network-vpn`, `network-proxy` |
| Personalization / Background / Colors / Themes / Lock screen | `personalization`, `personalization-background`, `colors`, `themes`, `lockscreen` |
| Taskbar / Start | `taskbar`, `personalization-start` |
| Apps / Default apps / Startup apps / Optional features | `appsfeatures`, `defaultapps`, `startupapps`, `optionalfeatures` |
| Accounts / Sign-in options / Other users | `yourinfo`, `signinoptions`, `otherusers` |
| Time & language / Region / Speech | `dateandtime`, `regionformatting`, `speech` |
| Gaming / Game Mode / Captures | `gaming-gamebar`, `gaming-gamemode`, `gaming-gamedvr` |
| Privacy: camera / microphone / location | `privacy-webcam`, `privacy-microphone`, `privacy-location` |
| Windows Update / Recovery / Activation / About | `windowsupdate`, `recovery`, `activation`, `about` |
| Storage / Storage Sense / Power & battery | `storagesense`, `storagepolicies`, `powersleep`, `batterysaver` |
| Windows Security | `windowsdefender` |
| Troubleshoot | `troubleshoot` |

Classic Control Panel applets are still useful: `appwiz.cpl` (programs), `ncpa.cpl` (network
adapters), `sysdm.cpl` (system properties, environment variables), `powercfg.cpl`,
`mmsys.cpl` (sound), `main.cpl` (mouse), `firewall.cpl`, `devmgmt.msc`, `diskmgmt.msc`,
`services.msc`, `taskschd.msc`, `eventvwr.msc`, `compmgmt.msc`. Open any of them with `Start-Process <name>`.

## Changing settings through Group Policy / HKLM

Machine-wide policies (`HKLM:\SOFTWARE\Policies\...`) need admin and affect all users. They
can also conflict with workplace management (Intune or a domain). Check first with
`dsregcmd /status` (AzureAdJoined / DomainJoined). On a managed work PC, tell the user their
IT may override or block the change.
