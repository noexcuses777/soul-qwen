param(
    [Parameter(Mandatory=$true)][string]$ModelPath,
    [Parameter(Mandatory=$true)][string]$Server,
    [int]$GpuLayers=99,
    [int]$Context=8192,
    [int]$Threads=6
)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$model=(Resolve-Path -LiteralPath $ModelPath).Path
$serverExe=(Resolve-Path -LiteralPath $Server).Path
$python=Join-Path $root '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $python)) { throw 'Create .venv and install requirements first.' }

$ownedModel=$null
try {
    $ready=$false
    try {
        $health=Invoke-RestMethod -Uri 'http://127.0.0.1:8080/health' -TimeoutSec 2
        $ready=$health.status -eq 'ok'
    } catch {}
    if (!$ready) {
        $runtime=Join-Path $root 'runtime'
        New-Item -ItemType Directory -Force $runtime | Out-Null
        $args=@('-m',$model,'--alias','persona-qwen','--host','127.0.0.1','--port','8080','-c',"$Context",'-np','1','-ngl',"$GpuLayers",'-t',"$Threads",'-b','256','-ub','128','--jinja','--reasoning','off')
        $ownedModel=Start-Process -FilePath $serverExe -ArgumentList $args -PassThru -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtime 'llama.stdout.log') -RedirectStandardError (Join-Path $runtime 'llama.stderr.log')
        for ($i=0; $i -lt 180; $i++) {
            if ($ownedModel.HasExited) { throw 'llama-server exited while loading. Check runtime/llama.stderr.log.' }
            try {
                $health=Invoke-RestMethod -Uri 'http://127.0.0.1:8080/health' -TimeoutSec 2
                if ($health.status -eq 'ok') { $ready=$true; break }
            } catch {}
            Start-Sleep -Seconds 1
        }
    }
    if (!$ready) { throw 'Qwen model server did not become ready within 180 seconds.' }
    $props=Invoke-RestMethod -Uri 'http://127.0.0.1:8080/props' -TimeoutSec 10
    if ($props.model_path -and [System.IO.Path]::GetFullPath($props.model_path) -ne $model) {
        throw "Port 8080 is running a different model: $($props.model_path). Stop that model server before selecting $model."
    }
    $env:LLM_MODE='qwen'
    $env:LLM_BASE_URL='http://127.0.0.1:8080/v1'
    $env:LLM_MODEL='persona-qwen'
    $actualContext=[int]$props.default_generation_settings.n_ctx
    $env:CONTEXT_SIZE="$(if($actualContext -gt 0){[math]::Min($Context,$actualContext)}else{$Context})"
    Set-Location -LiteralPath $root
    Write-Output 'Persona Studio: http://127.0.0.1:8000'
    & $python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
} finally {
    if ($ownedModel -and !$ownedModel.HasExited) { Stop-Process -Id $ownedModel.Id }
}
