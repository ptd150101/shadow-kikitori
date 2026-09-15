from __future__ import annotations

import gc
from collections.abc import Callable
from pathlib import Path

from jlpt_studio.core.config import Settings
from jlpt_studio.core.errors import ProviderUnavailableError, StudioError


class Audio8AsrProvider:
    """Audio8 Transformers inference adapter.

    The provider intentionally keeps timestamps outside the model: segmentation
    owns timing and Audio8 owns text for <= 28-second WAV slices.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _device(self, torch_module) -> str:  # type: ignore[no-untyped-def]
        if self.settings.device != "auto":
            return self.settings.device
        return "cuda" if torch_module.cuda.is_available() else "cpu"

    def transcribe_many(
        self,
        audio_paths: list[Path],
        *,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> list[str]:
        import wave

        for path in audio_paths:
            try:
                with wave.open(str(path), "rb") as handle:
                    duration = handle.getnframes() / max(handle.getframerate(), 1)
                if duration > self.settings.audio8_max_seconds:
                    raise StudioError(
                        "ASR_AUDIO_TOO_LONG",
                        f"Audio8 chỉ nhận tối đa {self.settings.audio8_max_seconds} giây mỗi chunk.",
                        status_code=422,
                    )
            except (wave.Error, OSError) as error:
                raise StudioError(
                    "INVALID_CHUNK_AUDIO", "Không đọc được audio chunk", status_code=422
                ) from error
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoProcessor
        except ImportError as error:
            raise ProviderUnavailableError(
                "audio8", "Chưa cài Transformers/PyTorch. Chạy `uv sync --group ai`."
            ) from error
        device = self._device(torch)
        model = None
        try:
            load_kwargs: dict[str, object] = {
                "trust_remote_code": True,
                "attn_implementation": "eager",
            }
            if self.settings.audio8_revision:
                load_kwargs["revision"] = self.settings.audio8_revision
            if device.startswith("cuda"):
                load_kwargs["torch_dtype"] = torch.bfloat16
            processor_kwargs: dict[str, object] = {"trust_remote_code": True}
            if self.settings.audio8_revision:
                processor_kwargs["revision"] = self.settings.audio8_revision
            processor = AutoProcessor.from_pretrained(self.settings.audio8_model_id, **processor_kwargs)
            model = AutoModelForCausalLM.from_pretrained(
                self.settings.audio8_model_id, **load_kwargs
            )
            model = model.to(device)
            model.eval()
            outputs: list[str] = []
            for index, path in enumerate(audio_paths, start=1):
                text = self._transcribe_one(torch, processor, model, path, device)
                outputs.append(text)
                if on_progress:
                    on_progress(index, len(audio_paths))
            return outputs
        except StudioError:
            raise
        except RuntimeError as error:
            message = str(error)
            if "out of memory" in message.lower():
                raise StudioError(
                    "CUDA_OOM",
                    "Audio8 hết VRAM. Hãy đóng model khác hoặc giảm batch/pipeline đồng thời.",
                    status_code=503,
                ) from error
            raise StudioError(
                "ASR_FAILED", f"Audio8 transcription thất bại: {message}", status_code=422
            ) from error
        except Exception as error:
            raise StudioError(
                "ASR_FAILED", f"Audio8 transcription thất bại: {error}", status_code=422
            ) from error
        finally:
            if model is not None:
                del model
            gc.collect()
            try:
                if torch.cuda.is_available():  # type: ignore[possibly-undefined]
                    torch.cuda.empty_cache()  # type: ignore[possibly-undefined]
            except Exception:
                pass

    @staticmethod
    def _transcribe_one(torch_module, processor, model, path: Path, device: str) -> str:  # type: ignore[no-untyped-def]
        conversation = [
            {
                "role": "user",
                "content": [
                    {"type": "audio", "path": str(path)},
                    {
                        "type": "text",
                        "text": "Transcribe this Japanese audio exactly. Output only the Japanese transcript, with no explanation.",
                    },
                ],
            }
        ]
        batch = processor.apply_chat_template(
            conversation,
            return_tensors="pt",
            sampling_rate=16000,
            audio_padding="longest",
            add_generation_prompt=True,
            audio_max_length=30 * 16000,
            text_kwargs={"padding": "longest", "truncation": True, "max_length": 1000},
        )
        batch = {
            key: value.to(device) if hasattr(value, "to") else value
            for key, value in dict(batch).items()
        }
        with torch_module.inference_mode():
            output_ids = model.generate(**batch, max_new_tokens=256, do_sample=False)
        prompt_len = int(batch["input_ids"].shape[1])
        text = processor.decode(output_ids[0, prompt_len:], skip_special_tokens=True).strip()
        if not text:
            raise StudioError(
                "EMPTY_ASR_OUTPUT",
                "Audio8 không trả transcript cho audio chunk này",
                status_code=422,
            )
        return text
