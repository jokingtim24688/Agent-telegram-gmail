<#
.SYNOPSIS
  Brightness, dark/light mode and wallpaper.
.EXAMPLE
  display.ps1 get                       -> {"brightness":70,"apps":"dark","system":"dark","wallpaper":"C:\\..."}
  display.ps1 brightness 40             (built-in laptop screens only)
  display.ps1 dark   /  display.ps1 light
  display.ps1 dark -AppsOnly            (keep the taskbar/Start as they are)
  display.ps1 wallpaper "C:\Users\me\Pictures\beach.jpg"
.NOTES
  External monitors don't expose brightness through Windows. They need DDC/CI:
  winget install Monitorian (a GUI), or NirSoft ControlMyMonitor (CLI: /SetValue Primary 10 50).
#>
param(
    [Parameter(Position = 0)]
    [ValidateSet('get', 'brightness', 'dark', 'light', 'wallpaper')]
    [string]$Action = 'get',
    [Parameter(Position = 1)]
    [string]$Value,
    [switch]$AppsOnly
)
$ErrorActionPreference = 'Stop'
$personalize = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize'

if (-not ('WinCtl.Display' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
namespace WinCtl {
    public static class Display {
        [DllImport("user32.dll", CharSet = CharSet.Unicode)]
        public static extern bool SystemParametersInfo(uint action, uint param, string value, uint flags);
        [DllImport("user32.dll", CharSet = CharSet.Unicode)]
        static extern IntPtr SendMessageTimeout(IntPtr h, uint msg, IntPtr w, string l, uint flags, uint timeout, out IntPtr result);
        // Tell open windows the theme changed, so Explorer and apps repaint without a sign-out.
        public static void BroadcastThemeChange() {
            IntPtr r;
            SendMessageTimeout((IntPtr)0xffff, 0x001A, IntPtr.Zero, "ImmersiveColorSet", 2, 5000, out r);
        }
    }
}
'@
}

function Get-Brightness {
    try { (Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness -ErrorAction Stop | Select-Object -First 1).CurrentBrightness }
    catch { $null }
}
function Get-State {
    $p = Get-ItemProperty $personalize -ErrorAction SilentlyContinue
    [ordered]@{
        brightness = Get-Brightness
        apps       = if ($p.AppsUseLightTheme -eq 0) { 'dark' } else { 'light' }
        system     = if ($p.SystemUsesLightTheme -eq 0) { 'dark' } else { 'light' }
        wallpaper  = (Get-ItemProperty 'HKCU:\Control Panel\Desktop').WallPaper
    } | ConvertTo-Json -Compress
}

switch ($Action) {
    'get' { Get-State }
    'brightness' {
        $level = [int]$Value
        if ($level -lt 0 -or $level -gt 100) { throw 'Brightness is 0-100.' }
        $m = Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods -ErrorAction SilentlyContinue
        if (-not $m) { throw 'This screen does not support software brightness (usually a desktop monitor). See the notes in this script for DDC/CI tools.' }
        $m | ForEach-Object { Invoke-CimMethod -InputObject $_ -MethodName WmiSetBrightness -Arguments @{ Timeout = 1; Brightness = [byte]$level } | Out-Null }
        Get-State
    }
    { $_ -in 'dark', 'light' } {
        $v = if ($Action -eq 'dark') { 0 } else { 1 }
        Set-ItemProperty $personalize -Name AppsUseLightTheme -Value $v -Type DWord
        if (-not $AppsOnly) { Set-ItemProperty $personalize -Name SystemUsesLightTheme -Value $v -Type DWord }
        [WinCtl.Display]::BroadcastThemeChange()
        Get-State
    }
    'wallpaper' {
        $file = (Resolve-Path $Value).Path
        # SPI_SETDESKWALLPAPER, save to profile + broadcast
        if (-not [WinCtl.Display]::SystemParametersInfo(0x0014, 0, $file, 0x03)) { throw "Windows rejected $file (use .jpg, .png or .bmp)." }
        Get-State
    }
}
