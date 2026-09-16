$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
& 'C:\Users\HP\AppData\Local\Programs\Python\Python311\python.exe' -m uvicorn advisor_entry:app --host 127.0.0.1 --port 8023
