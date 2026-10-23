import pytest

from textuniq.domain.text import is_translatable, split_edges, split_into_chunks


@pytest.mark.parametrize(
    "text, expected",
    [
        ("", False),
        ("   \t", False),
        ("123 - 456", False),
        ("— • ★ 😀", False),
        ("Привет", True),
        ("1. Пункт списка", True),
        ("Hello", True),
    ],
)
def test_is_translatable(text, expected):
    assert is_translatable(text) is expected


def test_split_edges_keeps_surrounding_whitespace():
    assert split_edges("  текст абзаца \t") == ("  ", "текст абзаца", " \t")


def test_split_edges_on_blank_text():
    assert split_edges("   ") == ("   ", "", "")


def test_short_text_is_a_single_chunk():
    assert split_into_chunks("Одно предложение. И второе.", max_chars=100) == [
        "Одно предложение. И второе."
    ]


def test_long_text_is_split_on_sentence_boundaries():
    sentences = [f"Это предложение номер {i}." for i in range(1, 21)]
    text = " ".join(sentences)

    chunks = split_into_chunks(text, max_chars=120)

    assert len(chunks) > 1
    assert all(len(c) <= 120 for c in chunks)
    assert all(c.endswith(".") for c in chunks)
    assert " ".join(chunks) == text


def test_sentence_split_handles_other_terminators():
    text = "Правда? Да! Конечно… «Цитата». Конец."
    chunks = split_into_chunks(text, max_chars=12)
    assert " ".join(chunks) == text
    assert chunks[0] == "Правда? Да!"


def test_overlong_sentence_is_split_without_losing_words():
    text = "слово, " * 60 + "конец."
    chunks = split_into_chunks(text.strip(), max_chars=50)

    assert all(0 < len(c) <= 50 for c in chunks)
    assert " ".join(chunks).split() == text.split()


def test_single_word_longer_than_limit_is_kept_whole():
    word = "а" * 80
    assert split_into_chunks(word, max_chars=50) == [word]


def test_max_chars_must_be_positive():
    with pytest.raises(ValueError):
        split_into_chunks("текст", max_chars=0)
