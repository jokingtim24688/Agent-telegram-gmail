<#
.SYNOPSIS
  Synthetic keyboard and mouse input for the foreground window.
.DESCRIPTION
  Input goes to whatever window has focus, so focus the target first (window.ps1 focus ...).
  Coordinates are physical screen pixels (the script is DPI-aware), which match screenshot.ps1.
  Apps running as Administrator ignore input from a non-elevated script (Windows UIPI).
.EXAMPLE
  input.ps1 type "Hello, world"            (any Unicode text; newlines press Enter)
  input.ps1 keys "ctrl+s"
  input.ps1 keys "win+d"
  input.ps1 keys "ctrl+shift+esc"
  input.ps1 keys "alt+f4"
  input.ps1 keys "enter"
  input.ps1 click -X 960 -Y 540            (left click)
  input.ps1 click -X 960 -Y 540 -Button right
  input.ps1 double-click -X 100 -Y 200
  input.ps1 move -X 10 -Y 10
  input.ps1 scroll -Amount -5              (negative = down)
  input.ps1 position                       (where the mouse is now)
#>
param(
    [Parameter(Position = 0, Mandatory)]
    [ValidateSet('type', 'keys', 'click', 'double-click', 'move', 'scroll', 'position')]
    [string]$Action,
    [Parameter(Position = 1)]
    [string]$Text,
    [int]$X = -1, [int]$Y = -1,
    [ValidateSet('left', 'right', 'middle')]
    [string]$Button = 'left',
    [int]$Amount = -3,
    [int]$DelayMs = 0
)
$ErrorActionPreference = 'Stop'

