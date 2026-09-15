from __future__ import annotations

import difflib
import unicodedata

PUNCTUATION = "。、「」！？!?.,，．・"


def normalize_japanese(text: str, *, forgiving: bool = True) -> str:
    normalized = unicodedata.normalize("NFKC", text or "")
    normalized = " ".join(normalized.split())
    if forgiving:
        normalized = "".join(
            character
            for character in normalized
            if character not in PUNCTUATION and not character.isspace()
        )
    return normalized


def character_diff(expected: str, actual: str) -> list[dict[str, str]]:
    matcher = difflib.SequenceMatcher(a=expected, b=actual, autojunk=False)
    parts: list[dict[str, str]] = []
    for tag, a0, a1, b0, b1 in matcher.get_opcodes():
        if tag == "equal":
            parts.append({"kind": "equal", "text": expected[a0:a1]})
        elif tag == "delete":
            parts.append({"kind": "missing", "text": expected[a0:a1]})
        elif tag == "insert":
            parts.append({"kind": "extra", "text": actual[b0:b1]})
        else:
            parts.append({"kind": "missing", "text": expected[a0:a1]})
            parts.append({"kind": "extra", "text": actual[b0:b1]})
    return [part for part in parts if part["text"]]


def similarity_score(expected: str, actual: str) -> float:
    if not expected and not actual:
        return 1.0
    if not expected:
        return 0.0
    return round(difflib.SequenceMatcher(a=expected, b=actual, autojunk=False).ratio() * 100, 2)
