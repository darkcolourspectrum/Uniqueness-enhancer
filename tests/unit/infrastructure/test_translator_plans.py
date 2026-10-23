import pytest

from textuniq.domain.errors import TranslatorUnavailableError
from textuniq.domain.models import TranslationChain
from textuniq.infrastructure.translators import create_translator
from textuniq.infrastructure.translators.identity import IdentityTranslator
from textuniq.infrastructure.translators.marian import MarianTranslator
from textuniq.infrastructure.translators.nllb import NllbTranslator


def test_marian_covers_default_chain():
    marian = MarianTranslator()
    for source, target in TranslationChain.default().steps:
        assert marian.plan(source, target).model_name


def test_marian_de_ru_uses_multitarget_model_with_russian_token():
    plan = MarianTranslator().plan("de", "ru")
    assert plan.model_name == "Helsinki-NLP/opus-mt-tc-big-de-zle"
    assert plan.prefix == ">>rus<< "


def test_marian_unknown_pair():
    with pytest.raises(TranslatorUnavailableError):
        MarianTranslator().plan("ru", "ja")


def test_nllb_plan_sets_source_and_forces_target_language():
    plan = NllbTranslator().plan("de", "ru")
    assert plan.tokenizer_attrs == {"src_lang": "deu_Latn"}
    assert plan.forced_bos_token == "rus_Cyrl"
    assert plan.prefix == ""


def test_nllb_unknown_language():
    with pytest.raises(TranslatorUnavailableError):
        NllbTranslator().plan("ru", "xx")


def test_factory_builds_engines_without_loading_models():
    assert isinstance(create_translator("marian", num_beams=2), MarianTranslator)
    nllb = create_translator("nllb", model="facebook/nllb-200-distilled-1.3B")
    assert nllb.model_name == "facebook/nllb-200-distilled-1.3B"
    assert isinstance(create_translator("identity"), IdentityTranslator)


def test_factory_builds_yandex_ignoring_local_options(monkeypatch):
    from textuniq.infrastructure.translators.yandex_api import YandexTranslator

    monkeypatch.setenv("YANDEX_API_KEY", "secret")
    translator = create_translator("yandex", device="cpu", num_beams=4)

    assert isinstance(translator, YandexTranslator)


def test_factory_rejects_unknown_engine_and_misplaced_model():
    with pytest.raises(TranslatorUnavailableError):
        create_translator("google")
    with pytest.raises(TranslatorUnavailableError):
        create_translator("marian", model="something")
    with pytest.raises(TranslatorUnavailableError):
        create_translator("yandex", model="something")


def test_identity_translator_returns_input():
    assert IdentityTranslator().translate_batch(["а", "б"], "ru", "en") == ["а", "б"]
