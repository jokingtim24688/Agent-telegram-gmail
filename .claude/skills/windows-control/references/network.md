# Network

## Current state

```powershell
Get-NetIPConfiguration | Where-Object IPv4DefaultGateway          # the adapter actually in use: IP, gateway, DNS
Get-NetAdapter | Select-Object Name, Status, LinkSpeed, MediaType, MacAddress
netsh wlan show interfaces                                         # Wi-Fi: SSID, signal %, band, channel, speed
(Invoke-RestMethod https://api.ipify.org)                          # public IP
Test-NetConnection 8.8.8.8 ; Test-NetConnection google.com -Port 443   # reachability and TCP port
Resolve-DnsName example.com                                        # DNS lookup
tracert -d 8.8.8.8 ; pathping -n 8.8.8.8                           # where along the path it breaks
```

## "The internet isn't working": triage in order

Each step narrows where the problem is. Stop at the first one that fails, and tell the user
what that means.

```powershell
Get-NetAdapter | Where-Object Status -eq 'Up'           # 1. Is any adapter connected? None → Wi-Fi off, cable, airplane mode
Get-NetIPAddress -AddressFamily IPv4 | Where-Object IPAddress -like '169.254*'   # 2. 169.254.x.x → no DHCP lease from the router
Test-NetConnection (Get-NetIPConfiguration | Where-Object IPv4DefaultGateway).IPv4DefaultGateway.NextHop   # 3. Router reachable?
Test-NetConnection 1.1.1.1                              # 4. Internet by IP? Fails → router/ISP problem
Resolve-DnsName google.com                              # 5. DNS works? 4 passes but 5 fails → DNS problem
Test-NetConnection google.com -Port 443                 # 6. HTTPS works? Fails → proxy, firewall or VPN
```

Fixes, least disruptive first:

```powershell
ipconfig /flushdns                                       # stale DNS
ipconfig /release ; ipconfig /renew                      # new DHCP lease (drops the connection for a moment)
Restart-NetAdapter -Name 'Wi-Fi'                         # (admin) bounce the adapter
Set-DnsClientServerAddress -InterfaceAlias 'Wi-Fi' -ServerAddresses 1.1.1.1, 8.8.8.8   # (admin) public DNS
Set-DnsClientServerAddress -InterfaceAlias 'Wi-Fi' -ResetServerAddresses               # (admin) back to automatic
netsh winsock reset ; netsh int ip reset                 # (admin, needs a reboot) last resort for a broken stack
# Nuclear option, reinstalls all adapters: Settings > Network > Advanced > Network reset (ms-settings:network-advancedsettings)
```

Also check for a VPN or proxy that's still set: `Get-VpnConnection`, and the proxy section below.

## Wi-Fi

```powershell
netsh wlan show networks mode=bssid                     # visible networks, signal, channel, security
netsh wlan show profiles                                # saved networks
netsh wlan show profile name="HomeWiFi" key=clear       # saved password is on the "Key Content" line (user's own network)
netsh wlan connect name="HomeWiFi"
netsh wlan disconnect
netsh wlan delete profile name="OldCafe"
netsh wlan show wlanreport                              # (admin) HTML report of drops and errors over 3 days
```

**Drops and slow Wi-Fi:** read `netsh wlan show interfaces` for signal (under ~60% is weak),
radio type and band (2.4 GHz is slower and crowded; 5/6 GHz is faster but shorter range).
Then run `wlanreport` for disconnect reasons. Adapter power saving is a common culprit:
`Get-NetAdapterPowerManagement -Name 'Wi-Fi'`. The Device Manager option "allow the computer
to turn off this device" corresponds to `AllowComputerToTurnOffDevice`.

## Ports and connections

```powershell
Get-NetTCPConnection -State Listen | Sort-Object LocalPort | Select-Object LocalAddress, LocalPort,
  @{n='Process';e={(Get-Process -Id $_.OwningProcess).ProcessName}}          # what's listening
Get-NetTCPConnection -State Established | Select-Object RemoteAddress, RemotePort,
  @{n='Process';e={(Get-Process -Id $_.OwningProcess).ProcessName}}          # who this PC is talking to
netstat -ano | findstr :3000                                                 # classic
```

## Firewall

```powershell
Get-NetFirewallProfile | Select-Object Name, Enabled, DefaultInboundAction
Get-NetFirewallRule -Enabled True -Direction Inbound | Where-Object DisplayName -like '*python*'
# Allow one port inbound (admin); scope it as narrowly as the user's need allows:
New-NetFirewallRule -DisplayName 'Dev server 8080 (LAN)' -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow -Profile Private -RemoteAddress LocalSubnet
New-NetFirewallRule -DisplayName 'Block app outbound' -Direction Outbound -Program 'C:\path\app.exe' -Action Block
Remove-NetFirewallRule -DisplayName 'Dev server 8080 (LAN)'
Set-NetConnectionProfile -InterfaceAlias 'Wi-Fi' -NetworkCategory Private   # home network (makes Private rules apply)
```

Open ports for the **Private** profile, not Public, unless the user explicitly needs Public.
Don't disable the firewall to "make it work". Add the specific rule instead.

## Hosts file (block or redirect a domain)

```powershell
$hosts = "$env:WINDIR\System32\drivers\etc\hosts"
Get-Content $hosts
Add-Content $hosts "`n0.0.0.0 distracting-site.com`n0.0.0.0 www.distracting-site.com"   # admin
ipconfig /flushdns
```

Browsers with DNS-over-HTTPS turned on (Chrome, Edge, Firefox "Secure DNS") can bypass the
hosts file. Mention that if a block "doesn't work".

## Proxy

```powershell
Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' | Select-Object ProxyEnable, ProxyServer, AutoConfigURL
netsh winhttp show proxy                               # the system (service) proxy is separate
Set-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' -Name ProxyEnable -Value 0   # turn off the user proxy
```

## Network drives and sharing

```powershell
New-PSDrive -Name Z -PSProvider FileSystem -Root \\nas\media -Persist   # map (shows in Explorer)
net use Z: \\nas\media /persistent:yes ; net use ; net use Z: /delete
Get-SmbShare                                                          # this PC's shares
New-SmbShare -Name Drop -Path C:\Drop -ChangeAccess "$env:USERNAME"   # (admin) share a folder
Get-SmbConnection                                                     # open connections to other PCs
```

## Speed test and LAN discovery

```powershell
winget install Ookla.Speedtest.CLI ; speedtest --accept-license      # real speed test
arp -a                                                               # devices this PC has talked to recently
Get-NetNeighbor -AddressFamily IPv4 | Where-Object State -ne 'Unreachable'
# Ping sweep of the user's own /24 (PowerShell 7, parallel, about 5 s):
1..254 | ForEach-Object -Parallel { if (Test-Connection "192.168.1.$_" -Count 1 -TimeoutSeconds 1 -Quiet) { "192.168.1.$_" } } -ThrottleLimit 64
```

Only scan networks the user owns. Don't port-scan other people's hosts.

## Remote access to this PC

- **Remote Desktop** (Pro and above): `Start-Process ms-settings:remotedesktop`.
- **SSH server:** see `dev-tools.md`.
- For simple phone-to-PC access, suggest Tailscale (`winget install tailscale.tailscale`)
  rather than opening ports on the router.
