param([Parameter(Mandatory=$true)][string]$ModelPath,[string]$Server='llama-server.exe',[int]$GpuLayers=99,[int]$Context=8192)
$ErrorActionPreference='Stop'
if (!(Test-Path -LiteralPath $ModelPath)) { throw 'GGUF file not found' }
& $Server -m $ModelPath --alias persona-qwen --host 127.0.0.1 --port 8080 -c $Context -np 1 -ngl $GpuLayers -b 256 -ub 128 --jinja --reasoning off --chat-template-kwargs '{"enable_thinking":false}'
