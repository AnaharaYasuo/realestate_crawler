# Antigravity Quota Bypass Loop Script
# Periodically triggers the agent by resuming the specified conversation session.

$ConversationID = "a24cc9ed-e6b8-42ab-afa4-49b7d13a7731"
$IntervalSeconds = 18000

# Resolve script directory to load instruction file
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrEmpty($ScriptDir)) {
    $ScriptDir = "."
}
$InstructionPath = Join-Path $ScriptDir "antigravity_instruction.txt"

Write-Host "========================================="
Write-Host "Antigravity Auto-Run Loop Started."
Write-Host "Conversation ID: $ConversationID"
Write-Host "Interval: $IntervalSeconds seconds (5 hours)"
Write-Host "Instruction Path: $InstructionPath"
Write-Host "========================================="

while ($true) {
    if (Test-Path $InstructionPath) {
        # Read the latest instruction from text file (avoids PS encoding syntax issues)
        $Instruction = Get-Content -Raw -Path $InstructionPath -Encoding UTF8
    } else {
        $Instruction = "Please continue the development based on the design documents in this repository."
    }

    Write-Host "[$(Get-Date)] Sending instruction to Antigravity..."
    Write-Host "Prompt: $Instruction"

    # Try running with Gemini 3.5 first
    Write-Host "[$(Get-Date)] Trying Gemini 3.5 (gemini-3.5-flash-medium)..."
    agy --conversation $ConversationID --model gemini-3.5-flash-medium --dangerously-skip-permissions -p "$Instruction"

    # Check exit code to handle quota exhaustion or other errors
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "[$(Get-Date)] Gemini 3.5 execution failed (likely quota limit reached)."
        Write-Warning "[$(Get-Date)] Falling back to Claude 3.5 (claude-3.5-sonnet)..."
        
        agy --conversation $ConversationID --model claude-3.5-sonnet --dangerously-skip-permissions -p "$Instruction"
        
        if ($LASTEXITCODE -ne 0) {
            Write-Error "[$(Get-Date)] Fallback to Claude 3.5 also failed."
        }
    }

    Write-Host "[$(Get-Date)] Completed. Sleeping for $IntervalSeconds seconds..."
    Start-Sleep -Seconds $IntervalSeconds
}
