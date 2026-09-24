# System and hardware

## Quick snapshot

`scripts/sysinfo.ps1` returns OS, CPU, GPU with real VRAM, RAM, disks, battery, network and
top processes as JSON. Use `-Section gpu,memory` to ask for just what's needed. Individual
pieces follow.

```powershell
Get-ComputerInfo -Property OsName, OsVersion, OsBuildNumber, CsManufacturer, CsModel, BiosSMBIOSBIOSVersion   # slow (~5 s)
(Get-CimInstance Win32_BIOS).SerialNumber          # serial number / service tag
(Get-CimInstance Win32_BaseBoard) | Select-Object Manufacturer, Product    # motherboard
Get-CimInstance Win32_PhysicalMemory | Select-Object Capacity, ConfiguredClockSpeed, Manufacturer, PartNumber, DeviceLocator
Get-CimInstance Win32_PhysicalMemoryArray | Select-Object MemoryDevices, MaxCapacity   # RAM slots and max (MaxCapacity is in KB)
winver                                             # the friendly version dialog
```

**GPU:** `Win32_VideoController.AdapterRAM` caps at 4 GB because the field is 32-bit, so
use `sysinfo.ps1 -Section gpu` or `nvidia-smi` for real VRAM. Live NVIDIA stats:
`nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv`.

## Performance: "why is my PC slow?"

Work through this in order and report what you find in plain language:

```powershell
# 1. What's using CPU right now (averaged over a moment, per process, in % of total CPU)
$cores = [Environment]::ProcessorCount
Get-CimInstance Win32_PerfFormattedData_PerfProc_Process | Where-Object Name -notin '_Total','Idle' |
  Sort-Object PercentProcessorTime -Descending | Select-Object -First 10 Name, IDProcess,
  @{n='CPU%';e={[math]::Round($_.PercentProcessorTime/$cores,1)}}, @{n='RAM_MB';e={[math]::Round($_.WorkingSetPrivate/1MB)}}
# 2. Memory pressure
Get-Counter '\Memory\Available MBytes','\Memory\% Committed Bytes In Use','\Paging File(_Total)\% Usage'
# 3. Disk busy? (sustained 100% "% Disk Time" on an HDD is the classic cause)
Get-Counter '\PhysicalDisk(_Total)\% Disk Time','\PhysicalDisk(_Total)\Avg. Disk Queue Length' -SampleInterval 2 -MaxSamples 3
# 4. Free space on C: (under ~10% makes Windows sluggish and updates fail)
Get-Volume C | Select-Object SizeRemaining, Size
# 5. Startup load: count and list startup apps (apps-and-processes.md)
# 6. Uptime: days without a restart means pending updates and memory leaks pile up
(Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
# 7. Thermals and throttling (laptops): current vs max clock
Get-CimInstance Win32_Processor | Select-Object CurrentClockSpeed, MaxClockSpeed, LoadPercentage
```

`Get-Counter` counter names are localized. On a non-English Windows, find the names with
`Get-Counter -ListSet *` or use the CIM classes above.

## Disks and storage health

```powershell
Get-Volume | Where-Object DriveLetter | Select-Object DriveLetter, FileSystemLabel, FileSystem,
  @{n='SizeGB';e={[math]::Round($_.Size/1GB)}}, @{n='FreeGB';e={[math]::Round($_.SizeRemaining/1GB)}}
Get-PhysicalDisk | Select-Object FriendlyName, MediaType, BusType, HealthStatus, @{n='SizeGB';e={[math]::Round($_.Size/1GB)}}
Get-PhysicalDisk | Get-StorageReliabilityCounter | Select-Object DeviceId, Temperature, Wear, ReadErrorsTotal, PowerOnHours   # admin
Optimize-Volume -DriveLetter C -Analyze -Verbose      # SSD = TRIM, HDD = defrag analysis (admin)
chkdsk C: /scan                                        # online check (admin); /f needs a reboot for C:
Get-Disk ; Get-Partition                               # layout
```

Formatting, partitioning (`Clear-Disk`, `Initialize-Disk`, `New-Partition`, `Format-Volume`)
and `diskpart` destroy data. Name the exact disk (number, size, model) back to the user and
get a clear yes. Never guess which disk is the USB stick.

Cleanup: `scripts/cleanup.ps1` (dry run by default). Other built-in routes:
`Start-Process ms-settings:storagesense`, and `cleanmgr` (admin: `cleanmgr /sageset:1`, then
`/sagerun:1`), which can also remove `Windows.old` after an upgrade (often 10–30 GB).
Compacting the component store: `DISM /Online /Cleanup-Image /StartComponentCleanup` (admin).

## Battery (laptops)

```powershell
powercfg /batteryreport /output "$env:TEMP\battery.html"; Invoke-Item "$env:TEMP\battery.html"   # design vs full-charge capacity = wear
Get-CimInstance Win32_Battery | Select-Object EstimatedChargeRemaining, BatteryStatus, EstimatedRunTime
powercfg /energy /output "$env:TEMP\energy.html" /duration 30     # (admin) finds battery-drain culprits
```

## Power, sleep, shutdown

