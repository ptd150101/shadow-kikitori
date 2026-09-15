$ErrorActionPreference = "Stop"
$api = Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/health"
if ($api.status -ne "ok") { throw "API health check failed" }
Write-Output "API: ok"
Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/system/capabilities" | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/models/status" | ConvertTo-Json
