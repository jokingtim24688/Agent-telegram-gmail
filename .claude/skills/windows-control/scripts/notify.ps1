<#
.SYNOPSIS
  Show a Windows notification.
.DESCRIPTION
  Real toast notifications need the WinRT APIs in Windows PowerShell 5.1. When run from
  PowerShell 7 this script relaunches itself under powershell.exe. If toasts are blocked
  (Focus Assist, or notifications turned off for PowerShell), it falls back to a tray balloon.
.EXAMPLE
  notify.ps1 -Title "Backup done" -Message "412 files copied to D:\Backup"
  notify.ps1 -Title "Reminder" -Message "Stand up and stretch" -Silent
#>
param(
    [Parameter(Mandatory)][string]$Title,
    [string]$Message = '',
    [switch]$Silent
)

if ($PSVersionTable.PSEdition -eq 'Core') {
    $argList = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $PSCommandPath, '-Title', $Title, '-Message', $Message)
    if ($Silent) { $argList += '-Silent' }
    & powershell.exe @argList
    return
}

$esc = { param($s) [Security.SecurityElement]::Escape($s) }
$audio = if ($Silent) { '<audio silent="true"/>' } else { '' }
$xmlText = "<toast><visual><binding template=`"ToastGeneric`"><text>$(& $esc $Title)</text><text>$(& $esc $Message)</text></binding></visual>$audio</toast>"

try {
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
    $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
    $xml.LoadXml($xmlText)
    # PowerShell's own app id: registered on every Windows install, so the toast is allowed.
    $appId = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show(
        [Windows.UI.Notifications.ToastNotification]::new($xml))
    'toast shown'
} catch {
    Add-Type -AssemblyName System.Windows.Forms, System.Drawing
    $icon = New-Object System.Windows.Forms.NotifyIcon
    $icon.Icon = [System.Drawing.SystemIcons]::Information
    $icon.BalloonTipTitle = $Title
    $icon.BalloonTipText = if ($Message) { $Message } else { ' ' }
    $icon.Visible = $true
    $icon.ShowBalloonTip(8000)
    Start-Sleep -Seconds 8   # the balloon disappears when the icon is disposed
    $icon.Dispose()
    "balloon shown (toast failed: $($_.Exception.Message))"
}
