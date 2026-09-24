<#
.SYNOPSIS
  Save a screenshot to PNG and print its path.
.EXAMPLE
  screenshot.ps1                         (all monitors -> Pictures\Screenshots\shot-<time>.png)
  screenshot.ps1 -Monitor 1              (primary monitor = 1, as listed by -ListMonitors)
  screenshot.ps1 -Window "*Chrome*"      (one window, by title wildcard)
  screenshot.ps1 -Path C:\temp\s.png
  screenshot.ps1 -ListMonitors
.NOTES
  After saving, read the PNG to look at it. Screens with protected content (DRM video,
  some password dialogs) come out black; that's Windows, not a bug.
#>
param(
    [string]$Path,
    [int]$Monitor = 0,
    [string]$Window,
    [switch]$ListMonitors
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing, System.Windows.Forms

if (-not ('WinCtl.Shot' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
namespace WinCtl {
    public static class Shot {
        [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
        [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
        [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
        [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
        [DllImport("dwmapi.dll")] static extern int DwmGetWindowAttribute(IntPtr h, int attr, out RECT r, int size);
        [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
        // Visible bounds without the invisible resize border Windows 10/11 adds.
        public static int[] Bounds(IntPtr h) {
            RECT r; DwmGetWindowAttribute(h, 9 /* DWMWA_EXTENDED_FRAME_BOUNDS */, out r, Marshal.SizeOf(typeof(RECT)));
            return new[] { r.L, r.T, r.R - r.L, r.B - r.T };
        }
    }
}
'@
}
[void][WinCtl.Shot]::SetProcessDPIAware()   # otherwise scaled displays (125%, 150%) get cropped

$screens = [System.Windows.Forms.Screen]::AllScreens | Sort-Object { -not $_.Primary }, { $_.Bounds.X }
if ($ListMonitors) {
    $i = 0
    $screens | ForEach-Object { $i++; [ordered]@{ monitor = $i; primary = $_.Primary; x = $_.Bounds.X; y = $_.Bounds.Y; width = $_.Bounds.Width; height = $_.Bounds.Height } } | ConvertTo-Json
    return
}

if ($Window) {
    $p = Get-Process | Where-Object { $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle -like $Window } | Select-Object -First 1
    if (-not $p) { throw "No window titled like '$Window'. Try: window.ps1 list" }
    $h = $p.MainWindowHandle
    if ([WinCtl.Shot]::IsIconic($h)) { [void][WinCtl.Shot]::ShowWindow($h, 9) }
    [void][WinCtl.Shot]::SetForegroundWindow($h)
    Start-Sleep -Milliseconds 300
    $b = [WinCtl.Shot]::Bounds($h)
    $rect = New-Object System.Drawing.Rectangle $b[0], $b[1], $b[2], $b[3]
} elseif ($Monitor -gt 0) {
    if ($Monitor -gt $screens.Count) { throw "There are only $($screens.Count) monitors." }
    $rect = $screens[$Monitor - 1].Bounds
} else {
    $rect = [System.Windows.Forms.SystemInformation]::VirtualScreen
}

if (-not $Path) {
    $dir = Join-Path ([Environment]::GetFolderPath('MyPictures')) 'Screenshots'
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $Path = Join-Path $dir ("shot-{0:yyyyMMdd-HHmmss}.png" -f (Get-Date))
}
$bmp = New-Object System.Drawing.Bitmap $rect.Width, $rect.Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
try {
    $g.CopyFromScreen($rect.X, $rect.Y, 0, 0, $bmp.Size)
    $bmp.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
} finally {
    $g.Dispose(); $bmp.Dispose()
}
[ordered]@{ path = (Resolve-Path $Path).Path; width = $rect.Width; height = $rect.Height } | ConvertTo-Json -Compress
