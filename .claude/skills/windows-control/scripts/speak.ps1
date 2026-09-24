<#
.SYNOPSIS
  Read text aloud with the built-in Windows voices (SAPI), or save it as a WAV file.
.EXAMPLE
  speak.ps1 "Your download is finished"
  speak.ps1 "Faster please" -Rate 3            (-10 slowest .. 10 fastest)
  speak.ps1 -ListVoices
  speak.ps1 "Hello" -Voice "*Zira*"
  speak.ps1 "Meeting in five minutes" -OutFile C:\temp\reminder.wav
.NOTES
  More natural voices: Settings > Time & language > Speech > Manage voices. Some of those
  only appear to SAPI after installing, and the Narrator-only "natural" voices never do.
#>
param(
    [Parameter(Position = 0)][string]$Text,
    [ValidateRange(-10, 10)][int]$Rate = 0,
    [ValidateRange(0, 100)][int]$Volume = 100,
    [string]$Voice,
    [string]$OutFile,
    [switch]$ListVoices
)
$ErrorActionPreference = 'Stop'
$sapi = New-Object -ComObject SAPI.SpVoice

$voices = @(foreach ($v in $sapi.GetVoices()) { $v })
if ($ListVoices) {
    $voices | ForEach-Object { $_.GetDescription() }
    return
}
if (-not $Text) { throw 'Give the text to speak.' }
if ($Voice) {
    $pick = $voices | Where-Object { $_.GetDescription() -like $Voice } | Select-Object -First 1
    if (-not $pick) { throw "No voice like '$Voice'. Run with -ListVoices." }
    $sapi.Voice = $pick
}
$sapi.Rate = $Rate
$sapi.Volume = $Volume

if ($OutFile) {
    $stream = New-Object -ComObject SAPI.SpFileStream
    $stream.Open($OutFile, 3 <# SSFMCreateForWrite #>)
    $sapi.AudioOutputStream = $stream
    [void]$sapi.Speak($Text)
    $stream.Close()
    "saved $OutFile"
} else {
    [void]$sapi.Speak($Text)
    'spoken'
}
