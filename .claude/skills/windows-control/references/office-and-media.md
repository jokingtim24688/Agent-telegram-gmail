# Office, printing and media

## Office automation through COM (desktop Office only)

COM drives the installed Office apps the way a person would, so they have to be installed,
and only the classic desktop versions work. The **new Outlook** (olk.exe) and Office on the
web have no COM. For creating or editing files without Office installed, prefer the docx,
xlsx, pptx and pdf skills.

Always quit and release COM objects in `finally`, or a hidden `EXCEL.EXE` stays running and
keeps the file locked.

### Excel

```powershell
$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false; $xl.DisplayAlerts = $false
try {
  $wb = $xl.Workbooks.Open('C:\data\sales.xlsx')
  $ws = $wb.Worksheets.Item('Sheet1')
  $ws.Range('A1').Value2                                   # read one cell
  $data = $ws.UsedRange.Value2                             # 2-D array (1-based)
  $ws.Range('E1').Value2 = 'Margin'
  $ws.Range('E2:E100').Formula = '=IFERROR((C2-D2)/C2,"")' # relative formula filled down
  $wb.RefreshAll()                                         # refresh pivots / queries
  $wb.Save()                                               # or $wb.SaveAs('C:\out.xlsx', 51)  51 = xlsx, 6 = csv
  $wb.ExportAsFixedFormat(0, 'C:\out.pdf')                 # 0 = PDF
  $wb.Close($false)
} finally {
  $xl.Quit(); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($xl); [GC]::Collect()
}
# Run a macro: $xl.Run('MacroName')
```

Plain CSV needs no Office: `Import-Csv file.csv | Where-Object ... | Export-Csv out.csv -NoTypeInformation -Encoding utf8`.

### Word

```powershell
$word = New-Object -ComObject Word.Application; $word.Visible = $false
try {
  $doc = $word.Documents.Open('C:\docs\letter.docx')
  $doc.Content.Find.Execute('[NAME]', $false, $false, $false, $false, $false, $true, 1, $false, 'Alex', 2) | Out-Null   # replace all
  $doc.SaveAs2('C:\docs\letter-alex.pdf', 17)             # 17 = PDF; 16 = docx
  $doc.Close($false)
} finally { $word.Quit(); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($word) }
```

Converting a folder of `.docx` to PDF means looping over `Get-ChildItem *.docx` with the same
calls. PowerPoint: `$ppt = New-Object -ComObject PowerPoint.Application; $p = $ppt.Presentations.Open($f, $true, $false, $false); $p.SaveAs($out, 32); $p.Close()`
(32 = PDF).

### Outlook (classic)

```powershell
$ol = New-Object -ComObject Outlook.Application
$inbox = $ol.GetNamespace('MAPI').GetDefaultFolder(6)          # 6 = Inbox
$inbox.Items.Restrict('[Unread] = true') | Select-Object -First 10 ReceivedTime, SenderName, Subject
# Sending: build the mail, then .Display() so the user reviews and clicks Send. Use .Send() only when they asked for that.
$m = $ol.CreateItem(0); $m.To = 'someone@example.com'; $m.Subject = 'Report'; $m.Body = 'Attached.'; $m.Attachments.Add('C:\out.pdf'); $m.Display()
```

Sending email is outward-facing and can't be undone, so show the draft first (`.Display()`)
unless the user explicitly asked for a silent send.

## Printing

```powershell
Get-Printer | Select-Object Name, DriverName, PortName, PrinterStatus, Shared
(Get-CimInstance Win32_Printer -Filter 'Default=TRUE').Name
Invoke-CimMethod -InputObject (Get-CimInstance Win32_Printer -Filter "Name='HP LaserJet'") -MethodName SetDefaultPrinter
Start-Process -FilePath 'C:\docs\file.pdf' -Verb Print      # prints with the file's default app and default printer
Get-Content notes.txt | Out-Printer -Name 'HP LaserJet'
Get-PrintJob -PrinterName 'HP LaserJet' ; Get-PrintJob -PrinterName 'HP LaserJet' | Remove-PrintJob
```

"Microsoft Print to PDF" is a printer too, so anything printable can become a PDF.

**Stuck print queue** (admin):

```powershell
Stop-Service Spooler -Force
Remove-Item "$env:WINDIR\System32\spool\PRINTERS\*" -Force
Start-Service Spooler
```

Also: Windows 11 disables automatic default-printer management through
`HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Windows` → `LegacyDefaultPrinterMode` = 1.
If the default printer keeps changing, set that value.

## PDFs

For merging, splitting, extracting text, OCR, filling forms or watermarks, use the **pdf**
skill. Quick CLI options on Windows: `winget install qpdf.qpdf`
(`qpdf --empty --pages a.pdf b.pdf -- merged.pdf`) and `winget install ArtifexSoftware.GhostScript`
(compression).

## Images

```powershell
winget install ImageMagick.ImageMagick
magick input.heic output.jpg                                   # convert (HEIC from iPhones too)
magick mogrify -resize 1920x1920> -quality 85 -path .\small *.jpg   # batch shrink, keeping aspect ratio
```

Without installing anything, `System.Drawing` can resize and convert JPG, PNG and BMP (not HEIC or WebP).

## Audio and video (ffmpeg)

```powershell
winget install Gyan.FFmpeg                                     # restart the terminal for PATH
ffmpeg -i in.mov -c:v libx264 -crf 23 -c:a aac out.mp4         # convert / shrink video
ffmpeg -i in.mp4 -vn -c:a libmp3lame -q:a 2 out.mp3            # extract audio
ffmpeg -ss 00:01:30 -to 00:02:10 -i in.mp4 -c copy clip.mp4    # cut without re-encoding
ffmpeg -i in.mp4 -vf "fps=10,scale=640:-1" out.gif             # GIF
ffmpeg -f gdigrab -framerate 30 -i desktop -t 60 screen.mp4    # record the screen for 60 s
ffmpeg -list_devices true -f dshow -i dummy                    # cameras and microphones by name
ffprobe -hide_banner in.mp4                                    # what's in a file
```

For NVIDIA hardware encoding, which is much faster, use `-c:v h264_nvenc -cq 23`.

Built-in capture: Snipping Tool (`Start-Process ms-screenclip:` or Win+Shift+S; it records
video on Windows 11), Xbox Game Bar (Win+Alt+R), the Camera app (`Start-Process microsoft.windows.camera:`),
and Sound Recorder (search Start for "Sound Recorder").
