$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\apps\api")
uv sync --locked
uv run python -m jlpt_studio.jobs.worker
