# Developer setup

## Core toolchain via winget

```powershell
winget install -e --id Git.Git
winget install -e --id Microsoft.PowerShell              # PowerShell 7 (pwsh)
winget install -e --id Microsoft.WindowsTerminal         # built into Windows 11
winget install -e --id Microsoft.VisualStudioCode
winget install -e --id Python.Python.3.12                # then use `py -3.12` or `python`
winget install -e --id OpenJS.NodeJS.LTS                 # or Schniz.fnm for several Node versions
winget install -e --id GoLang.Go ; winget install -e --id Rustlang.Rustup
winget install -e --id Docker.DockerDesktop              # needs WSL 2; reboot after
winget install -e --id Microsoft.VisualStudio.2022.BuildTools --override "--quiet --wait --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"   # C/C++ compilers (pip wheels, node-gyp)
```

Refresh PATH afterwards: see `troubleshooting.md`.

**The `python` command opens the Microsoft Store?** That's an "App execution alias" stub. Turn
off `python.exe` / `python3.exe` at Settings → Apps → Advanced app settings → App execution
aliases (`Start-Process ms-settings:advanced-apps`), or use the `py` launcher.

```powershell
py -0p                                   # every installed Python and its path
py -3.12 -m venv .venv ; .\.venv\Scripts\Activate.ps1
```

## WSL (Linux on Windows)

```powershell
wsl --install                            # (admin) installs WSL 2 + Ubuntu; reboot
wsl --install -d Debian ; wsl -l -o      # other distros / list available
wsl -l -v                                # installed distros and WSL version
wsl --update ; wsl --shutdown            # update the kernel / stop everything (frees RAM)
wsl -d Ubuntu -- bash -lc 'uname -a'     # run a command in a distro
\\wsl$\Ubuntu\home\<user>                # Linux files from Explorer
```

Limit WSL's RAM and CPUs with `$HOME\.wslconfig`, then run `wsl --shutdown`:

```ini
[wsl2]
memory=8GB
processors=4
```

Keep project files inside the Linux file system (`~/project`), not `/mnt/c/...`. Cross-OS
file access is many times slower.

## GPU / CUDA

```powershell
nvidia-smi                               # driver + CUDA version the driver supports
winget install -e --id Nvidia.CUDA       # toolkit (only if compiling CUDA; PyTorch wheels bundle their own)
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

## OpenSSH

```powershell
Get-WindowsCapability -Online -Name OpenSSH*             # (admin)
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
Start-Service sshd ; Set-Service sshd -StartupType Automatic
# Keys for administrators go in C:\ProgramData\ssh\administrators_authorized_keys (not ~\.ssh\authorized_keys)
ssh-keygen -t ed25519 ; Get-Service ssh-agent | Set-Service -StartupType Automatic ; Start-Service ssh-agent ; ssh-add
```

## Windows features

```powershell
Get-WindowsOptionalFeature -Online | Where-Object State -eq Enabled | Select-Object FeatureName   # admin
Enable-WindowsOptionalFeature -Online -FeatureName Containers-DisposableClientVM -All   # Windows Sandbox (Pro/Enterprise), reboot
Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -All              # Hyper-V (Pro), reboot
Start-Process optionalfeatures.exe                                                     # GUI list
```

**Windows Sandbox** is a throwaway VM: good for trying an untrusted installer. Everything is
deleted when it closes.

## Long paths, symlinks, Developer Mode

```powershell
Set-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' LongPathsEnabled 1 -Type DWord   # admin; apps must also opt in
git config --system core.longpaths true
Start-Process ms-settings:developers        # Developer Mode: symlinks without admin, sideloading
```

## PowerShell environment

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned      # local scripts run; downloaded ones must be signed or unblocked
$PROFILE ; notepad $PROFILE                               # startup script (create with New-Item $PROFILE -Force)
Install-Module PSReadLine -Scope CurrentUser -Force       # better line editing and history search
Get-History ; (Get-PSReadLineOption).HistorySavePath      # command history across sessions
```

## Windows Terminal

Its settings are JSON at
`$env:LOCALAPPDATA\Packages\Microsoft.WindowsTerminal_8wekyb3d8bbwe\LocalState\settings.json`.
Back it up before editing. Useful launches: `wt -d C:\project`, `wt -p "Ubuntu"`,
`wt new-tab -p "PowerShell" ; split-pane -p "Ubuntu"`.

## Ports and dev servers

"Port already in use" → `Get-NetTCPConnection -LocalPort 3000 -State Listen | Select-Object OwningProcess`,
then look at that process (see `apps-and-processes.md`). Letting a phone on the same Wi-Fi
reach a dev server needs a Private-profile firewall rule (see `network.md`).
