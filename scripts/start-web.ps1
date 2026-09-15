$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\apps\web")
npm install
npm run dev -- --host 127.0.0.1
