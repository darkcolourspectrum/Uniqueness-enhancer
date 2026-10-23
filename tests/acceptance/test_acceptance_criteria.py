"""Критерии приёмки из ТЗ на моковом документе с фейковым переводчиком.

1. На входе Word-файл, на выходе его копия, исходный файл не изменён.
2. Каждый абзац прошёл цепочку перевода отдельно.
3. В копии все тире приведены к «-».
"""

import hashlib
import shutil
from pathlib import Path

import docx
import pytest

from docx_helpers import all_text_nodes
from fakes import SpyTranslator
from textuniq.bootstrap import Settings, build_uniquify
from textuniq.domain.dashes import DASH_CHARS, contains_dashes
from textuniq.domain.text import is_translatable

SAMPLE = Path(__file__).resolve().parents[2] / "samples" / "sample_article.docx"


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "статья.docx"
    shutil.copy(SAMPLE, path)
    return path


@pytest.fixture
def run(source):
    spy = SpyTranslator(inject=" —")  # переводчик ещё и добавляет тире
    summary = build_uniquify(Settings(), translator=spy).execute(source)
    return summary, spy


def main_paragraphs(path: Path) -> list[str]:
    d = docx.Document(str(path))
    texts = [p.text for p in d.paragraphs]
    for table in d.tables:
        for row in table.rows:
            for cell in row.cells:
                texts.extend(p.text for p in cell.paragraphs)
    return [t for t in texts if is_translatable(t)]


def test_sample_document_has_dashes_to_fix():
    assert any(contains_dashes(t) for texts in all_text_nodes(SAMPLE).values() for t in texts)


def test_criterion_1_output_is_a_copy_and_source_is_untouched(source):
    before = hashlib.sha256(source.read_bytes()).hexdigest()

    summary = build_uniquify(Settings(), translator=SpyTranslator()).execute(source)

    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    assert summary.output == source.with_name("статья_uniq.docx")
    assert summary.output.exists()
    docx.Document(str(summary.output))  # открывается как нормальный .docx


def test_criterion_2_every_paragraph_went_through_chain_separately(source, run):
    summary, spy = run
    originals = main_paragraphs(source)

    assert all(len(texts) == 1 for texts, _, _ in spy.calls), "в каждом запросе ровно один абзац"
    steps = [(src, tgt) for _, src, tgt in spy.calls]
    assert steps == [("ru", "en"), ("en", "de"), ("de", "ru")] * len(originals)
    assert sorted(texts[0] for texts, src, _ in spy.calls if src == "ru") == sorted(
        t.strip() for t in originals
    )
    assert summary.translated == len(originals)
    assert summary.failed == 0
    for text in main_paragraphs(summary.output):
        assert text.startswith("[ru] - [de] - [en] - ")


def test_criterion_3_no_dashes_left_anywhere_in_copy(run):
    summary, _ = run

    for part, texts in all_text_nodes(summary.output).items():
        for text in texts:
            assert not (set(text) & DASH_CHARS), f"тире в {part}: {text!r}"
