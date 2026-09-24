# Troubleshooting

## Running commands

**"X is not recognized as the name of a cmdlet…"** right after installing: this terminal's PATH
is stale. Refresh it without reopening:

```powershell
$env:PATH = [Environment]::GetEnvironmentVariable('PATH', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('PATH', 'User')
```

In Git Bash, the fastest fix is to call the tool by its full path, or restart the session.
Find where it installed with `winget list <name>` and `Get-ChildItem "$env:LOCALAPPDATA\Programs", $env:ProgramFiles -Filter <name>.exe -Recurse -Depth 3`.

**"…cannot be loaded because running scripts is disabled"**: the execution policy. Run the
script with `powershell -ExecutionPolicy Bypass -File x.ps1` (this process only), or set
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once. Downloaded scripts also need
`Unblock-File`.

**Quoting between Git Bash and PowerShell.** Bash expands `$var` inside double quotes before
PowerShell sees it. Use single quotes around `-Command '...'`, and for anything with nested
quotes, write a `.ps1` file and use `-File`. Inside PowerShell, backtick (`` ` ``) is the
escape character, not backslash.

**A command hangs forever**: it's waiting for input you can't see. Add `-Confirm:$false`,
`-Force`, `-y`, or winget's `--accept-source-agreements --accept-package-agreements`, or
pipe in an answer. Put a `timeout` on the Bash call so a hang doesn't eat the session.

**Output cut off with "…"**: that's table formatting. Use `| ConvertTo-Json -Depth 4`,
`| Format-List *`, or `| Out-String -Width 4096`.

**Garbled characters (Ã©, ?) in output or files**: Windows PowerShell 5.1 writes UTF-16 by
default with `>` and `Out-File`. Use `-Encoding utf8` (`Set-Content`, `Out-File`,
`Export-Csv`), or run `[Console]::OutputEncoding = [Text.UTF8Encoding]::new()` before
printing. `chcp 65001` fixes cmd.

**Works in the terminal, fails as a scheduled task**: the working directory is System32,
mapped drives don't exist, `$HOME` differs under SYSTEM, and there's no desktop for GUIs. Use
absolute paths and UNC paths, and log to a file (`Start-Transcript -Path C:\Logs\task.log`)
to see what happened.

**32-bit vs 64-bit**: a 32-bit process sees `SysWOW64` and `WOW6432Node` redirected views.
`[Environment]::Is64BitProcess` tells you which one you're in. Use `$env:WINDIR\Sysnative\`
to reach real System32 from a 32-bit shell.

## Access denied

Work out which case it is:

1. **Needs admin**: check with the elevation test in SKILL.md. Rerun elevated, or ask the user.
2. **File in use**: another process has it open. Find it with Resource Monitor (Associated
   Handles) or `handle.exe` (see `apps-and-processes.md`), and close that app.
3. **Controlled folder access**: Defender blocks writes to Documents, Desktop and Pictures by
   untrusted apps. See `security-and-users.md`.
4. **Permissions or ownership** on old drives and folders from another PC: `icacls` /
   `takeown` (see `files-and-search.md`).
5. **`C:\Program Files\WindowsApps`** and system folders are protected on purpose. Don't
   fight them.
6. **OneDrive**: a file that's "online-only" or mid-sync can fail to open or rename. Check with
   `attrib <file>`: `P` means pinned (always local) and `U` means online-only. Make it local with
   `attrib +p -u <file>`, or pause syncing.

## "My PC is slow"

Follow the performance checklist in `system-and-hardware.md`. Well-known culprits by name:

| Process | Usually means | What to do |
|---|---|---|
| `MsMpEng` (Antimalware Service Executable) | a Defender scan is running | Let it finish. For persistently high usage, add a narrow exclusion for a busy dev folder |
| `SearchIndexer` / `SearchHost` | rebuilding the search index | Wait, or trim indexed locations (`control srchadmin.dll`) |
| `TiWorker` / `TrustedInstaller` | Windows Update installing | Let it finish, then reboot |
| `WmiPrvSE` | some app polling WMI too hard | `Get-WinEvent Microsoft-Windows-WMI-Activity/Operational` names the client PID |
| `dwm` high GPU | many high-refresh monitors or a driver problem | Update the GPU driver |
| `System` / `ntoskrnl` high CPU | a driver problem | Update chipset, storage, Wi-Fi and GPU drivers |
| Disk at 100% on an HDD | Search, Update or a scan on a spinning disk | An SSD upgrade is the real fix |
| Memory full | too many browser tabs, or a leak | Sort processes by RAM; restart the leaking app |

## Disk full

In order of safety:
1. `scripts/cleanup.ps1` (temp files, Recycle Bin, caches).
2. `scripts/find-large.ps1 -Folders`, starting from `C:\Users\<name>`. Old downloads, videos
   and game libraries are the usual finds; the user decides what goes.
3. `Windows.old` after an upgrade: Settings → Storage → Temporary files ("Previous Windows
   installation"). Only after the user is happy with the upgrade.
4. `DISM /Online /Cleanup-Image /StartComponentCleanup` (admin).
5. Hibernation file: `powercfg /hibernate off` frees RAM-sized space, but disables hibernate
   and Fast Startup.
6. Move big libraries (Steam, videos) to another drive with the app's own "move" feature, not
   by hand.

Never delete from `C:\Windows\WinSxS`, `C:\Windows\Installer`, `System Volume Information`
or `pagefile.sys` by hand.

## Explorer, Start menu or taskbar frozen

```powershell
Stop-Process -Name explorer -Force        # it restarts itself; if not: Start-Process explorer
Get-Process StartMenuExperienceHost, SearchHost -ErrorAction SilentlyContinue | Stop-Process -Force   # Start and search restart on the next click
```

If the Start menu is still broken: `sfc /scannow`, then `DISM ... /RestoreHealth` (admin).

## An app won't open or crashes on start

1. `Get-WinEvent -FilterHashtable @{LogName='Application'; Id=1000,1026} -MaxEvents 5`: the
   faulting module often names the cause (a missing VC++ runtime, a GPU driver).
2. Missing runtime: `winget install Microsoft.VCRedist.2015+.x64` (and `.x86`), and
   `Microsoft.DotNet.DesktopRuntime.8`.
3. Store apps: `Get-AppxPackage *name* | Reset-AppxPackage` (resets the app's data), or
   Settings → Apps → the app → Advanced options → Repair.
4. Run it once as admin, to rule out a permissions problem. Don't leave it set to always
   run as admin.

## Bluescreens and random restarts

`Get-WinEvent -FilterHashtable @{LogName='System'; Id=41,1001} -MaxEvents 10`, and look for
dump files in `C:\Windows\Minidump`. The stop code and the driver named in event 1001 point
to the culprit, which is usually a GPU, storage or network driver, or unstable RAM or
overclock settings. Memory test: `mdsched.exe` (reboots).

## Time and sign-in problems

The clock is wrong (so HTTPS errors appear everywhere) → `w32tm /resync` (admin), or turn on
"Set time automatically". A PIN or Windows Hello that stopped working →
`Start-Process ms-settings:signinoptions`. Don't touch `C:\Windows\ServiceProfiles\...\Ngc`
without the user's clear understanding that it resets all PINs.
