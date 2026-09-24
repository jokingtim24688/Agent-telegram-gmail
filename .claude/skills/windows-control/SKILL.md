---
name: windows-control
description: >-
  Operate and automate a Windows 10/11 PC from the terminal (PowerShell-first): files and search,
  installing/uninstalling apps with winget, launching and closing programs, hardware info (CPU,
  GPU/VRAM, RAM, disks, battery), volume and media keys, brightness, dark mode, wallpaper,
  window/keyboard/mouse control, screenshots, notifications, speech, Wi-Fi and network fixes,
  firewall, services, scheduled tasks, registry, PATH, power and shutdown, Windows Update, Defender,
  disk cleanup, event logs, drivers, printers, WSL and Office automation. Use it whenever the user
  wants something done on or learned about their Windows computer, even without saying PowerShell or
  Windows, e.g. free up space, what GPU do I have, turn the volume down, why is my PC slow, install
  Discord, run this every morning, my wifi keeps dropping, take a screenshot. For deep control of
  specific apps (Steam, Spotify, Blender, Minecraft) also see app-launcher-control.
---

# Windows control

PowerShell is the main tool. Nearly everything Windows exposes (files, processes, services,
network, hardware, settings) is reachable from it, and the output comes back as objects you
can filter and convert to JSON. Classic tools (`winget`, `netsh`, `powercfg`, `robocopy`,
`pnputil`, `icacls`, `schtasks`) fill the gaps. For things Windows has no command for (exact
volume level, moving windows, sending keystrokes, screenshots, toast notifications), use the
bundled scripts in `scripts/`. They wrap the Win32 and COM calls, so you don't have to rewrite
that interop each time.

## Before running anything: know your shell

In Claude Code on Windows, the Bash tool usually runs **Git Bash**, not PowerShell. So:

- **One-liners:** `powershell.exe -NoProfile -Command '<command>'`. Single quotes stop bash
  from expanding `$variables`. Use `pwsh` instead of `powershell.exe` if PowerShell 7 is installed.
- **Anything longer than one line, or with nested quotes:** write a `.ps1` file and run
  `powershell.exe -NoProfile -ExecutionPolicy Bypass -File path\to\script.ps1 -Arg value`.
  Quoting bugs between bash and PowerShell waste more time than anything else, and `-File`
  avoids them entirely.
- **Bundled scripts:** `powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<skill-dir>/scripts/<name>.ps1" ...`
- **Structured output:** end the pipeline with `| ConvertTo-Json -Depth 4`, so you parse data
  rather than column-formatted text that truncates.
- `-ExecutionPolicy Bypass` applies only to that one process. It doesn't change the machine's
  policy, which is why it's safe to use routinely.
- Windows PowerShell 5.1 is always installed. PowerShell 7 (`pwsh`) might not be. The bundled
  scripts work in both. `notify.ps1` works best in 5.1 because it can use real toast
  notifications there.

Check whether the session is elevated before trying admin-only work:

```powershell
([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
```

You can't click the UAC prompt yourself. If a task needs admin rights and the session isn't
elevated, either ask the user to restart the terminal as Administrator, or launch that one
step elevated with `Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile','-File','C:\path\task.ps1'`,
which makes the user approve UAC. Output from an elevated child doesn't come back to you, so
have the script write its results to a file, and read that file afterwards.

## How careful to be

It's the user's own machine, so match your caution to how hard the action is to undo:

| Kind of action | Examples | What to do |
|---|---|---|
| Read-only | system info, listing files, checking the network | Just do it. |
| Easy to undo | volume, dark mode, opening apps, creating files | Do it, and say what you changed. |
| Hard to undo | deleting files, uninstalling apps, registry edits, killing processes, changing the firewall, emptying the Recycle Bin | Show what will be affected first (`-WhatIf`, a dry-run list, sizes and counts). Then get a clear yes. |
| System-level | driver changes, disabling services, BitLocker, boot settings, user accounts | Make a restore point first (`Checkpoint-Computer -Description "before X"`, needs admin), explain the risk, and get a clear yes. |

Two recurring cases:

