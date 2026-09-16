# Install Slack Agent into Windows User Startup Folder (No Admin Required)
$StartupDir = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"
$WorkingDir = "c:\Users\weare\Documents\realestate_crawler"
$ScriptPath = "c:\Users\weare\Documents\realestate_crawler\src\crawler\scripts\slack_agent_host.js"
$NodePath = (Get-Command node).Source

# 1. コンソール非表示バックグラウンド起動用 VBScript
$VbsPath = "$WorkingDir\src\crawler\scripts\run_slack_agent_background.vbs"
$VbsContent = @"
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "$WorkingDir"
WshShell.Run """$NodePath"" ""$ScriptPath""", 0, False
"@

Set-Content -Path $VbsPath -Value $VbsContent -Encoding UTF8
Write-Host "Created VBScript wrapper at: $VbsPath"

# 2. スタートアップフォルダに VBScript へのショートカット (.lnk) を作成
$WshShell = New-Object -ComObject WScript.Shell
$ShortcutPath = "$StartupDir\RealEstateCrawler_SlackAgent.lnk"
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "wscript.exe"
$Shortcut.Arguments = "`"$VbsPath`""
$Shortcut.WorkingDirectory = $WorkingDir
$Shortcut.Description = "24/7 Slack Listener Agent for RealEstate Crawler"
$Shortcut.Save()

Write-Host "SUCCESS: Slack Agent auto-start shortcut installed into Windows Startup folder:"
Write-Host "  Path: $ShortcutPath"
