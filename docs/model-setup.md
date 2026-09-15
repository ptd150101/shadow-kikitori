# Local model setup

## Audio8

The default adapter is `Edge0/Audio8-ASR-0.1B`. Install the AI dependency group with `uv sync --group ai`, keep `JLPT_AUDIO8_MODEL_ID` at the default, and choose `JLPT_DEVICE=auto`, `cuda` or `cpu`. Audio is converted to mono 16 kHz WAV and capped at 28 seconds before inference.

## Community-1

Accept the model terms on Hugging Face once, set `JLPT_HF_TOKEN` for the first download, and then point `JLPT_PYANNOTE_MODEL_PATH` at the local model directory. The diarization adapter uses the exclusive diarization output when available and supports an optional speaker count. The API reports Community-1 as unavailable until dependencies and either a local path or token are present.

## Gemma 4

Run a local llama.cpp OpenAI-compatible server with a Gemma 4 E4B quantization. Example:

```powershell
llama-server -hf unsloth/gemma-4-E4B-it-qat-GGUF:UD-Q4_K_XL -ngl 999 --port 8080
```

Set `JLPT_LLM_MODE=external` to use that process, or `managed` together with `JLPT_LLM_EXECUTABLE` and `JLPT_LLM_MODEL_PATH` to let the worker start and stop it. The translator requests strict JSON, validates every target chunk ID, and runs one repair request when a quantized model wraps JSON in prose.
