# Presentation launcher — opens one PowerShell window per step so each can be inspected.
#
# Usage:
#   .\scripts\presentation_launch.ps1                 # defaults to model=bist-qwen
#   .\scripts\presentation_launch.ps1 -Model qwen2.5:7b-instruct
#   .\scripts\presentation_launch.ps1 -SkipHarness    # don't auto-start the 15-min harness

param(
    [string]$Model = "bist-qwen",
    [switch]$SkipHarness
)

$ErrorActionPreference = "Stop"

# Resolve repo root (parent of this script's directory) so the launcher works from anywhere.
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python   = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    Write-Host "ERROR: venv python not found at $Python" -ForegroundColor Red
    Write-Host "Run docs/LOCAL_SETUP.md section 1 first." -ForegroundColor Red
    exit 1
}

function Start-Step {
    param(
        [string]$Title,
        [string]$Command,
        [string]$Color = "Cyan"
    )
    # Build an inline command that:
    #   - sets a readable window title
    #   - cd's to the repo root
    #   - prints a banner
    #   - runs the command
    #   - keeps the window open so you can inspect output
    $banner = "Write-Host '=== $Title ===' -ForegroundColor $Color"
    $inner  = "`$Host.UI.RawUI.WindowTitle = '$Title'; Set-Location '$RepoRoot'; $banner; $Command"
    Start-Process powershell -ArgumentList "-NoExit", "-NoProfile", "-Command", $inner | Out-Null
}

Write-Host "Repo root : $RepoRoot"
Write-Host "Python    : $Python"
Write-Host "Model     : $Model"
Write-Host ""

# ---- Step 1: Ollama server ---------------------------------------------------
# Detect an already-running Ollama so we don't spawn a window that immediately errors
# with "bind: address already in use".
$ollamaAlreadyUp = $false
try {
    $probe = New-Object System.Net.Sockets.TcpClient
    $probe.Connect("127.0.0.1", 11434)
    $probe.Close()
    $ollamaAlreadyUp = $true
} catch { }

if ($ollamaAlreadyUp) {
    Write-Host "Ollama already listening on 11434 - skipping serve window." -ForegroundColor Yellow
} else {
    $serveBanner = @"
Write-Host 'This window runs the Ollama inference server for the local LLM stack.' -ForegroundColor DarkGray;
Write-Host 'Expect: "Listening on 127.0.0.1:11434" within a few seconds.' -ForegroundColor DarkGray;
Write-Host 'Leave open for the rest of the demo. Ctrl+C to stop.' -ForegroundColor DarkGray;
Write-Host '';
ollama serve
"@
    Start-Step -Title "1/4 ollama serve" -Color "Yellow" -Command $serveBanner
}

# Wait for port 11434 to accept connections so downstream steps don't race.
Write-Host "Waiting for Ollama on 127.0.0.1:11434 ..."
$deadline = (Get-Date).AddSeconds(30)
while ((Get-Date) -lt $deadline) {
    try {
        $c = New-Object System.Net.Sockets.TcpClient
        $c.Connect("127.0.0.1", 11434)
        $c.Close()
        Write-Host "Ollama is up." -ForegroundColor Green
        break
    } catch {
        Start-Sleep -Milliseconds 500
    }
}

# ---- Step 2: health check (models + port) -----------------------------------
$healthCmd = @"
Write-Host 'Pre-flight check before the harness run:' -ForegroundColor DarkGray;
Write-Host '  - installed Ollama models'              -ForegroundColor DarkGray;
Write-Host '  - required model ($Model) is present'   -ForegroundColor DarkGray;
Write-Host '  - something is actually listening on 11434' -ForegroundColor DarkGray;
Write-Host '';
Write-Host 'Installed models:' -ForegroundColor Cyan;
ollama list;
Write-Host '';
Write-Host 'Checking required model: $Model' -ForegroundColor Cyan;
if ((ollama list) -match '$Model') { Write-Host 'OK: model present' -ForegroundColor Green }
else { Write-Host 'MISSING: run `ollama create $Model -f training/Modelfile.finetuned`' -ForegroundColor Red };
Write-Host '';
Write-Host 'Localhost sockets on 11434:' -ForegroundColor Cyan;
netstat -an | Select-String ':11434';
Write-Host '';
Write-Host 'Health check complete. Safe to close this window once reviewed.' -ForegroundColor DarkGray
"@
Start-Step -Title "2/4 health check" -Color "Cyan" -Command $healthCmd

# ---- Step 3: local agent smoke test -----------------------------------------
$smokeBanner = @"
Write-Host 'Smoke test: spin up the MCP server as a child process and ask the local' -ForegroundColor DarkGray;
Write-Host 'LLM one scripted question against THYAO. Validates the full tool-calling' -ForegroundColor DarkGray;
Write-Host 'loop (model -> MCP -> cached data -> response) end-to-end.' -ForegroundColor DarkGray;
Write-Host 'Expect: ~30-60 s of tool-call log lines, then a short JSON answer.' -ForegroundColor DarkGray;
Write-Host 'Artefacts: outputs/agent/local_agent.result.json and .trace.json'    -ForegroundColor DarkGray;
Write-Host '';
& '$Python' scripts\local_agent.py --smoke
"@
Start-Step -Title "3/4 local_agent --smoke" -Color "Magenta" -Command $smokeBanner

