<#
.SYNOPSIS
  Find what's using disk space: the largest files, or folder sizes one level down.
.EXAMPLE
  find-large.ps1                               (20 largest files under your user folder)
  find-large.ps1 -Path D:\ -Top 50 -MinMB 500
  find-large.ps1 -Path C:\Users\me -Folders    (size of each subfolder, largest first)
  find-large.ps1 -Path $HOME\Downloads -OlderThanDays 180   (big files you haven't touched in 6 months)
#>
param(
    [string]$Path = $HOME,
    [int]$Top = 20,
    [int]$MinMB = 50,
    [int]$OlderThanDays = 0,
    [switch]$Folders
)
$ErrorActionPreference = 'SilentlyContinue'
$root = (Resolve-Path $Path).Path

if ($Folders) {
    $rows = foreach ($d in Get-ChildItem $root -Directory -Force) {
        # Skip junctions (e.g. "Application Data") so sizes aren't double-counted.
        if ($d.Attributes -band [IO.FileAttributes]::ReparsePoint) { continue }
        $sum = (Get-ChildItem $d.FullName -Recurse -File -Force | Measure-Object Length -Sum).Sum
        [pscustomobject]@{ folder = $d.FullName; size_gb = [math]::Round($sum / 1GB, 2) }
    }
    $loose = (Get-ChildItem $root -File -Force | Measure-Object Length -Sum).Sum
    $rows += [pscustomobject]@{ folder = "$root (files directly inside)"; size_gb = [math]::Round($loose / 1GB, 2) }
    $rows | Sort-Object size_gb -Descending | Select-Object -First $Top | ConvertTo-Json
    return
}

$cutoff = if ($OlderThanDays -gt 0) { (Get-Date).AddDays(-$OlderThanDays) } else { [datetime]::MaxValue }
Get-ChildItem $root -Recurse -File -Force |
    Where-Object { $_.Length -ge $MinMB * 1MB -and $_.LastWriteTime -lt $cutoff } |
    Sort-Object Length -Descending | Select-Object -First $Top | ForEach-Object {
        [pscustomobject]@{ file = $_.FullName; size_mb = [math]::Round($_.Length / 1MB); modified = $_.LastWriteTime.ToString('yyyy-MM-dd') }
    } | ConvertTo-Json
