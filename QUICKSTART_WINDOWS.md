# Quick start on Windows

1. Install Python 3.11/3.12, Node.js 20+, [uv](https://docs.astral.sh/uv/), FFmpeg and yt-dlp.
2. Copy `.env.example` to `.env` and set the optional model paths/token.
3. In PowerShell from this directory run:

```powershell
./scripts/start-api.ps1
```

Open a second PowerShell window and run `./scripts/start-worker.ps1`, then a third with `./scripts/start-web.ps1`. Visit `http://127.0.0.1:5173`.

The first test can use only the pure-domain pipeline tests. Real Audio8/Community-1/Gemma inference requires the AI group, model weights and (for Community-1) accepted Hugging Face terms.
