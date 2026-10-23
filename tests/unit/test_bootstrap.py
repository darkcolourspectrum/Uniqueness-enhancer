from fakes import SpyTranslator
from textuniq.bootstrap import Settings, build_chain_translator
from textuniq.domain.models import TranslationChain

LONG = " ".join(f"Предложение номер {i}." for i in range(100))
SETTINGS = Settings(chain=TranslationChain.parse("ru,en,ru"), max_chunk_chars=200)


class UnlimitedSpy(SpyTranslator):
    max_text_chars = None


class LimitedSpy(SpyTranslator):
    max_text_chars = 1000


def first_step_texts(spy):
    (texts,) = [texts for texts, src, _ in spy.calls if src == "ru"]
    return texts


def test_local_models_get_long_paragraphs_in_chunks_from_settings():
    spy = SpyTranslator()
    build_chain_translator(SETTINGS, spy).translate(LONG)

    texts = first_step_texts(spy)
    assert len(texts) > 1 and all(len(t) <= 200 for t in texts)


def test_translator_without_limit_gets_whole_paragraph():
    spy = UnlimitedSpy()
    build_chain_translator(SETTINGS, spy).translate(LONG)

    assert first_step_texts(spy) == (LONG,)


def test_translator_limit_overrides_settings():
    spy = LimitedSpy()
    build_chain_translator(SETTINGS, spy).translate(LONG)

    texts = first_step_texts(spy)
    assert len(texts) > 1 and all(200 < len(t) <= 1000 for t in texts[:-1])