```powershell
powercfg /list ; powercfg /getactivescheme
powercfg /setactive SCHEME_MIN        # High performance  (SCHEME_BALANCED, SCHEME_MAX = power saver)
powercfg /change standby-timeout-ac 30 ; powercfg /change monitor-timeout-ac 10   # minutes; 0 = never; -dc for battery
powercfg /requests                     # (admin) what's stopping the PC from sleeping
powercfg /lastwake ; powercfg /waketimers
powercfg /hibernate on|off

shutdown /s /t 0          # shut down now          shutdown /s /t 3600 = in an hour ; shutdown /a = cancel
shutdown /r /t 0          # restart                shutdown /r /o /t 0 = restart into Advanced Startup (recovery/BIOS menu)
shutdown /l               # sign out
rundll32.exe user32.dll,LockWorkStation              # lock
Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Application]::SetSuspendState('Suspend', $false, $false)   # sleep (hibernates instead if hibernation is on)
```

Shutting down, restarting or signing out ends this session too. Confirm first, and mention
any unsaved work in open apps (`Get-Process | Where-Object MainWindowTitle`). Prefer a
delayed `shutdown /s /t 60` so the user can cancel with `shutdown /a`.

## Windows Update

```powershell
Start-Process ms-settings:windowsupdate              # the reliable way for a person
Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 10   # recently installed
UsoClient StartInteractiveScan                       # trigger a check (no output; watch Settings)
(New-Object -ComObject Microsoft.Update.SystemInfo).RebootRequired         # pending reboot?
# Full scripting (admin): Install-Module PSWindowsUpdate -Scope CurrentUser
#   Get-WindowsUpdate ; Install-WindowsUpdate -AcceptAll -IgnoreReboot
```

## Drivers and devices

```powershell
Get-PnpDevice -PresentOnly | Where-Object Status -ne 'OK' | Select-Object Class, FriendlyName, Status, InstanceId   # problem devices
Get-CimInstance Win32_PnPSignedDriver | Where-Object DeviceName | Select-Object DeviceName, DriverVersion, DriverDate, Manufacturer |
  Sort-Object DeviceName
pnputil /enum-drivers                           # third-party driver packages
pnputil /add-driver C:\drivers\*.inf /install   # (admin) install from .inf
Disable-PnpDevice -InstanceId '<id>' -Confirm:$false ; Enable-PnpDevice -InstanceId '<id>' -Confirm:$false   # (admin) turn a device off and on
pnputil /scan-devices                           # rescan hardware
Get-PnpDevice -Class Camera, Image, AudioEndpoint, Bluetooth, USB -PresentOnly
```

GPU drivers: NVIDIA → the NVIDIA App (or nvidia.com/drivers); AMD → AMD Software: Adrenalin. Don't hand-install GPU `.inf` files.

## Logs: what just crashed or went wrong

```powershell
# Errors in the last day, System and Application logs
Get-WinEvent -FilterHashtable @{LogName='System','Application'; Level=1,2; StartTime=(Get-Date).AddDays(-1)} -MaxEvents 50 |
  Select-Object TimeCreated, ProviderName, Id, Message | Format-List
# Unexpected shutdowns / bluescreens
Get-WinEvent -FilterHashtable @{LogName='System'; Id=41,1001,6008} -MaxEvents 10 | Select-Object TimeCreated, Id, Message
# App crashes (faulting module names the culprit)
Get-WinEvent -FilterHashtable @{LogName='Application'; Id=1000} -MaxEvents 10 | Select-Object TimeCreated, Message
# Reliability history, the friendliest timeline:
Start-Process perfmon.exe -ArgumentList '/rel'
Get-ChildItem C:\Windows\Minidump -ErrorAction SilentlyContinue      # BSOD dumps (analyze with WinDbg / BlueScreenView)
```

## Repairs

```powershell
sfc /scannow                                         # (admin) repair system files
DISM /Online /Cleanup-Image /RestoreHealth           # (admin) repair the image sfc repairs from; run before sfc if sfc fails
Checkpoint-Computer -Description 'Before changes' -RestorePointType MODIFY_SETTINGS   # (admin; one per 24 h by default)
Get-ComputerRestorePoint ; rstrui.exe                # list / restore (GUI)
Start-Process ms-settings:recovery                   # reset this PC, advanced startup
```

## Time, date, region

```powershell
Get-TimeZone ; Set-TimeZone -Id 'Eastern Standard Time'     # Get-TimeZone -ListAvailable for IDs (admin)
w32tm /resync                                                # (admin) resync the clock
Get-Culture ; Get-WinSystemLocale ; Set-Culture en-GB        # formats for the current user
```

## Hardware peripherals

- **Webcam and mic in use / privacy:** `Start-Process ms-settings:privacy-webcam` / `privacy-microphone`.
- **Bluetooth:** no full CLI. Show devices with `Get-PnpDevice -Class Bluetooth`; open
  `ms-settings:bluetooth` to pair. Turning the radio on and off needs WinRT
  (`Windows.Devices.Radios`), which is not worth scripting. Use the Settings page.
- **Printers:** see `office-and-media.md`.
- **USB drives:** `Get-Disk | Where-Object BusType -eq USB`. Safe eject:
  `(New-Object -ComObject Shell.Application).Namespace(17).ParseName('E:\').InvokeVerb('Eject')`.
