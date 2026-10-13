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
$logDir=Join-Path $root 'examples'
New-Item -ItemType Directory -Force $logDir | Out-Null
$stdout=Join-Path $logDir 'llama-server.stdout.log'
$stderr=Join-Path $logDir 'llama-server.stderr.log'
$serverArgs=@('-m',$model,'--alias','persona-qwen','--host','127.0.0.1','--port','8080','-c',"$Context",'-np','1','-ngl',"$GpuLayers",'-t',"$Threads",'-b','256','-ub','128','--jinja','--reasoning','off')
$process=Start-Process -FilePath $serverExe -ArgumentList $serverArgs -PassThru -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr
try {
    $ready=$false
    for ($i=0; $i -lt 180; $i++) {
        if ($process.HasExited) { throw "llama-server exited early. See $stderr" }
        try {
            $health=Invoke-RestMethod -Uri 'http://127.0.0.1:8080/health' -TimeoutSec 2
            if ($health.status -eq 'ok') { $ready=$true; break }
        } catch {}
        Start-Sleep -Seconds 1
    }
    if (!$ready) { throw 'llama-server was not ready in 180 seconds.' }
    $sha=(Get-FileHash -LiteralPath $model -Algorithm SHA256).Hash.ToLowerInvariant()
    & $python (Join-Path $root 'scripts\qwen_smoke.py') --server-exe $serverExe --model-path $model --model-sha256 $sha --context $Context
    if ($LASTEXITCODE -ne 0) { throw 'Qwen E2E failed.' }
} finally {
    if (!$process.HasExited) { Stop-Process -Id $process.Id }
}
