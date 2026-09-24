<#
.SYNOPSIS
  One-shot system snapshot as JSON: OS, CPU, GPU (real VRAM), RAM, disks, battery, network, uptime, top processes.
.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File sysinfo.ps1
  powershell -NoProfile -ExecutionPolicy Bypass -File sysinfo.ps1 -Section gpu,disks
#>
param(
    [string[]]$Section = @('os', 'cpu', 'gpu', 'memory', 'disks', 'battery', 'network', 'processes'),
    [int]$TopProcesses = 8
)
$ErrorActionPreference = 'SilentlyContinue'
$Section = $Section | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim().ToLower() }
$out = [ordered]@{}
$os = Get-CimInstance Win32_OperatingSystem
$cs = Get-CimInstance Win32_ComputerSystem

if ($Section -contains 'os') {
    $cv = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'
    $uptime = (Get-Date) - $os.LastBootUpTime
    $out.os = [ordered]@{
        name         = $os.Caption
        version      = "$($cv.DisplayVersion) (build $($os.BuildNumber).$($cv.UBR))"
        computer     = $env:COMPUTERNAME
        user         = "$env:USERDOMAIN\$env:USERNAME"
        manufacturer = $cs.Manufacturer
        model        = $cs.Model
        uptime       = '{0}d {1}h {2}m' -f $uptime.Days, $uptime.Hours, $uptime.Minutes
        last_boot    = $os.LastBootUpTime.ToString('yyyy-MM-dd HH:mm')
    }
}

if ($Section -contains 'cpu') {
    $cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
    $out.cpu = [ordered]@{
        name         = $cpu.Name.Trim()
        cores        = $cpu.NumberOfCores
        threads      = $cpu.NumberOfLogicalProcessors
        max_mhz      = $cpu.MaxClockSpeed
        load_percent = $cpu.LoadPercentage
    }
}

if ($Section -contains 'gpu') {
    # Win32_VideoController.AdapterRAM is 32-bit and caps at 4 GB, so read the real
    # size from the display-adapter class key, and prefer nvidia-smi when present.
    $classKey = 'HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}'
    $adapters = Get-ChildItem $classKey | ForEach-Object { Get-ItemProperty $_.PSPath } |
        Where-Object { $_.DriverDesc }
    $nvidia = @{}
    $smi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
    if ($smi) {
        & $smi.Source --query-gpu=name,memory.total,memory.used,utilization.gpu,temperature.gpu --format=csv,noheader,nounits |
            ForEach-Object {
                $p = $_ -split ',\s*'
                $nvidia[$p[0]] = @{ total = [math]::Round([double]$p[1] / 1024, 1); used = [math]::Round([double]$p[2] / 1024, 1); util = [int]$p[3]; temp = [int]$p[4] }
            }
    }
    $out.gpu = @(foreach ($g in Get-CimInstance Win32_VideoController) {
        $reg = $adapters | Where-Object { $_.DriverDesc -eq $g.Name } | Select-Object -First 1
        $bytes = $reg.'HardwareInformation.qwMemorySize'
        if ($bytes -is [byte[]]) { $bytes = [BitConverter]::ToUInt64($bytes, 0) }
        $vram = if ($bytes) { [math]::Round([double]$bytes / 1GB, 1) } elseif ($g.AdapterRAM) { [math]::Round($g.AdapterRAM / 1GB, 1) } else { $null }
        $row = [ordered]@{
            name       = $g.Name
            vram_gb    = $vram
            driver     = $g.DriverVersion
            resolution = if ($g.CurrentHorizontalResolution) { "$($g.CurrentHorizontalResolution)x$($g.CurrentVerticalResolution) @ $($g.CurrentRefreshRate)Hz" } else { $null }
        }
        $n = $nvidia.Keys | Where-Object { $g.Name -like "*$_*" -or $_ -like "*$($g.Name)*" } | Select-Object -First 1
        if ($n) {
            $row.vram_gb = $nvidia[$n].total
            $row.vram_used_gb = $nvidia[$n].used
            $row.utilization_percent = $nvidia[$n].util
            $row.temperature_c = $nvidia[$n].temp
        }
        $row
    })
}

