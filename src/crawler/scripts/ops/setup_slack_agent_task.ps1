# PowerShell script to install Slack Agent as a persistent Windows Scheduled Task
$TaskName = "RealEstateCrawler_SlackAgent"
$ScriptPath = "c:\Users\weare\Documents\realestate_crawler\src\crawler\scripts\slack_agent_host.js"
$WorkingDir = "c:\Users\weare\Documents\realestate_crawler"
$NodePath = (Get-Command node).Source

Write-Host "Registering Windows Scheduled Task: $TaskName..."

# タスク起動用 VBScript (コンソールウィンドウ非表示で完全バックグラウンド常駐)
$VbsPath = "c:\Users\weare\Documents\realestate_crawler\src\crawler\scripts\run_slack_agent_background.vbs"
$VbsContent = @"
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "$WorkingDir"
WshShell.Run """$NodePath"" ""$ScriptPath""", 0, False
"@

Set-Content -Path $VbsPath -Value $VbsContent -Encoding UTF8
Write-Host "Created background VBS wrapper at: $VbsPath"

# Windows タスクスケジューラの登録 (ユーザーログオン時に自動起動、無制限実行)
$Action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$VbsPath`""
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Days 365) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

# 既存タスクがあれば削除して再登録
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "24/7 Slack Listener for Real Estate Crawler Antigravity Agent"

Write-Host "SUCCESS: $TaskName registered as Windows Scheduled Task."
