$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:ANONYMIZED_TELEMETRY = 'False'
& 'C:\Users\HP\AppData\Local\Programs\Python\Python311\python.exe' -m uvicorn app:app --host 127.0.0.1 --port 8021
