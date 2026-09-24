# Files, folders and search

## Known folders: resolve them, don't guess

OneDrive often redirects Desktop, Documents and Pictures (to `C:\Users\me\OneDrive\Desktop`),
so `$HOME\Desktop` can be the wrong folder. Ask Windows instead:

```powershell
[Environment]::GetFolderPath('Desktop')      # also: MyDocuments, MyPictures, MyMusic, MyVideos, ApplicationData, LocalApplicationData, Startup
(New-Object -ComObject Shell.Application).Namespace('shell:Downloads').Self.Path   # Downloads has no enum value
$env:TEMP; $env:APPDATA; $env:LOCALAPPDATA; $env:ProgramFiles; ${env:ProgramFiles(x86)}; $env:ProgramData
```

## Find files

```powershell
# By name, recursive (the -Filter wildcard runs in the file system and is fast)
Get-ChildItem $HOME -Recurse -Filter '*.pdf' -File -ErrorAction SilentlyContinue |
  Select-Object FullName, Length, LastWriteTime

# Modified in the last 24 hours
Get-ChildItem $HOME\Documents -Recurse -File | Where-Object LastWriteTime -gt (Get-Date).AddDays(-1)

# Containing text (like grep). -List stops after the first hit per file.
Get-ChildItem C:\Projects -Recurse -Include *.py,*.js -File | Select-String -Pattern 'api_key' -List |
  Select-Object Path, LineNumber, Line

# Across the whole machine, using the Windows Search index (fast; indexed places only: user folders by default)
$c = New-Object -ComObject ADODB.Connection
$c.Open("Provider=Search.CollatorDSO;Extended Properties='Application=Windows';")
$rs = $c.Execute("SELECT System.ItemPathDisplay FROM SYSTEMINDEX WHERE System.FileName LIKE '%invoice%'")
while (-not $rs.EOF) { $rs.Fields.Item('System.ItemPathDisplay').Value; $rs.MoveNext() }
```

If the user has **Everything** installed (`winget install voidtools.Everything`), its CLI
`es.exe` finds anything on NTFS drives instantly: `es.exe -n 50 invoice *.pdf`.

## Big files and disk usage

Use `scripts/find-large.ps1` (largest files, or folder sizes with `-Folders`). For a visual
breakdown, suggest `winget install WinDirStat.WinDirStat` or `WizTree` (much faster on NTFS).

## Copy, move, rename

```powershell
Copy-Item 'C:\src\file.txt' 'D:\backup\' ; Copy-Item C:\src D:\dst -Recurse
Move-Item *.jpg (Join-Path ([Environment]::GetFolderPath('MyPictures')) 'Sorted')
Rename-Item 'old.txt' 'new.txt'

# Bulk rename: preview first, then drop -WhatIf
Get-ChildItem *.jpeg | Rename-Item -NewName { $_.BaseName + '.jpg' } -WhatIf
Get-ChildItem IMG_*.jpg | Rename-Item -NewName { 'Holiday_{0:yyyy-MM-dd}_{1}' -f $_.LastWriteTime, $_.Name } -WhatIf
```

**Large or long-running copies and backups: use robocopy.** It retries, resumes, preserves
timestamps and prints a summary:

```powershell
robocopy C:\Users\me\Documents D:\Backup\Documents /E /Z /R:2 /W:5 /MT:16 /XJ /NP /LOG+:D:\Backup\robocopy.log
# /MIR mirrors, which DELETES files in the destination that aren't in the source. Preview with /L first.
```

robocopy's exit codes 0–7 mean success (1 = files copied). 8 or higher means something failed.
Don't treat a nonzero exit code as an error by itself.

## Organize a folder (a common request)

```powershell
# Sort Downloads into subfolders by type. Show the plan first.
$dl = (New-Object -ComObject Shell.Application).Namespace('shell:Downloads').Self.Path
$map = @{ Images='.jpg .jpeg .png .gif .webp .heic'; Documents='.pdf .docx .doc .xlsx .pptx .txt .csv'
          Archives='.zip .rar .7z .tar .gz'; Installers='.exe .msi .msix'; Video='.mp4 .mkv .mov .avi'; Audio='.mp3 .wav .flac .m4a' }
Get-ChildItem $dl -File | ForEach-Object {
  $f = $_; $dest = ($map.GetEnumerator() | Where-Object { $_.Value -split ' ' -contains $f.Extension.ToLower() }).Key
  if ($dest) { [pscustomobject]@{ File = $f.Name; To = $dest } }
}
# After the user agrees: the same loop with New-Item -ItemType Directory -Force + Move-Item
```

