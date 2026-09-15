# API

Run commands from this directory with `uv`. AI providers are imported lazily, so API and pure-domain tests run without model weights.

```powershell
uv sync --locked --group dev
uv run alembic upgrade head
uv run uvicorn jlpt_studio.main:app --reload --host 127.0.0.1 --port 8765
# second terminal
uv run python -m jlpt_studio.jobs.worker
```

The API exposes project/media import, durable processing jobs, waveform/timeline editing, speaker labels, bilingual transcript, full/cloze exercises, answer-gated attempts, metrics and JSON/ZIP export under `/api`.
