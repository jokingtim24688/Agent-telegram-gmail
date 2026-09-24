<#
.SYNOPSIS
  Measure, and optionally clear, space that's safe to reclaim. Dry run unless -Apply is given.
.DESCRIPTION
  Targets (all regenerate on their own or are already disposable):
    user-temp      %TEMP%, files older than -OlderThanDays (default 2, so running installers keep theirs)
    windows-temp   C:\Windows\Temp, same age rule                          (admin)
    recycle-bin    everything in the Recycle Bin on all drives
    crash-dumps    %LOCALAPPDATA%\CrashDumps and Windows Error Reporting archives
    thumbnails     Explorer thumbnail cache (rebuilt as you browse)
    update-cache   C:\Windows\SoftwareDistribution\Download                (admin, stops wuauserv briefly)
    delivery-opt   Delivery Optimization cache                             (admin)
  Files in use are skipped silently.
.EXAMPLE
  cleanup.ps1                                  (report only)
  cleanup.ps1 -Apply -Include user-temp,crash-dumps,thumbnails
  cleanup.ps1 -Apply                           (all targets this session has rights for)
#>
param(
    [ValidateSet('user-temp', 'windows-temp', 'recycle-bin', 'crash-dumps', 'thumbnails', 'update-cache', 'delivery-opt')]
    [string[]]$Include = @('user-temp', 'windows-temp', 'recycle-bin', 'crash-dumps', 'thumbnails', 'update-cache', 'delivery-opt'),
    [int]$OlderThanDays = 2,
    [switch]$Apply
)
$ErrorActionPreference = 'SilentlyContinue'
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
$cutoff = (Get-Date).AddDays(-$OlderThanDays)

function Files($paths, [switch]$Aged) {
    foreach ($p in $paths) {
        if (Test-Path $p) {
            Get-ChildItem $p -Recurse -Force -File | Where-Object { -not $Aged -or $_.LastWriteTime -lt $cutoff }
        }
    }
}
function Remove-Files($files) {
    $freed = 0
    foreach ($f in $files) {
        $len = $f.Length
        Remove-Item -LiteralPath $f.FullName -Force
        if (-not (Test-Path -LiteralPath $f.FullName)) { $freed += $len }
    }
    $freed
}
function Remove-EmptyDirs($root) {
    if (Test-Path $root) {
        Get-ChildItem $root -Recurse -Force -Directory | Sort-Object { $_.FullName.Length } -Descending |
            Where-Object { -not (Get-ChildItem $_.FullName -Force) } | Remove-Item -Force
    }
}

$targets = [ordered]@{
    'user-temp'    = @{ admin = $false; paths = @($env:TEMP); aged = $true }
    'windows-temp' = @{ admin = $true; paths = @("$env:WINDIR\Temp"); aged = $true }
    'crash-dumps'  = @{ admin = $false; paths = @("$env:LOCALAPPDATA\CrashDumps", "$env:LOCALAPPDATA\Microsoft\Windows\WER\ReportArchive", "$env:ProgramData\Microsoft\Windows\WER\ReportArchive"); aged = $false }
    'thumbnails'   = @{ admin = $false; paths = @(); aged = $false }
    'update-cache' = @{ admin = $true; paths = @("$env:WINDIR\SoftwareDistribution\Download"); aged = $false }
}

$report = foreach ($name in $Include) {
    $row = [ordered]@{ target = $name; size_mb = 0; freed_mb = 0; note = '' }
    switch ($name) {
        'recycle-bin' {
            $bin = (New-Object -ComObject Shell.Application).Namespace(10)
            $size = ($bin.Items() | ForEach-Object { $_.Size } | Measure-Object -Sum).Sum
            $row.size_mb = [math]::Round($size / 1MB)
            if ($Apply -and $size) { Clear-RecycleBin -Force; $row.freed_mb = $row.size_mb; $row.note = 'emptied (not recoverable)' }
        }
        'delivery-opt' {
            $cache = Get-DeliveryOptimizationStatus | Measure-Object FileSizeInCache -Sum
            $row.size_mb = [math]::Round($cache.Sum / 1MB)
            if ($Apply) {
                if ($isAdmin) { Delete-DeliveryOptimizationCache -Force; $row.freed_mb = $row.size_mb }
                else { $row.note = 'needs admin' }
            }
        }
        'thumbnails' {
            $files = @(Get-ChildItem "$env:LOCALAPPDATA\Microsoft\Windows\Explorer" -Filter 'thumbcache_*.db' -Force)
            $row.size_mb = [math]::Round(($files | Measure-Object Length -Sum).Sum / 1MB)
            if ($Apply) { $row.freed_mb = [math]::Round((Remove-Files $files) / 1MB); $row.note = 'files locked by Explorer are skipped' }
        }
        default {
            $t = $targets[$name]
            $files = @(Files $t.paths -Aged:$t.aged)
            $row.size_mb = [math]::Round(($files | Measure-Object Length -Sum).Sum / 1MB)
            if ($Apply) {
                if ($t.admin -and -not $isAdmin) { $row.note = 'needs admin' }
                else {
                    if ($name -eq 'update-cache') { Stop-Service wuauserv -Force }
                    $row.freed_mb = [math]::Round((Remove-Files $files) / 1MB)
                    $t.paths | ForEach-Object { Remove-EmptyDirs $_ }
                    if ($name -eq 'update-cache') { Start-Service wuauserv }
                }
            }
        }
    }
    [pscustomobject]$row
}

$report | ConvertTo-Json
$total = ($report | Measure-Object size_mb -Sum).Sum
$freed = ($report | Measure-Object freed_mb -Sum).Sum
if ($Apply) { "Freed about $freed MB." } else { "About $total MB could be reclaimed. Nothing was deleted; re-run with -Apply." }
if (-not $isAdmin) { 'Not elevated: windows-temp, update-cache and delivery-opt need an Administrator terminal.' }
'For bigger wins: Settings > System > Storage > Cleanup recommendations, or cleanmgr /sageset:1 then cleanmgr /sagerun:1 (admin, includes old Windows installs).'
