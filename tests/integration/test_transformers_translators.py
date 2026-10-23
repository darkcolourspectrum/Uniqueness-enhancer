import pytest

pytest.importorskip("torch")
pytest.importorskip("transformers")
pytest.importorskip("sentencepiece")

from tiny_models import build_tiny_marian, build_tiny_nllb  # noqa: E402
from textuniq.domain.errors import TranslatorUnavailableError  # noqa: E402
from textuniq.infrastructure.translators.marian import MarianModel, MarianTranslator  # noqa: E402
from textuniq.infrastructure.translators.nllb import NllbTranslator  # noqa: E402


@pytest.fixture(scope="module")
def tiny_marian(tmp_path_factory):
    return build_tiny_marian(tmp_path_factory.mktemp("marian"))


@pytest.fixture(scope="module")
def tiny_nllb(tmp_path_factory):
    return build_tiny_nllb(tmp_path_factory.mktemp("nllb"))


def test_marian_adapter_translates_in_batches(tiny_marian):
    translator = MarianTranslator(
        models={("ru", "en"): MarianModel(str(tiny_marian))},
        device="cpu",
        num_beams=2,
        batch_size=2,
        local_files_only=True,
    )
    texts = ["Привет мир.", "Номер один.", "Номер два.", "Мир."]

    result = translator.translate_batch(texts, "ru", "en")

    assert len(result) == len(texts)
    assert all(isinstance(r, str) for r in result)


def test_marian_adapter_loads_each_model_once(tiny_marian):
    translator = MarianTranslator(
        models={("ru", "en"): MarianModel(str(tiny_marian)), ("en", "de"): MarianModel(str(tiny_marian))},
        device="cpu",
        num_beams=1,
        local_files_only=True,
    )
    translator.translate_batch(["Привет"], "ru", "en")
    translator.translate_batch(["Hello"], "en", "de")
    translator.translate_batch(["Привет"], "ru", "en")

    assert len(translator._models) == 1


def test_marian_prefix_is_added_before_tokenization(tiny_marian, monkeypatch):
    translator = MarianTranslator(
        models={("de", "ru"): MarianModel(str(tiny_marian), prefix=">>rus<< ")},
        device="cpu",
        num_beams=1,
        local_files_only=True,
    )
    seen = []
    original = translator._generate
    monkeypatch.setattr(
        translator, "_generate", lambda tok, model, batch, kw: seen.extend(batch) or original(tok, model, batch, kw)
    )

    translator.translate_batch(["Hallo Welt"], "de", "ru")

    assert seen == [">>rus<< Hallo Welt"]


def test_nllb_adapter_sets_languages(tiny_nllb):
    translator = NllbTranslator(model_name=str(tiny_nllb), device="cpu", num_beams=2, local_files_only=True)

    result = translator.translate_batch(["Привет мир.", "Мир."], "ru", "de")

    assert len(result) == 2
    tokenizer, _ = translator._models[str(tiny_nllb)]
    assert tokenizer.src_lang == "rus_Cyrl"


def test_missing_model_gives_clear_error(tmp_path):
    translator = MarianTranslator(
        models={("ru", "en"): MarianModel(str(tmp_path / "нет-модели"))},
        device="cpu",
        local_files_only=True,
    )
    with pytest.raises(TranslatorUnavailableError):
        translator.translate_batch(["Привет"], "ru", "en")