if ($Section -contains 'memory') {
    $total = $cs.TotalPhysicalMemory
    $free = $os.FreePhysicalMemory * 1KB
    $sticks = Get-CimInstance Win32_PhysicalMemory
    $out.memory = [ordered]@{
        total_gb     = [math]::Round($total / 1GB, 1)
        used_gb      = [math]::Round(($total - $free) / 1GB, 1)
        free_gb      = [math]::Round($free / 1GB, 1)
        used_percent = [math]::Round(100 * ($total - $free) / $total)
        sticks       = @($sticks | ForEach-Object { '{0} GB @ {1} MHz' -f ($_.Capacity / 1GB), $_.ConfiguredClockSpeed })
    }
}

if ($Section -contains 'disks') {
    $out.volumes = @(Get-Volume | Where-Object { $_.DriveLetter -and $_.Size -gt 0 } | Sort-Object DriveLetter | ForEach-Object {
        [ordered]@{
            drive        = "$($_.DriveLetter):"
            label        = $_.FileSystemLabel
            size_gb      = [math]::Round($_.Size / 1GB, 1)
            free_gb      = [math]::Round($_.SizeRemaining / 1GB, 1)
            free_percent = [math]::Round(100 * $_.SizeRemaining / $_.Size)
            filesystem   = $_.FileSystem
        }
    })
    $out.physical_disks = @(Get-PhysicalDisk | ForEach-Object {
        [ordered]@{ name = $_.FriendlyName; type = "$($_.MediaType)"; bus = "$($_.BusType)"; size_gb = [math]::Round($_.Size / 1GB); health = "$($_.HealthStatus)" }
    })
}

if ($Section -contains 'battery') {
    $b = Get-CimInstance Win32_Battery | Select-Object -First 1
    $out.battery = if ($b) {
        $status = @{ 1 = 'discharging'; 2 = 'plugged in'; 3 = 'full'; 6 = 'charging'; 7 = 'charging (high)'; 8 = 'charging (low)'; 9 = 'charging (critical)' }
        [ordered]@{ percent = $b.EstimatedChargeRemaining; status = $status[[int]$b.BatteryStatus]; minutes_left = if ($b.EstimatedRunTime -lt 71582788) { $b.EstimatedRunTime } else { $null } }
    } else { 'none (desktop)' }
}

if ($Section -contains 'network') {
    $wifi = (netsh wlan show interfaces) -join "`n"
    $ssid = if ($wifi -match '(?m)^\s*SSID\s*:\s*(.+)$') { $Matches[1].Trim() } else { $null }
    $signal = if ($wifi -match '(?m)^\s*Signal\s*:\s*(\d+)%') { [int]$Matches[1] } else { $null }
    $out.network = @(Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway } | ForEach-Object {
        $adapter = Get-NetAdapter -InterfaceIndex $_.InterfaceIndex
        $row = [ordered]@{
            adapter = $_.InterfaceAlias
            type    = $adapter.MediaType
            speed   = $adapter.LinkSpeed
            ipv4    = ($_.IPv4Address.IPAddress -join ', ')
            gateway = $_.IPv4DefaultGateway.NextHop
            dns     = ($_.DNSServer | Where-Object AddressFamily -eq 2 | ForEach-Object { $_.ServerAddresses }) -join ', '
        }
        if ($ssid -and $adapter.PhysicalMediaType -match '802\.11|Native 802') { $row.wifi_ssid = $ssid; $row.wifi_signal_percent = $signal }
        $row
    })
}

if ($Section -contains 'processes') {
    $cores = [Environment]::ProcessorCount
    $out.top_processes_by_memory = @(Get-Process | Group-Object ProcessName | ForEach-Object {
        [pscustomobject]@{ name = $_.Name; count = $_.Count; ram_mb = [math]::Round(($_.Group | Measure-Object WorkingSet64 -Sum).Sum / 1MB) }
    } | Sort-Object ram_mb -Descending | Select-Object -First $TopProcesses)
    $out.top_processes_by_cpu = @(Get-CimInstance Win32_PerfFormattedData_PerfProc_Process |
        Where-Object { $_.Name -notin '_Total', 'Idle' } | Sort-Object PercentProcessorTime -Descending |
        Select-Object -First $TopProcesses | ForEach-Object {
            [pscustomobject]@{ name = $_.Name; pid = $_.IDProcess; cpu_percent = [math]::Round($_.PercentProcessorTime / $cores, 1) }
        })
}

$out | ConvertTo-Json -Depth 5
