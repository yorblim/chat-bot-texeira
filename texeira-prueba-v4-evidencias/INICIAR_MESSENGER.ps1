$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:ANONYMIZED_TELEMETRY = 'False'
$env:TEXEIRA_ENABLE_MESSENGER = 'true'
try {
    & 'C:\Users\HP\AppData\Local\Programs\Python\Python311\python.exe' -m uvicorn whatsapp_entry:app --host 127.0.0.1 --port 8022
} finally {
    Remove-Item Env:TEXEIRA_ENABLE_MESSENGER -ErrorAction SilentlyContinue
}
