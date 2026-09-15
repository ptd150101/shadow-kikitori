# Troubleshooting

* **`TOOL_NOT_FOUND` / missing FFmpeg**: install FFmpeg, add its `bin` directory to PATH, or set `JLPT_FFMPEG_PATH` and `JLPT_FFPROBE_PATH`.
* **`YTDLP_NOT_FOUND`**: install `yt-dlp` separately (`winget install yt-dlp`) and verify `yt-dlp --version` works in the same terminal as the API.
* **`PYANNOTE_ACCESS_REQUIRED`**: accept Community-1 terms, set `JLPT_HF_TOKEN`, run one diarization, then configure the downloaded directory as `JLPT_PYANNOTE_MODEL_PATH`.
* **`PROVIDER_UNAVAILABLE` for Audio8/Sudachi**: run `uv sync --group ai`; model weights are downloaded lazily on first use.
* **`CUDA_OOM`**: close other GPU processes, select CPU in Model & Settings, or use the shorter segmentation preset.
* **Gemma unavailable**: check `http://127.0.0.1:8080/v1/models`, then compare the URL and model name in Model & Settings.
* **Stuck job**: start the worker again. A heartbeat older than `JLPT_STALE_JOB_SECONDS` is marked `interrupted` and can be retried.
* **Transcript changed unexpectedly**: a gray `ai_unverified` label can be edited and confirmed. `user_confirmed` references are preserved across reprocessing.
