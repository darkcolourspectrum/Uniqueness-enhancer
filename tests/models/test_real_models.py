"""Прогон на настоящих моделях. По умолчанию не запускается.

Запуск: pytest -m models -s
При первом запуске модели скачиваются в кэш HuggingFace (нужен интернет).
"""

import pytest

pytest.importorskip("torch")
pytest.importorskip("transformers")

from textuniq.bootstrap import Settings, build_chain_translator  # noqa: E402

pytestmark = pytest.mark.models

TEXT = (
    "Утренняя пробежка задаёт тон всему дню. После 20 минут лёгкого бега "
    "улучшается кровообращение, а голова становится яснее."
)


def cyrillic_share(text: str) -> float:
    letters = [ch for ch in text if ch.isalpha()]
    return sum("а" <= ch.lower() <= "я" or ch.lower() == "ё" for ch in letters) / max(len(letters), 1)


@pytest.mark.parametrize("engine", ["marian", "nllb"])
def test_round_trip_returns_russian_text(engine):
    translator = build_chain_translator(Settings(engine=engine, num_beams=4))

    result = translator.translate(TEXT)

    print(f"\n[{engine}]\nбыло:  {TEXT}\nстало: {result}")
    assert cyrillic_share(result) > 0.8
    assert "20" in result
    assert result != TEXT
