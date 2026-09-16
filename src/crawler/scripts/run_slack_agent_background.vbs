' Perpetual Watchdog Runner for Slack Agent
Set WshShell = CreateObject("WScript.Shell")
WorkingDir = "c:\Users\weare\Documents\realestate_crawler"
NodePath = "C:\Program Files\nodejs\node.exe"
ScriptPath = "c:\Users\weare\Documents\realestate_crawler\src\crawler\scripts\slack_agent_host.js"

WshShell.CurrentDirectory = WorkingDir

' Watchdog Loop
Do
    ReturnCode = WshShell.Run("""" & NodePath & """ """ & ScriptPath & """", 0, True)
    WScript.Sleep 2000
Loop
