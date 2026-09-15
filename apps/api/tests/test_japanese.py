from jlpt_studio.japanese import character_diff, normalize_japanese, similarity_score


def test_forgiving_normalization_ignores_spacing_and_punctuation() -> None:
    assert normalize_japanese(" 今日は、 3 時です。 ") == "今日は3時です"


def test_strict_normalization_preserves_punctuation() -> None:
    assert normalize_japanese("今日は。", forgiving=False) == "今日は。"


def test_character_diff_captures_missing_and_extra() -> None:
    diff = character_diff("私は学生です", "私学生だ")
    assert any(item["kind"] == "missing" for item in diff)
    assert any(item["kind"] == "extra" for item in diff)
    assert similarity_score("abc", "abc") == 100.0