# ---- Step 4: 5-stage harness ------------------------------------------------
# The harness runs 5 architecture stages serially and only prints at the very end.
# We watch outputs/harness/{stage}.score.json mtimes to report each completion live.
if (-not $SkipHarness) {
    $harnessCmd = @"
`$ErrorActionPreference = 'Stop';
`$stages = @(
    @{ name = 'raw_llm';               desc = 'LLM alone, no tools: should be weak / mostly null' },
    @{ name = 'llm_tools';             desc = 'LLM + 19 MCP tools: numbers from real data' },
    @{ name = 'stateful_harness';      desc = 'As above + immutable run state (as_of, window)' },
    @{ name = 'evidence_quality_gate'; desc = '+ quality gate: reject if any number is uncited' },
    @{ name = 'memory_human_review';   desc = '+ reviewed project memory for human presentation' }
);
Write-Host 'This runs the 5-stage architecture ablation against a single fixed model.'    -ForegroundColor DarkGray;
Write-Host 'Model : $Model (local, via Ollama - no cloud)'                                 -ForegroundColor DarkGray;
Write-Host 'Output: outputs/harness/{stage}.{json,jsonl,score.json} + comparison.json'     -ForegroundColor DarkGray;
Write-Host 'Expect: ~2-3 minutes per stage, ~10-15 minutes total.'                         -ForegroundColor DarkGray;
Write-Host '';
Write-Host 'Stages (in order):' -ForegroundColor Cyan;
for (`$i = 0; `$i -lt `$stages.Count; `$i++) {
    Write-Host ('  {0}. {1,-24} - {2}' -f (`$i+1), `$stages[`$i].name, `$stages[`$i].desc) -ForegroundColor DarkGray;
}
Write-Host '';

# Snapshot mtimes of any pre-existing score files so we only report NEW completions.
`$outDir = Join-Path '$RepoRoot' 'outputs/harness';
if (-not (Test-Path `$outDir)) { New-Item -ItemType Directory -Path `$outDir | Out-Null }
`$baseline = @{};
foreach (`$s in `$stages) {
    `$f = Join-Path `$outDir ((`$s.name) + '.score.json');
    if (Test-Path `$f) { `$baseline[`$s.name] = (Get-Item `$f).LastWriteTime }
    else { `$baseline[`$s.name] = [datetime]::MinValue };
}

`$startTime = Get-Date;
Write-Host ('Launching harness at ' + `$startTime.ToString('HH:mm:ss') + ' ...') -ForegroundColor Green;
Write-Host '';

# Start the harness as a child process whose stdout/stderr still flow into this window.
`$proc = Start-Process -FilePath '$Python' ``
    -ArgumentList 'scripts\run_harness_experiments.py','--backend','ollama','--model','$Model' ``
    -NoNewWindow -PassThru;

`$seen = @{};
while (-not `$proc.HasExited) {
    foreach (`$s in `$stages) {
        if (`$seen.ContainsKey(`$s.name)) { continue }
        `$f = Join-Path `$outDir ((`$s.name) + '.score.json');
        if ((Test-Path `$f) -and (Get-Item `$f).LastWriteTime -gt `$baseline[`$s.name]) {
            `$elapsed = (Get-Date) - `$startTime;
            `$verdict = '(score unreadable)';
            try {
                `$score = Get-Content `$f -Raw | ConvertFrom-Json;
                `$gate = if (`$score.quality_gate_pass) { 'PASS' } else { 'FAIL' };
                `$verdict = ('gate=' + `$gate);
                if (`$score.PSObject.Properties.Name -contains 'overall_score') {
                    `$verdict = `$verdict + (' overall={0:F2}' -f [double]`$score.overall_score);
                }
            } catch { }
            `$line = ('[t+{0,5:F0}s] stage {1}/{2} {3,-24} done  {4}' -f ``
                `$elapsed.TotalSeconds, (`$seen.Count + 1), `$stages.Count, `$s.name, `$verdict);
            Write-Host `$line -ForegroundColor Green;
            `$seen[`$s.name] = `$true;
        }
    }
    Start-Sleep -Seconds 3;
}

`$total = (Get-Date) - `$startTime;
Write-Host '';
Write-Host ('Harness process exited with code ' + `$proc.ExitCode + ' after ' + ('{0:F0}' -f `$total.TotalSeconds) + 's.') -ForegroundColor Cyan;
`$comparison = Join-Path `$outDir 'comparison.json';
if (Test-Path `$comparison) {
    Write-Host 'Comparison summary:' -ForegroundColor Cyan;
    Get-Content `$comparison -Raw | Write-Host;
}
"@
    Start-Step -Title "4/4 harness ($Model)" -Color "Green" -Command $harnessCmd
} else {
    Write-Host "Skipped harness window (-SkipHarness)." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Launched. Inspect each window; close them manually when done." -ForegroundColor Green
