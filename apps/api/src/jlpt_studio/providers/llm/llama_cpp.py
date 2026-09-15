from __future__ import annotations

import atexit
import json
import subprocess
import time
from collections.abc import Iterable
from typing import Any

import httpx

from jlpt_studio.core.config import Settings
from jlpt_studio.core.errors import ProviderUnavailableError, StudioError

PROMPT_VERSION = "translation-ja-vi-v1"


class LlamaServerManager:
    """Optional local process manager; external mode never owns the process."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._process: subprocess.Popen[str] | None = None
        atexit.register(self.close)

    @property
    def base_url(self) -> str:
        return self.settings.llm_base_url.rstrip("/")

    def ensure_running(self) -> None:
        if self.settings.llm_mode == "external":
            return
        if self.health_check():
            return
        if not self.settings.llm_executable or not self.settings.llm_model_path:
            raise ProviderUnavailableError(
                "llama.cpp",
                "Managed llama.cpp cần JLPT_LLM_EXECUTABLE và JLPT_LLM_MODEL_PATH.",
            )
        if self._process and self._process.poll() is None:
            return
        command = [
            str(self.settings.llm_executable),
            "-m",
            str(self.settings.llm_model_path),
            "--host",
            "127.0.0.1",
            "--port",
            str(self.settings.llm_port),
            "-ngl",
            "999",
        ]
        popen_kwargs: dict[str, Any] = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "text": True,
        }
        if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            popen_kwargs["start_new_session"] = True
        self._process = subprocess.Popen(command, **popen_kwargs)
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if self._process.poll() is not None:
                raise StudioError(
                    "LLAMA_SERVER_FAILED", "llama.cpp không khởi động được", status_code=503
                )
            if self.health_check():
                return
            time.sleep(0.5)
        raise ProviderUnavailableError("llama.cpp", "llama.cpp chưa sẵn sàng sau 45 giây")

    def health_check(self) -> bool:
        try:
            response = httpx.get(f"{self.base_url}/models", timeout=2.5, trust_env=False)
            return response.is_success
        except httpx.HTTPError:
            return False

    def close(self) -> None:
        if self.settings.llm_mode == "managed" and self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()


class GemmaTranslator:
    def __init__(self, settings: Settings, manager: LlamaServerManager | None = None) -> None:
        self.settings = settings
        self.manager = manager or LlamaServerManager(settings)

    def health_check(self) -> tuple[bool, str]:
        if self.settings.llm_mode == "managed":
            try:
                self.manager.ensure_running()
            except StudioError as error:
                return False, error.message
        ready = self.manager.health_check()
        return ready, "Sẵn sàng" if ready else "Không kết nối được llama.cpp server"

    def translate_batch(
        self,
        *,
        previous_context: list[dict[str, str]],
        targets: list[dict[str, str]],
        future_context: list[dict[str, str]],
    ) -> dict[str, str]:
        if not targets:
            return {}
        self.manager.ensure_running()
        user_prompt = self._prompt(previous_context, targets, future_context)
        payload: dict[str, Any] = {
            "model": self.settings.llm_model,
            "temperature": 0.1,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a precise Japanese-to-Vietnamese translator for JLPT listening study material. Return valid JSON only.",
                },
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        try:
            with httpx.Client(timeout=90, trust_env=False) as client:
                response = client.post(f"{self.manager.base_url}/chat/completions", json=payload)
                # Older llama.cpp builds may not support response_format. Retry once without it.
                if response.status_code in {400, 422} and "response_format" in response.text:
                    payload.pop("response_format", None)
                    response = client.post(
                        f"{self.manager.base_url}/chat/completions", json=payload
                    )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
        except httpx.HTTPError as error:
            raise ProviderUnavailableError(
                "llama.cpp", f"Không gọi được Gemma local: {error}"
            ) from error
        expected_ids = {item["chunk_id"] for item in targets}
        try:
            return self._parse(content, expected_ids)
        except StudioError as first_error:
            # A small repair pass handles models that wrap valid JSON in prose/fences.
            repair_payload = {
                **payload,
                "messages": [
                    {"role": "system", "content": "Repair JSON only. Return no markdown or prose."},
                    {"role": "user", "content": f"Expected IDs: {sorted(expected_ids)}\nMalformed output:\n{content[:6000]}\nReturn {{\"translations\":[{{\"chunk_id\":\"id\",\"translation_vi\":\"...\"}}]}}"},
                ],
            }
            try:
                with httpx.Client(timeout=45, trust_env=False) as client:
                    repaired = client.post(f"{self.manager.base_url}/chat/completions", json=repair_payload)
                    repaired.raise_for_status()
                    repaired_content = repaired.json()["choices"][0]["message"]["content"]
                return self._parse(repaired_content, expected_ids)
            except (httpx.HTTPError, KeyError, StudioError) as repair_error:
                raise first_error from repair_error

    @staticmethod
    def _prompt(
        previous_context: list[dict[str, str]],
        targets: list[dict[str, str]],
        future_context: list[dict[str, str]],
    ) -> str:
        def render(name: str, items: Iterable[dict[str, str]]) -> str:
            lines = [f"[{item['speaker']}] {item['text']}" for item in items]
            return f"{name}:\n" + ("\n".join(lines) if lines else "(none)")

        target_lines = "\n".join(
            f"{item['chunk_id']} | speaker={item['speaker']} | Japanese={item['text']}"
            for item in targets
        )
        return f"""Translate only TARGET lines from Japanese to natural Vietnamese. Use context only to resolve omitted subjects, politeness, and conversation flow. Do not add explanations. Preserve names and numbers accurately.

{render("PREVIOUS CONTEXT — DO NOT TRANSLATE", previous_context)}

TARGETS — TRANSLATE EVERY ID EXACTLY ONCE:
{target_lines}

{render("FUTURE CONTEXT — DO NOT TRANSLATE", future_context)}

Return exactly this JSON shape:
{{"translations":[{{"chunk_id":"target id","translation_vi":"Vietnamese translation"}}]}}"""

    @staticmethod
    def _parse(content: str, expected_ids: set[str]) -> dict[str, str]:
        raw = content.strip()
        if raw.startswith("```"):
            raw = raw.removeprefix("```").removeprefix("json").strip()
            if raw.endswith("```"):
                raw = raw[:-3].strip()
        # Some quantized instruct models add one sentence around the object.
        if not raw.startswith("{"):
            start, end = raw.find("{"), raw.rfind("}")
            if start >= 0 and end > start:
                raw = raw[start : end + 1]
        try:
            decoded = json.loads(raw)
            items = decoded["translations"]
        except (json.JSONDecodeError, KeyError, TypeError) as error:
            raise StudioError(
                "TRANSLATION_INVALID_JSON",
                "Gemma không trả JSON dịch hợp lệ",
                {"output": content[:1000]},
                422,
            ) from error
        mapping: dict[str, str] = {}
        for item in items:
            chunk_id = str(item.get("chunk_id", ""))
            translation = str(item.get("translation_vi", "")).strip()
            if not chunk_id or not translation or chunk_id in mapping:
                raise StudioError(
                    "TRANSLATION_INVALID_ITEMS", "Gemma trả item dịch không hợp lệ", status_code=422
                )
            mapping[chunk_id] = translation
        if set(mapping) != expected_ids:
            raise StudioError(
                "TRANSLATION_MISSING_IDS",
                "Gemma không trả đủ bản dịch cho các chunk yêu cầu",
                {"expected": sorted(expected_ids), "returned": sorted(mapping)},
                422,
            )
        return mapping
