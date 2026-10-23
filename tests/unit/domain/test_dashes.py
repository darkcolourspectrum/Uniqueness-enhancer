import sys
import unicodedata

import pytest

from textuniq.domain.dashes import DASH_CHARS, contains_dashes, normalize_dashes


@pytest.mark.parametrize(
    "dash",
    [
        "—",  # — длинное тире
        "–",  # – короткое тире
        "‒",  # ‒ цифровое тире
        "―",  # ― горизонтальная черта
        "−",  # − знак минуса
        "‐",  # ‐ дефис Unicode
        "‑",  # ‑ неразрывный дефис
        "⸺",  # ⸺ двойное тире
        "⸻",  # ⸻ тройное тире
        "﹘",  # ﹘ малое длинное тире
        "﹣",  # ﹣ малый дефис-минус
        "－",  # － полноширинный дефис-минус
    ],
)
def test_every_dash_variant_becomes_hyphen_minus(dash):
    assert normalize_dashes(f"слово{dash}слово") == "слово-слово"


def test_all_unicode_dash_punctuation_is_covered():
    pd_chars = {
        chr(cp)
        for cp in range(sys.maxunicode + 1)
        if unicodedata.category(chr(cp)) == "Pd" and chr(cp) != "-"
    }
    assert pd_chars <= DASH_CHARS


def test_spaces_around_dash_are_kept():
    assert normalize_dashes("Утро — лучшее время") == "Утро - лучшее время"


def test_ranges_and_minus_in_numbers():
    assert normalize_dashes("10–15 минут при −5 °C") == "10-15 минут при -5 °C"


def test_text_without_dashes_is_unchanged():
    text = "Обычный текст, где-то с дефисом и неразрывным пробелом."
    assert normalize_dashes(text) == text


def test_soft_hyphen_is_not_treated_as_dash():
    text = "пере­нос"
    assert normalize_dashes(text) == text


def test_contains_dashes():
    assert contains_dashes("а — б")
    assert not contains_dashes("а - б")