if (-not ('WinCtl.Input' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
namespace WinCtl {
    public static class Input {
        [StructLayout(LayoutKind.Sequential)] struct KEYBDINPUT { public ushort wVk; public ushort wScan; public uint dwFlags; public uint time; public IntPtr extra; }
        [StructLayout(LayoutKind.Sequential)] struct MOUSEINPUT { public int dx; public int dy; public uint mouseData; public uint dwFlags; public uint time; public IntPtr extra; }
        [StructLayout(LayoutKind.Explicit)] struct UNION { [FieldOffset(0)] public MOUSEINPUT mi; [FieldOffset(0)] public KEYBDINPUT ki; }
        [StructLayout(LayoutKind.Sequential)] struct INPUT { public uint type; public UNION u; }
        [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X; public int Y; }

        [DllImport("user32.dll", SetLastError = true)] static extern uint SendInput(uint n, INPUT[] inputs, int size);
        [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
        [DllImport("user32.dll")] public static extern bool GetCursorPos(out POINT p);
        [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();

        static void Send(INPUT[] inputs) {
            if (SendInput((uint)inputs.Length, inputs, Marshal.SizeOf(typeof(INPUT))) != inputs.Length)
                throw new InvalidOperationException("SendInput was blocked (is the target app running as Administrator?)");
        }
        static INPUT Key(ushort vk, ushort scan, uint flags) {
            var i = new INPUT { type = 1 };
            i.u.ki = new KEYBDINPUT { wVk = vk, wScan = scan, dwFlags = flags };
            return i;
        }
        static bool IsExtended(ushort vk) {
            // arrows, Home/End/PgUp/PgDn, Insert/Delete, Win keys, right Ctrl/Alt need the extended flag
            return (vk >= 0x21 && vk <= 0x28) || vk == 0x2D || vk == 0x2E || vk == 0x5B || vk == 0x5C || vk == 0xA3 || vk == 0xA5;
        }
        public static void Combo(ushort[] vks) {
            var list = new System.Collections.Generic.List<INPUT>();
            foreach (var vk in vks) list.Add(Key(vk, 0, IsExtended(vk) ? 1u : 0u));
            for (int n = vks.Length - 1; n >= 0; n--) list.Add(Key(vks[n], 0, (IsExtended(vks[n]) ? 1u : 0u) | 2u));
            Send(list.ToArray());
        }
        public static void Type(string text) {
            foreach (char c in text) {
                if (c == '\r') continue;
                if (c == '\n') { Combo(new ushort[] { 0x0D }); continue; }
                Send(new[] { Key(0, c, 4 /* UNICODE */), Key(0, c, 4 | 2) });
            }
        }
        public static void Mouse(uint flags, int data) {
            var i = new INPUT { type = 0 };
            i.u.mi = new MOUSEINPUT { dwFlags = flags, mouseData = (uint)data };
            Send(new[] { i });
        }
    }
}
'@
}
[void][WinCtl.Input]::SetProcessDPIAware()

$vk = @{
    ctrl = 0x11; control = 0x11; shift = 0x10; alt = 0x12; win = 0x5B; windows = 0x5B
    enter = 0x0D; return = 0x0D; esc = 0x1B; escape = 0x1B; tab = 0x09; space = 0x20
    backspace = 0x08; delete = 0x2E; del = 0x2E; insert = 0x2D; home = 0x24; end = 0x23
    pageup = 0x21; pgup = 0x21; pagedown = 0x22; pgdn = 0x22
    left = 0x25; up = 0x26; right = 0x27; down = 0x28
    printscreen = 0x2C; prtsc = 0x2C; capslock = 0x14; menu = 0x5D; apps = 0x5D
    volumeup = 0xAF; volumedown = 0xAE; mute = 0xAD; playpause = 0xB3; nexttrack = 0xB0; prevtrack = 0xB1
    ';' = 0xBA; '=' = 0xBB; ',' = 0xBC; '-' = 0xBD; '.' = 0xBE; '/' = 0xBF; '`' = 0xC0
    '[' = 0xDB; '\' = 0xDC; ']' = 0xDD; "'" = 0xDE
}
function Resolve-Key([string]$name) {
    $n = $name.Trim().ToLower()
    if ($vk.ContainsKey($n)) { return [uint16]$vk[$n] }
    if ($n -match '^f([1-9]|1\d|2[0-4])$') { return [uint16](0x6F + [int]$Matches[1]) }
    if ($n -match '^[a-z0-9]$') { return [uint16][char]$n.ToUpper() }
    throw "Unknown key '$name'. Use names like ctrl, shift, alt, win, enter, esc, tab, f5, a-z, 0-9, left, pageup."
}
function Need-XY { if ($X -lt 0 -or $Y -lt 0) { throw "Give -X and -Y (physical pixels)." } }
$buttons = @{ left = @(0x02, 0x04); right = @(0x08, 0x10); middle = @(0x20, 0x40) }

if ($DelayMs -gt 0) { Start-Sleep -Milliseconds $DelayMs }
switch ($Action) {
    'type' { [WinCtl.Input]::Type($Text); "typed $($Text.Length) characters" }
    'keys' {
        $codes = [uint16[]]@($Text -split '\+' | Where-Object { $_ } | ForEach-Object { Resolve-Key $_ })
        [WinCtl.Input]::Combo($codes)
        "pressed $Text"
    }
    'move' { Need-XY; [void][WinCtl.Input]::SetCursorPos($X, $Y); "mouse at $X,$Y" }
    { $_ -in 'click', 'double-click' } {
        if ($X -ge 0 -and $Y -ge 0) { [void][WinCtl.Input]::SetCursorPos($X, $Y); Start-Sleep -Milliseconds 30 }
        $times = if ($Action -eq 'double-click') { 2 } else { 1 }
        for ($i = 0; $i -lt $times; $i++) {
            [WinCtl.Input]::Mouse($buttons[$Button][0], 0)
            [WinCtl.Input]::Mouse($buttons[$Button][1], 0)
            Start-Sleep -Milliseconds 40
        }
        "$Action ($Button)"
    }
    'scroll' { [WinCtl.Input]::Mouse(0x0800, 120 * $Amount); "scrolled $Amount" }
    'position' {
        $p = New-Object WinCtl.Input+POINT
        [void][WinCtl.Input]::GetCursorPos([ref]$p)
        [ordered]@{ x = $p.X; y = $p.Y } | ConvertTo-Json -Compress
    }
}
