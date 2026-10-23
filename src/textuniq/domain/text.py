"""Чистые текстовые утилиты: что переводить и как резать длинный абзац."""

import re

# Граница предложения: знак конца, пробел, затем начало нового предложения
# (заглавная буква, цифра, открывающая кавычка/скобка или тире прямой речи).
_SENTENCE_BOUNDARY = re.compile(
    r"(?<=[.!?…])\s+(?=[«\"„“(\[\-—–]?[A-ZА-ЯЁÄÖÜ0-9])"
)
_SOFT_BOUNDARY = re.compile(r"(?<=[,;:])\s+")


def is_translatable(text: str) -> bool:
    """Есть ли в тексте хоть одна буква — без букв переводить нечего."""
    return any(ch.isalpha() for ch in text)


def split_edges(text: str) -> tuple[str, str, str]:
    """Разделяет текст на (ведущие пробелы, суть, хвостовые пробелы)."""
    core = text.strip()
    if not core:
        return text, "", ""
    start = text.index(core)
    return text[:start], core, text[start + len(core):]


def split_into_chunks(text: str, max_chars: int) -> list[str]:
    """Режет текст на куски не длиннее max_chars по границам предложений.

    Куски склеиваются обратно через один пробел. Предложение длиннее лимита
    режется по запятым/точкам с запятой, затем по словам. Слово длиннее лимита
    остаётся целым.
    """
    if max_chars <= 0:
        raise ValueError("max_chars должен быть положительным")
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    pieces: list[str] = []
    for sentence in _SENTENCE_BOUNDARY.split(text):
        pieces.extend(_split_long(sentence, max_chars))
    return _pack(pieces, max_chars)


def _split_long(sentence: str, max_chars: int) -> list[str]:
    if len(sentence) <= max_chars:
        return [sentence]
    parts: list[str] = []
    for clause in _SOFT_BOUNDARY.split(sentence):
        if len(clause) <= max_chars:
            parts.append(clause)
        else:
            parts.extend(clause.split())
    return _pack(parts, max_chars)


def _pack(pieces: list[str], max_chars: int) -> list[str]:
    chunks: list[str] = []
    current = ""
    for piece in pieces:
        if not piece:
            continue
        candidate = f"{current} {piece}" if current else piece
        if len(candidate) <= max_chars or not current:
            current = candidate
        else:
            chunks.append(current)
            current = piece
    if current:
        chunks.append(current)
    return chunks
