import pytest

from fakes import InMemoryDocument, InMemoryLoader, SpyTranslator
from textuniq.application.output_path import default_output_path
from textuniq.application.processing import BlockProcessor
from textuniq.application.translation import ChainTranslator
from textuniq.application.uniquify import UniquifyDocument
from textuniq.domain.dashes import contains_dashes
from textuniq.domain.errors import DocumentError
from textuniq.domain.models import BlockRole, TextBlock, TranslationChain


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "статья.docx"
    path.write_bytes(b"original")
    return path


def make_use_case(blocks, spy=None):
    spy = spy or SpyTranslator(inject=" —")
    document = InMemoryDocument(blocks)
    processor = BlockProcessor(ChainTranslator(spy, TranslationChain.default()))
    return UniquifyDocument(InMemoryLoader(document), processor), document, spy


def test_each_main_paragraph_goes_through_chain_separately(source):
    blocks = [TextBlock(1, "Первый абзац."), TextBlock(2, "Второй абзац."), TextBlock(3, "Третий.")]
    use_case, _, spy = make_use_case(blocks)

    use_case.execute(source)

    assert len(spy.calls) == 3 * len(blocks)
    for texts, _, _ in spy.calls:
        assert len(texts) == 1
    first_steps = [texts[0] for texts, src, _ in spy.calls if src == "ru"]
    assert first_steps == ["Первый абзац.", "Второй абзац.", "Третий."]


def test_result_has_no_dashes_anywhere(source):
    blocks = [
        TextBlock(1, "Текст — раз"),
        TextBlock(2, "Колонтитул – два", BlockRole.AUXILIARY),
        TextBlock(3, "− 5"),
    ]
    use_case, document, _ = make_use_case(blocks)

    use_case.execute(source)

    assert not any(contains_dashes(b.text) for b in document.blocks())


def test_saves_to_default_copy_and_leaves_source_untouched(source):
    use_case, document, _ = make_use_case([TextBlock(1, "Абзац")])

    summary = use_case.execute(source)

    assert source.read_bytes() == b"original"
    assert document.saved_to == source.with_name("статья_uniq.docx")
    assert summary.output == document.saved_to


def test_refuses_to_overwrite_source(source):
    use_case, document, _ = make_use_case([TextBlock(1, "Абзац")])

    with pytest.raises(DocumentError):
        use_case.execute(source, target=source)
    assert document.saved_to is None


def test_summary_counts(source):
    blocks = [
        TextBlock(1, "Хороший абзац"),
        TextBlock(2, "Тут сбой"),
        TextBlock(3, "123"),
        TextBlock(4, "Колонтитул", BlockRole.AUXILIARY),
    ]
    use_case, _, _ = make_use_case(blocks, SpyTranslator(fail_on="сбой"))

    summary = use_case.execute(source)

    assert (summary.total, summary.translated, summary.failed, summary.skipped) == (4, 1, 1, 2)


def test_unchanged_blocks_are_not_rewritten(source):
    use_case, document, _ = make_use_case([TextBlock(1, "12 34")])

    use_case.execute(source)

    assert document.replacements == []


def test_progress_callback_receives_every_block(source):
    blocks = [TextBlock(1, "Один"), TextBlock(2, "Два")]
    use_case, _, _ = make_use_case(blocks)
    seen = []

    use_case.execute(source, on_block=lambda i, total, block, result: seen.append((i, total, block.id)))

    assert seen == [(1, 2, 1), (2, 2, 2)]


def test_default_output_path_does_not_overwrite_existing(tmp_path):
    src = tmp_path / "post.docx"
    src.touch()
    assert default_output_path(src) == tmp_path / "post_uniq.docx"

    (tmp_path / "post_uniq.docx").touch()
    assert default_output_path(src) == tmp_path / "post_uniq_2.docx"

    (tmp_path / "post_uniq_2.docx").touch()
    assert default_output_path(src) == tmp_path / "post_uniq_3.docx"
