from fakes import SpyTranslator
from textuniq.application.processing import BlockProcessor, BlockStatus
from textuniq.application.translation import ChainTranslator
from textuniq.domain.models import BlockRole, TextBlock, TranslationChain


def make_processor(spy=None):
    spy = spy or SpyTranslator()
    return BlockProcessor(ChainTranslator(spy, TranslationChain.default())), spy


def test_main_block_is_translated_and_dashes_normalized_after_translation():
    processor, _ = make_processor(SpyTranslator(inject=" —"))

    result = processor.process(TextBlock(1, "Текст – с тире"))

    assert result.status is BlockStatus.TRANSLATED
    assert "—" not in result.text and "–" not in result.text
    assert result.text == "[ru] - [de] - [en] - Текст – с тире".replace("–", "-")


def test_surrounding_whitespace_is_preserved_and_not_sent_to_translator():
    processor, spy = make_processor()

    result = processor.process(TextBlock(1, "  Абзац\t"))

    assert spy.calls[0][0] == ("Абзац",)
    assert result.text == "  [ru] [de] [en] Абзац\t"


def test_auxiliary_block_is_only_normalized():
    processor, spy = make_processor()

    result = processor.process(TextBlock(1, "Блог — 2026", BlockRole.AUXILIARY))

    assert result.status is BlockStatus.SKIPPED
    assert result.text == "Блог - 2026"
    assert spy.calls == []


def test_block_without_letters_is_skipped_but_normalized():
    processor, spy = make_processor()

    result = processor.process(TextBlock(1, "10–20"))

    assert result.status is BlockStatus.SKIPPED
    assert result.text == "10-20"
    assert spy.calls == []


def test_translation_failure_keeps_original_text_normalized():
    processor, _ = make_processor(SpyTranslator(fail_on="сбой"))

    result = processor.process(TextBlock(1, "Здесь сбой — бывает"))

    assert result.status is BlockStatus.FAILED
    assert result.text == "Здесь сбой - бывает"
    assert result.error


def test_processor_without_translator_only_normalizes():
    processor = BlockProcessor(translator=None)

    result = processor.process(TextBlock(1, "А — Б"))

    assert result.status is BlockStatus.SKIPPED
    assert result.text == "А - Б"
