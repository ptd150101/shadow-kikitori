# JLPT Listening Studio

Local-first Japanese listening practice application for JLPT audio and YouTube sources.

It segments speech, assigns speakers, creates editable audio chunks, transcribes Japanese with Audio8, then supports full-transcript and cloze practice with furigana and context-aware Vietnamese translation.

The workspace includes an editor timeline with draggable boundaries, split/merge/reorder/delete, speaker colors, optimistic revision checks, undo/redo and loop playback. Transcript/practice routes use the same audio controller; practice responses deliberately omit answer text until an explicit reveal request.

## Architecture

- `apps/api`: FastAPI API, SQLite, persistent worker, media and AI pipeline.
- `apps/web`: React + Vite audio editor and practice UI.
- `.runtime-data/` (or the configured data directory): local runtime data, intentionally ignored by git.

More detail is in [`docs/architecture.md`](docs/architecture.md), [`docs/data-model.md`](docs/data-model.md), [`docs/model-setup.md`](docs/model-setup.md) and [`docs/troubleshooting.md`](docs/troubleshooting.md).

## Prerequisites

- Python 3.11 or 3.12 and [uv](https://docs.astral.sh/uv/)
- Node.js 20+
- FFmpeg and FFprobe on `PATH`
- `yt-dlp` on `PATH` for YouTube import (kept as an external executable so `uv sync` stays offline-friendly)
- NVIDIA CUDA/PyTorch for local AI inference
- A local llama.cpp server configured with Gemma 4 E4B, or a managed llama.cpp executable/model path

## Development

```bash
cp .env.example .env
cd apps/api
uv sync --all-groups
uv run alembic upgrade head
uv run uvicorn jlpt_studio.main:app --reload --host 127.0.0.1 --port 8765
```

In a second terminal:

```bash
cd apps/api
uv run python -m jlpt_studio.jobs.worker
```

And for the web UI:

```bash
cd apps/web
npm install
npm run dev
```

The frontend proxies `/api` to port `8765` in development.

### UI preview without models

To view the editor layout without installing the backend or downloading model weights, build the static demo route:

```bash
cd apps/web
VITE_PREVIEW_MODE=true npm run build
npx vite preview --host 127.0.0.1
```

Open `/` or `/preview`. The demo uses representative JLPT data and keeps all controls local; the full `/projects` route remains connected to the real API when `VITE_PREVIEW_MODE` is not set.

On Windows, the same three processes can be started with `scripts/start-api.ps1`, `scripts/start-worker.ps1` and `scripts/start-web.ps1`. `scripts/healthcheck.ps1` checks the local tools and model dependencies.

## Model setup

1. Accept the Community-1 terms on Hugging Face and provide `JLPT_HF_TOKEN` for first download, or set `JLPT_PYANNOTE_MODEL_PATH` to the downloaded model folder. The intended steady state is the local path.
2. Install AI dependencies with `uv sync --group ai` (or `--all-groups`).
3. Start Gemma 4 in llama.cpp, for example:

```bash
llama-server -hf unsloth/gemma-4-E4B-it-qat-GGUF:UD-Q4_K_XL -ngl 999 --port 8080
```

4. Open `http://127.0.0.1:5173`.

## Important licensing note

Audio8 is currently licensed CC-BY-NC-4.0. This repository is intended for personal/non-commercial study until the ASR provider is replaced or a commercial license is confirmed.

Review the model terms before redistribution: [Audio8](https://huggingface.co/Edge0/Audio8-ASR-0.1B), [Community-1](https://huggingface.co/pyannote/speaker-diarization-community-1) and [Gemma 4 E4B GGUF](https://huggingface.co/unsloth/gemma-4-E4B-it-qat-GGUF) are external weights with their own access and license conditions.