## Delete safely: to the Recycle Bin

`Remove-Item` is permanent. Unless the user asks for a permanent delete, send files to the
Recycle Bin so they can be restored:

```powershell
Add-Type -AssemblyName Microsoft.VisualBasic
[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile('C:\path\file.txt', 'OnlyErrorDialogs', 'SendToRecycleBin')
[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory('C:\path\folder', 'OnlyErrorDialogs', 'SendToRecycleBin')

# Empty the Recycle Bin (permanent; confirm first)
Clear-RecycleBin -Force            # all drives;  -DriveLetter C for one drive
```

Delete files by pattern only after showing the list and the count:
`Get-ChildItem ... | Remove-Item -WhatIf`.

## Duplicates

```powershell
Get-ChildItem $HOME\Pictures -Recurse -File | Group-Object Length | Where-Object Count -gt 1 |
  ForEach-Object { $_.Group | Get-FileHash -Algorithm SHA256 } | Group-Object Hash |
  Where-Object Count -gt 1 | ForEach-Object { $_.Group.Path; '---' }
```

Grouping by size first keeps it fast, because only same-size files get hashed.

## Archives

```powershell
Compress-Archive -Path C:\project\* -DestinationPath C:\project.zip        # zip only; files over 2 GB fail on 5.1
Expand-Archive C:\file.zip -DestinationPath C:\out
tar -a -cf out.zip folder ; tar -xf archive.tar.gz -C C:\out               # tar.exe ships with Windows 10+ and also handles .zip
# .7z / .rar: winget install 7zip.7zip, then & "$env:ProgramFiles\7-Zip\7z.exe" x file.rar -oC:\out
```

## Hashes and verifying downloads

```powershell
Get-FileHash C:\Downloads\installer.exe -Algorithm SHA256
(Get-FileHash file.iso).Hash -eq 'EXPECTEDHASH'.ToUpper()
Get-AuthenticodeSignature C:\Downloads\installer.exe | Select-Object Status, SignerCertificate   # who signed an .exe
```

## Attributes, hidden files, "blocked" downloads

```powershell
Get-ChildItem -Force                                   # include hidden and system files
attrib +h secret.txt ; attrib -h -s -r file.txt
Unblock-File C:\Downloads\tool.ps1                      # clears the "downloaded from the internet" mark
Get-ChildItem C:\Downloads -Recurse | Unblock-File
```

## Permissions (icacls)

```powershell
icacls 'C:\Data'                                        # show
icacls 'C:\Data' /grant "${env:USERNAME}:(OI)(CI)M"     # Modify, inherited by subfolders and files. ${} is needed: "$env:USERNAME:" misparses
icacls 'C:\Data' /reset /T                              # back to inherited defaults
takeown /F 'C:\stuck\folder' /R /D Y                    # (admin) take ownership when even admins get "access denied"
```

Take ownership only of the user's own stuck files (an old drive, a leftover folder). Never
touch `C:\Windows` or `WindowsApps`.

## Shortcuts and links

```powershell
$s = (New-Object -ComObject WScript.Shell).CreateShortcut("$([Environment]::GetFolderPath('Desktop'))\Project.lnk")
$s.TargetPath = 'C:\Projects\app'; $s.Save()
(New-Object -ComObject WScript.Shell).CreateShortcut('C:\path\x.lnk').TargetPath   # read a shortcut's target
New-Item -ItemType SymbolicLink -Path C:\link -Target D:\real                        # needs admin or Developer Mode
New-Item -ItemType Junction -Path C:\Games -Target D:\Games                          # directory junction; no admin needed
```

## Open things the way a double-click would

```powershell
Invoke-Item C:\report.pdf           # opens with the default app
explorer.exe /select,"C:\path\file.txt"   # opens Explorer with the file highlighted
Start-Process https://example.com
```

## Long paths

Paths over 260 characters fail in many tools. Prefix with `\\?\` for .NET/PowerShell
(`Get-ChildItem -LiteralPath '\\?\C:\very\long\...'`), use robocopy (it handles them natively),
or enable long paths system-wide (see `dev-tools.md`).
