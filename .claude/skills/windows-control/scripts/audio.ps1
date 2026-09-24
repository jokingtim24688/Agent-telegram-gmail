<#
.SYNOPSIS
  Master volume and media keys for the default playback device.
.DESCRIPTION
  Uses the Windows Core Audio API (IAudioEndpointVolume), so "set 30" means exactly 30%,
  unlike pressing volume keys, which moves in steps of 2.
.EXAMPLE
  audio.ps1 get              -> {"volume":45,"muted":false}
  audio.ps1 set 30
  audio.ps1 up 10  /  audio.ps1 down 10
  audio.ps1 mute / unmute / toggle-mute
  audio.ps1 play-pause / next / previous / stop     (media keys: Spotify, browsers, etc.)
  audio.ps1 devices          -> playback devices (switching needs the AudioDeviceCmdlets module)
#>
param(
    [Parameter(Position = 0)]
    [ValidateSet('get', 'set', 'up', 'down', 'mute', 'unmute', 'toggle-mute', 'play-pause', 'next', 'previous', 'stop', 'devices')]
    [string]$Action = 'get',
    [Parameter(Position = 1)]
    [ValidateRange(0, 100)]
    [int]$Value = 10
)
$ErrorActionPreference = 'Stop'

if (-not ('WinCtl.Audio' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
namespace WinCtl {
    [ComImport, Guid("5CDF2C82-841E-4546-9722-0CF74078229A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IAudioEndpointVolume {
        int RegisterControlChangeNotify(IntPtr p);
        int UnregisterControlChangeNotify(IntPtr p);
        int GetChannelCount(out uint count);
        int SetMasterVolumeLevel(float level, ref Guid ctx);
        int SetMasterVolumeLevelScalar(float level, ref Guid ctx);
        int GetMasterVolumeLevel(out float level);
        int GetMasterVolumeLevelScalar(out float level);
        int SetChannelVolumeLevel(uint ch, float level, ref Guid ctx);
        int SetChannelVolumeLevelScalar(uint ch, float level, ref Guid ctx);
        int GetChannelVolumeLevel(uint ch, out float level);
        int GetChannelVolumeLevelScalar(uint ch, out float level);
        int SetMute([MarshalAs(UnmanagedType.Bool)] bool mute, ref Guid ctx);
        int GetMute([MarshalAs(UnmanagedType.Bool)] out bool mute);
    }
    [ComImport, Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IMMDevice {
        int Activate(ref Guid iid, int clsCtx, IntPtr activationParams, [MarshalAs(UnmanagedType.IUnknown)] out object iface);
    }
    [ComImport, Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IMMDeviceEnumerator {
        int EnumAudioEndpoints(int dataFlow, int stateMask, out IntPtr devices);
        int GetDefaultAudioEndpoint(int dataFlow, int role, out IMMDevice device);
    }
    [ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")]
    class MMDeviceEnumerator { }

    public static class Audio {
        static IAudioEndpointVolume Endpoint() {
            var enumerator = (IMMDeviceEnumerator)(new MMDeviceEnumerator());
            IMMDevice device;
            Marshal.ThrowExceptionForHR(enumerator.GetDefaultAudioEndpoint(0 /* render */, 1 /* multimedia */, out device));
            Guid iid = typeof(IAudioEndpointVolume).GUID;
            object o;
            Marshal.ThrowExceptionForHR(device.Activate(ref iid, 23 /* CLSCTX_ALL */, IntPtr.Zero, out o));
            return (IAudioEndpointVolume)o;
        }
        public static int GetVolume() {
            float v; Marshal.ThrowExceptionForHR(Endpoint().GetMasterVolumeLevelScalar(out v));
            return (int)Math.Round(v * 100);
        }
        public static void SetVolume(int percent) {
            Guid g = Guid.Empty;
            float v = Math.Max(0, Math.Min(100, percent)) / 100f;
            Marshal.ThrowExceptionForHR(Endpoint().SetMasterVolumeLevelScalar(v, ref g));
        }
        public static bool GetMute() {
            bool m; Marshal.ThrowExceptionForHR(Endpoint().GetMute(out m)); return m;
        }
        public static void SetMute(bool mute) {
            Guid g = Guid.Empty; Marshal.ThrowExceptionForHR(Endpoint().SetMute(mute, ref g));
        }
        [DllImport("user32.dll")] static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
        public static void Key(byte vk) {
            keybd_event(vk, 0, 0, UIntPtr.Zero);
            keybd_event(vk, 0, 2 /* KEYUP */, UIntPtr.Zero);
        }
    }
}
'@
}

function State { [ordered]@{ volume = [WinCtl.Audio]::GetVolume(); muted = [WinCtl.Audio]::GetMute() } | ConvertTo-Json -Compress }

switch ($Action) {
    'get' { State }
    'set' { [WinCtl.Audio]::SetVolume($Value); State }
    'up' { [WinCtl.Audio]::SetVolume([WinCtl.Audio]::GetVolume() + $Value); State }
    'down' { [WinCtl.Audio]::SetVolume([WinCtl.Audio]::GetVolume() - $Value); State }
    'mute' { [WinCtl.Audio]::SetMute($true); State }
    'unmute' { [WinCtl.Audio]::SetMute($false); State }
    'toggle-mute' { [WinCtl.Audio]::SetMute(-not [WinCtl.Audio]::GetMute()); State }
    'play-pause' { [WinCtl.Audio]::Key(0xB3); 'sent play/pause' }
    'next' { [WinCtl.Audio]::Key(0xB0); 'sent next track' }
    'previous' { [WinCtl.Audio]::Key(0xB1); 'sent previous track' }
    'stop' { [WinCtl.Audio]::Key(0xB2); 'sent stop' }
    'devices' {
        Get-CimInstance Win32_SoundDevice | Select-Object Name, Manufacturer, Status | ConvertTo-Json
        'To switch the default device: Install-Module AudioDeviceCmdlets -Scope CurrentUser; Get-AudioDevice -List; Set-AudioDevice -Index N'
    }
}
