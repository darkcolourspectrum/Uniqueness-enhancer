import pytest

from fakes import SpyTranslator
from textuniq.application.translation import ChainTranslator, SegmentingTranslator
from textuniq.domain.errors import TranslationError
from textuniq.domain.models import TranslationChain


def test_text_goes_through_every_step_in_order():
    spy = SpyTranslator()
    chain = ChainTranslator(spy, TranslationChain.default())

    result = chain.translate("Привет")

    assert [(src, tgt) for _, src, tgt in spy.calls] == [("ru", "en"), ("en", "de"), ("de", "ru")]
    assert result == "[ru] [de] [en] Привет"


def test_each_step_receives_only_previous_result():
    spy = SpyTranslator()
    ChainTranslator(spy, TranslationChain.default()).translate("Привет")

    assert [texts for texts, _, _ in spy.calls] == [
        ("Привет",),
        ("[en] Привет",),
        ("[de] [en] Привет",),
    ]


def test_empty_step_result_raises():
    spy = SpyTranslator(empty_on="[en]")
    chain = ChainTranslator(spy, TranslationChain.default())

    with pytest.raises(TranslationError):
        chain.translate("Привет")


def test_segmenting_translator_keeps_short_text_whole():
    spy = SpyTranslator()
    seg = SegmentingTranslator(spy, max_chars=100)

    assert seg.translate_batch(["Коротко."], "ru", "en") == ["[en] Коротко."]
    assert spy.calls == [(("Коротко.",), "ru", "en")]


def test_segmenting_translator_splits_long_text_and_reassembles():
    spy = SpyTranslator()
    seg = SegmentingTranslator(spy, max_chars=30)
    text = "Первое предложение тут. Второе предложение тут. Третье."

    result = seg.translate_batch([text], "ru", "en")

    (sent, _, _), = spy.calls
    assert len(sent) > 1
    assert result == [" ".join(f"[en] {chunk}" for chunk in sent)]


def test_segmenting_translator_batches_several_texts_in_one_call():
    spy = SpyTranslator()
    seg = SegmentingTranslator(spy, max_chars=100)

    result = seg.translate_batch(["Один.", "Два."], "ru", "en")

    assert result == ["[en] Один.", "[en] Два."]
    assert len(spy.calls) == 1
