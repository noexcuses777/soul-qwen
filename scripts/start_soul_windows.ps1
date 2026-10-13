param(
    [ValidateSet('qwen','mock')][string]$Mode='qwen',
    [string]$ModelPath,
    [string]$Server,
    [string]$Python,
    [string]$SessionDb,
    [int]$Port=8000,
    [int]$Context=8192,
    [int]$GpuLayers=99,
    [int]$Threads=6
)
$ErrorActionPreference='Stop'
$taskRoot=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (!$Python) { $Python=Join-Path $taskRoot '.venv/Scripts/python.exe' }
$taskPython=(Resolve-Path -LiteralPath $Python).Path
if (!$SessionDb) { $SessionDb=Join-Path $taskRoot 'data/sessions.sqlite3' }
$taskNode=(Get-Command node -ErrorAction Stop).Source
if (!(Test-Path -LiteralPath (Join-Path $taskRoot '.next/BUILD_ID'))) { throw 'Run npm ci --ignore-scripts and npm run build first.' }
foreach ($taskPort in @(8001,$Port)) {
    if (Get-NetTCPConnection -LocalPort $taskPort -State Listen -ErrorAction SilentlyContinue) {
        throw "Port $taskPort is already in use. Keep the existing service intact; select another frontend port or stop its known launcher first."
    }
}
$taskLogs=Join-Path $taskRoot 'runtime'
New-Item -ItemType Directory -Force -Path $taskLogs | Out-Null
$ownedModel=$null; $ownedApi=$null
try {
    $env:LLM_MODE=$Mode
    $env:SESSION_DB=$SessionDb
    $env:SOUL_API_ORIGIN='http://127.0.0.1:8001'
    $env:LLM_BASE_URL='http://127.0.0.1:8080/v1'
    $env:LLM_MODEL='persona-qwen'
    $env:CONTEXT_SIZE="$Context"
    if ($Mode -eq 'qwen') {
        if (!$ModelPath -or !$Server) { throw 'Qwen mode requires -ModelPath /path/Qwen*.gguf and -Server /path/llama-server.exe.' }
        $taskModel=(Resolve-Path -LiteralPath $ModelPath).Path
        $taskServer=(Resolve-Path -LiteralPath $Server).Path
        if ([IO.Path]::GetFileName($taskModel) -notmatch '(?i)qwen.*\.gguf$') { throw 'Select the existing Qwen GGUF model explicitly.' }
        $taskReady=$false
        try { $taskReady=(Invoke-RestMethod 'http://127.0.0.1:8080/health' -TimeoutSec 2).status -eq 'ok' } catch {}
        if (!$taskReady) {
            $taskArgs=@('-m',('"'+$taskModel+'"'),'--alias','persona-qwen','--host','127.0.0.1','--port','8080','-c',"$Context",'-np','1','-ngl',"$GpuLayers",'-t',"$Threads",'-b','256','-ub','128','--jinja','--reasoning','off')
            $ownedModel=Start-Process -FilePath $taskServer -ArgumentList $taskArgs -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $taskLogs 'qwen.stdout.log') -RedirectStandardError (Join-Path $taskLogs 'qwen.stderr.log')
            for ($taskI=0; $taskI -lt 180; $taskI++) {
                if ($ownedModel.HasExited) { throw 'Qwen server exited. Check runtime/qwen.stderr.log.' }
                try { if ((Invoke-RestMethod 'http://127.0.0.1:8080/health' -TimeoutSec 2).status -eq 'ok') { $taskReady=$true; break } } catch {}
                Start-Sleep -Seconds 1
            }
        }
        if (!$taskReady) { throw 'Qwen server is not ready.' }
        $taskProps=Invoke-RestMethod 'http://127.0.0.1:8080/props' -TimeoutSec 10
        if (!$taskProps.model_path -or [IO.Path]::GetFullPath($taskProps.model_path) -ne $taskModel) { throw 'Port 8080 does not contain the explicitly selected Qwen model. No other model is used.' }
        $taskActual=[int]$taskProps.default_generation_settings.n_ctx
        if ($taskActual -gt 0) { $env:CONTEXT_SIZE="$( [Math]::Min($Context,$taskActual) )" }
    }
    $ownedApi=Start-Process -FilePath $taskPython -ArgumentList @('-X','utf8','-m','uvicorn','backend.app:app','--host','127.0.0.1','--port','8001') -WorkingDirectory $taskRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $taskLogs 'api.stdout.log') -RedirectStandardError (Join-Path $taskLogs 'api.stderr.log')
    $taskApiReady=$false
    for ($taskI=0; $taskI -lt 40; $taskI++) {
        if ($ownedApi.HasExited) { throw 'Backend exited. Check runtime/api.stderr.log.' }
        try {
            $taskHealth=Invoke-RestMethod 'http://127.0.0.1:8001/api/health' -TimeoutSec 3
            if ($taskHealth.mode -eq $Mode -and $taskHealth.status -eq 'ok') { $taskApiReady=$true; break }
        } catch {}
        Start-Sleep -Seconds 1
    }
    if (!$taskApiReady) { throw 'SOUL backend did not become ready.' }
    Write-Output "SOUL: http://127.0.0.1:$Port ($Mode mode)"
    Push-Location -LiteralPath $taskRoot
    try { & $taskNode 'node_modules/next/dist/bin/next' start --hostname 127.0.0.1 --port $Port } finally { Pop-Location }
} finally {
    if ($ownedApi -and !$ownedApi.HasExited) { Stop-Process -Id $ownedApi.Id }
    if ($ownedModel -and !$ownedModel.HasExited) { Stop-Process -Id $ownedModel.Id }
}
