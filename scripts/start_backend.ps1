param([ValidateSet('mock','qwen')][string]$Mode='mock')
$ErrorActionPreference='Stop'
Set-Location -LiteralPath (Split-Path $PSScriptRoot -Parent)
$env:LLM_MODE=$Mode
& ./.venv/Scripts/python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
