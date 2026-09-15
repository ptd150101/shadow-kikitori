from __future__ import annotations

import random
from collections.abc import Sequence

CONTENT_POS = {"名詞", "動詞", "形容詞", "副詞", "連体詞"}


def generate_blank_spec(
    tokens: Sequence[dict[str, object]], *, count: int = 1, grammar_mode: bool = False, seed: int | None = None
) -> dict[str, object]:
    """Choose stable token ranges, never fragile character regex offsets."""
    allowed = CONTENT_POS | ({"助詞", "助動詞"} if grammar_mode else set())
    candidates = [
        index
        for index, token in enumerate(tokens)
        if str(token.get("part_of_speech") or "") in allowed
        and str(token.get("surface") or "").strip()
    ]
    if not candidates:
        candidates = [
            index for index, token in enumerate(tokens) if str(token.get("surface") or "").strip()
        ]
    if seed is not None:
        random.Random(seed).shuffle(candidates)
    # Spread blanks across the utterance rather than hiding neighboring words.
    selected: list[int] = []
    while candidates and len(selected) < max(1, count):
        if not selected:
            selected.append(candidates.pop(len(candidates) // 2))
            continue
        best = max(candidates, key=lambda index: min(abs(index - chosen) for chosen in selected))
        selected.append(best)
        candidates.remove(best)
    selected.sort()
    return {"version": 1, "blank_token_indexes": selected}