- **Security features** (Defender, Windows Firewall, UAC, SmartScreen): don't turn them off
  just to make another step work. Look for the targeted fix instead: an exclusion for one
  folder, a firewall rule for one app. Turn a feature off only if the user explicitly asks,
  and tell them how to turn it back on.
- **Deleting:** prefer the Recycle Bin (see `references/files-and-search.md`) to
  `Remove-Item`, so the user can get files back. Never delete from `C:\Windows`,
  `Program Files` or another user's profile unless the user has pointed at those exact paths.

## Where to look

Read the one reference file that matches the task. Each has tested commands and the gotchas
for its area.

| Task area | Reference |
|---|---|
| Files, folders, search, large files, archives, hashes, permissions, shortcuts, Recycle Bin, robocopy | `references/files-and-search.md` |
| Installing, updating and uninstalling apps (winget), launching and closing programs, startup apps, default apps | `references/apps-and-processes.md` |
| Hardware and system info, performance, disks, battery, drivers, devices, power and sleep, Windows Update, repair (SFC/DISM), event logs, cleanup | `references/system-and-hardware.md` |
| Network, Wi-Fi, DNS, IP, ports, firewall, hosts file, proxy, network drives, "internet not working" | `references/network.md` |
| Volume, media keys, brightness, dark mode, wallpaper, Explorer options, Settings pages (`ms-settings:`), display | `references/settings-and-personalization.md` |
| Scheduled tasks, services, registry, environment variables and PATH, clipboard, windows, keyboard and mouse, screenshots, notifications, speech | `references/automation-and-ui.md` |
| Defender, BitLocker, local users and groups, credentials, UAC | `references/security-and-users.md` |
| Developer setup: WSL, Docker, Git, Python/Node, Windows Terminal, OpenSSH, long paths, Sandbox | `references/dev-tools.md` |
| Excel, Word and Outlook automation, printing, PDFs, audio and video conversion | `references/office-and-media.md` |
| "Not recognized", execution policy, access denied, file in use, encoding problems, a slow PC, a full disk | `references/troubleshooting.md` |

## Bundled scripts

All scripts take `-Help`-style parameters (run them with no arguments for usage) and print
JSON or plain confirmations. Where each is used is covered in the references.

| Script | Does |
|---|---|
| `sysinfo.ps1` | One-shot system snapshot as JSON: OS, CPU, GPU and VRAM, RAM, disks, battery, network, uptime, top processes |
| `audio.ps1` | Get or set master volume to an exact %, mute and unmute, media keys (play/pause, next, previous) |
| `window.ps1` | List, focus, minimize, maximize, restore, move/resize and close windows by title or process |
| `input.ps1` | Type text, send key combos, move and click the mouse |
| `screenshot.ps1` | Save the whole screen, one monitor, or a single window to PNG |
| `notify.ps1` | Show a Windows notification (toast in PowerShell 5.1, balloon fallback) |
| `speak.ps1` | Read text aloud (built-in speech synthesis) |
| `display.ps1` | Brightness (laptops), dark/light mode, wallpaper |
| `cleanup.ps1` | Measure and optionally clear temp files, the Recycle Bin, crash dumps and the update cache. Dry run by default |
| `find-large.ps1` | Largest files and folders under a path |

## Working style

- **Look before changing.** Read the current value first (volume, a registry key, a service's
  start type) so you can report "was X, now Y", and so you know how to undo it.
- **Check it took.** Re-read state after changing it. Many Windows settings silently need a
  sign-out, an Explorer restart (`Stop-Process -Name explorer`; it relaunches itself) or a
  reboot. When that's the case, say so rather than implying it's done.
- **Write reusable automations as files.** If the user wants something repeatable ("every
  morning", "when I log in"), save a `.ps1` somewhere sensible (for example
  `$HOME\Scripts\`) and register a scheduled task pointing at it. Don't bury a long command
  inside the task itself. See `references/automation-and-ui.md`.
- **Answer in the user's terms.** Report "Chrome is using 3.1 GB of your 16 GB", not a
  process table. Keep raw output to what backs up the answer.
