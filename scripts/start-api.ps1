$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\apps\api")
uv sync --locked
uv run alembic upgrade head
uv run uvicorn jlpt_studio.main:app --host 127.0.0.1 --port 8765 --reload
