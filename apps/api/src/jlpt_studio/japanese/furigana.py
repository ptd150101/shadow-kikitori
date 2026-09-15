from __future__ import annotations

import re

from jlpt_studio.core.errors import ProviderUnavailableError

KANJI_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


def katakana_to_hiragana(value: str) -> str:
    return "".join(
        chr(ord(character) - 0x60) if "ァ" <= character <= "ヶ" else character
        for character in value
    )


class FuriganaService:
    def tokenize(self, text: str) -> list[dict[str, str | bool | None]]:
        try:
            from sudachipy import Dictionary, SplitMode
        except ImportError as error:
            raise ProviderUnavailableError(
                "sudachipy", "Chưa cài SudachiPy. Chạy `uv sync --group ai`."
            ) from error
        tokenizer = Dictionary().create()
        tokens: list[dict[str, str | bool | None]] = []
        for token in tokenizer.tokenize(text, SplitMode.C):
            surface = token.surface()
            try:
                reading = token.reading_form()
            except AttributeError:
                reading = None
            reading_hiragana = katakana_to_hiragana(reading) if reading and reading != "*" else None
            tokens.append(
                {
                    "surface": surface,
                    "reading": reading_hiragana,
                    "ruby": bool(reading_hiragana and KANJI_RE.search(surface)),
                    "part_of_speech": token.part_of_speech()[0] if token.part_of_speech() else None,
                }
            )
        return tokens
