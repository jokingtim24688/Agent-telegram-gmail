<#
.SYNOPSIS
  List and control top-level windows.
.EXAMPLE
  window.ps1 list
  window.ps1 focus -Title "*Visual Studio Code*"
  window.ps1 focus -Process spotify
  window.ps1 maximize -Process chrome
  window.ps1 minimize-all                 (show desktop)
  window.ps1 move -Process notepad -X 0 -Y 0 -Width 960 -Height 1080   (left half of a 1920x1080 screen)
  window.ps1 close -Title "Untitled - Notepad"   (asks the app to close; it may prompt to save)
#>
param(
    [Parameter(Position = 0)]
    [ValidateSet('list', 'focus', 'minimize', 'maximize', 'restore', 'move', 'close', 'minimize-all')]
    [string]$Action = 'list',
    [string]$Title,
    [string]$Process,
    [int]$X, [int]$Y, [int]$Width, [int]$Height
)
$ErrorActionPreference = 'Stop'

if (-not ('WinCtl.Win' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;
namespace WinCtl {
    public class WinInfo { public IntPtr Handle; public string Title; public uint Pid; public int X, Y, Width, Height; public string State; }
    public static class Win {
        delegate bool EnumProc(IntPtr h, IntPtr l);
        [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
        [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
        [DllImport("user32.dll")] static extern int GetWindowTextLength(IntPtr h);
        [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
        [DllImport("user32.dll")] static extern bool IsIconic(IntPtr h);
        [DllImport("user32.dll")] static extern bool IsZoomed(IntPtr h);
        [DllImport("user32.dll")] static extern IntPtr GetWindow(IntPtr h, uint cmd);
        [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
        [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r);
        [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
        [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
        [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr h, int x, int y, int w, int hgt, bool repaint);
        [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);
        [DllImport("user32.dll")] static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
        [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
        [StructLayout(LayoutKind.Sequential)] struct RECT { public int L, T, R, B; }

        public static List<WinInfo> List() {
            var list = new List<WinInfo>();
            EnumWindows((h, l) => {
                if (!IsWindowVisible(h) || GetWindow(h, 4 /* GW_OWNER */) != IntPtr.Zero) return true;
                int n = GetWindowTextLength(h);
                if (n == 0) return true;
                var sb = new StringBuilder(n + 1);
                GetWindowText(h, sb, sb.Capacity);
                uint pid; GetWindowThreadProcessId(h, out pid);
                RECT r; GetWindowRect(h, out r);
                list.Add(new WinInfo { Handle = h, Title = sb.ToString(), Pid = pid, X = r.L, Y = r.T,
                    Width = r.R - r.L, Height = r.B - r.T,
                    State = IsIconic(h) ? "minimized" : IsZoomed(h) ? "maximized" : "normal" });
                return true;
            }, IntPtr.Zero);
            return list;
        }

        // Windows only lets the foreground app steal focus. A synthetic Alt press
        // satisfies that rule, so SetForegroundWindow works from a background script.
        public static bool Focus(IntPtr h) {
            if (IsIconic(h)) ShowWindow(h, 9 /* SW_RESTORE */);
            keybd_event(0x12, 0, 0, UIntPtr.Zero);
            keybd_event(0x12, 0, 2, UIntPtr.Zero);
            return SetForegroundWindow(h);
        }
    }
}
'@
}
[void][WinCtl.Win]::SetProcessDPIAware()

function Get-Windows {
    $names = @{}
    Get-Process | ForEach-Object { $names[[uint32]$_.Id] = $_.ProcessName }
    [WinCtl.Win]::List() | ForEach-Object {
        [pscustomobject]@{
            title   = $_.Title
            process = $names[$_.Pid]
            pid     = $_.Pid
            state   = $_.State
            x       = $_.X; y = $_.Y; width = $_.Width; height = $_.Height
            handle  = $_.Handle
        }
    }
}

if ($Action -eq 'list') {
    Get-Windows | Select-Object title, process, pid, state, x, y, width, height | ConvertTo-Json -Depth 2
    return
}
if ($Action -eq 'minimize-all') {
    (New-Object -ComObject Shell.Application).MinimizeAll()
    'minimized all windows'
    return
}
if (-not $Title -and -not $Process) { throw "Give -Title (wildcards allowed) or -Process (e.g. chrome)." }

$matches_ = @(Get-Windows | Where-Object {
        ((-not $Title) -or $_.title -like $Title) -and ((-not $Process) -or $_.process -like $Process)
    })
if ($matches_.Count -eq 0) {
    $hint = (Get-Windows | Select-Object -ExpandProperty title | Select-Object -First 15) -join "`n  "
    throw "No window matches. Open windows include:`n  $hint"
}
$w = $matches_[0]
$h = [IntPtr]$w.handle

switch ($Action) {
    'focus' { [void][WinCtl.Win]::Focus($h) }
    'minimize' { [void][WinCtl.Win]::ShowWindow($h, 6) }
    'maximize' { [void][WinCtl.Win]::ShowWindow($h, 3) }
    'restore' { [void][WinCtl.Win]::ShowWindow($h, 9) }
    'move' {
        [void][WinCtl.Win]::ShowWindow($h, 9)
        $nw = if ($PSBoundParameters.ContainsKey('Width')) { $Width } else { $w.width }
        $nh = if ($PSBoundParameters.ContainsKey('Height')) { $Height } else { $w.height }
        $nx = if ($PSBoundParameters.ContainsKey('X')) { $X } else { $w.x }
        $ny = if ($PSBoundParameters.ContainsKey('Y')) { $Y } else { $w.y }
        [void][WinCtl.Win]::MoveWindow($h, $nx, $ny, $nw, $nh, $true)
    }
    'close' { [void][WinCtl.Win]::PostMessage($h, 0x0010 <# WM_CLOSE #>, [IntPtr]::Zero, [IntPtr]::Zero) }
}
$note = if ($matches_.Count -gt 1) { " (first of $($matches_.Count) matches)" } else { '' }
"$Action -> '$($w.title)' [$($w.process)]$note"
