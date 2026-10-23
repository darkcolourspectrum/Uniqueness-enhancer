import hashlib
import io

import docx
import pytest
from docx.oxml import parse_xml

from docx_helpers import add_footnotes, part_xml, tiny_png
from textuniq.domain.errors import DocumentError
from textuniq.domain.models import BlockRole
from textuniq.infrastructure.docx_document import DocxDocumentLoader

V_NS = "urn:schemas-microsoft-com:vml"
MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def save(document, tmp_path, name="in.docx"):
    path = tmp_path / name
    document.save(str(path))
    return path


def texts(doc, role=None):
    return [b.text for b in doc.blocks() if b.text and (role is None or b.role is role)]


def load(path):
    return DocxDocumentLoader().load(path)


def test_reads_body_tables_and_headers_with_roles(tmp_path):
    d = docx.Document()
    d.add_heading("Заголовок", level=1)
    d.add_paragraph("Первый абзац.")
    table = d.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Ячейка"
    table.cell(0, 1).add_table(rows=1, cols=1).cell(0, 0).text = "Вложенная"
    d.add_paragraph("После таблицы.")
    d.sections[0].header.paragraphs[0].text = "Шапка"
    d.sections[0].footer.paragraphs[0].text = "Подвал"

    doc = load(save(d, tmp_path))

    assert texts(doc, BlockRole.MAIN) == ["Заголовок", "Первый абзац.", "Ячейка", "Вложенная", "После таблицы."]
    assert sorted(texts(doc, BlockRole.AUXILIARY)) == ["Подвал", "Шапка"]


def test_runs_tabs_and_breaks_are_joined_into_one_text(tmp_path):
    d = docx.Document()
    p = d.add_paragraph("Начало ")
    p.add_run("жирное").bold = True
    run = p.add_run(" и")
    run.add_tab()
    run.add_text("таб")
    run.add_break()
    run.add_text("перенос")

    doc = load(save(d, tmp_path))

    assert texts(doc) == ["Начало жирное и таб перенос"]


def test_same_length_replacement_keeps_run_formatting(tmp_path):
    d = docx.Document()
    p = d.add_paragraph("Утро ")
    p.add_run("—").bold = True
    p.add_run(" время")
    doc = load(save(d, tmp_path))

    (block,) = doc.blocks()
    doc.replace_text(block.id, "Утро - время")
    out = tmp_path / "out.docx"
    doc.save(out)

    runs = docx.Document(str(out)).paragraphs[0].runs
    assert [r.text for r in runs] == ["Утро ", "-", " время"]
    assert runs[1].bold is True


def test_new_text_collapses_into_first_run_and_keeps_images(tmp_path):
    d = docx.Document()
    p = d.add_paragraph("Старый ")
    p.add_run("текст").italic = True
    p.add_run().add_picture(io.BytesIO(tiny_png()))
    tail = p.add_run(" хвост")
    tail.add_tab()
    tail.add_break()
    doc = load(save(d, tmp_path))

    (block,) = doc.blocks()
    doc.replace_text(block.id, "Совсем новый текст")
    out = tmp_path / "out.docx"
    doc.save(out)

    paragraph = docx.Document(str(out)).paragraphs[0]
    assert paragraph.text == "Совсем новый текст"
    assert paragraph.runs[0].text == "Совсем новый текст"
    assert paragraph._p.xpath(".//pic:pic")
    assert not paragraph._p.xpath(".//w:tab | .//w:br")


def test_leading_and_trailing_spaces_survive_saving(tmp_path):
    d = docx.Document()
    d.add_paragraph("x")
    doc = load(save(d, tmp_path))

    (block,) = doc.blocks()
    doc.replace_text(block.id, "  с пробелами  ")
    out = tmp_path / "out.docx"
    doc.save(out)

    assert docx.Document(str(out)).paragraphs[0].text == "  с пробелами  "


def test_text_box_paragraph_is_a_separate_block(tmp_path):
    d = docx.Document()
    p = d.add_paragraph("Снаружи")
    p._p.append(parse_xml(
        f'<w:r xmlns:w="{W_NS}" xmlns:v="{V_NS}"><w:pict><v:shape><v:textbox><w:txbxContent>'
        f"<w:p><w:r><w:t>Внутри</w:t></w:r></w:p>"
        f"</w:txbxContent></v:textbox></v:shape></w:pict></w:r>"
    ))
    doc = load(save(d, tmp_path))

    assert texts(doc) == ["Снаружи", "Внутри"]

    outer = doc.blocks()[0]
    doc.replace_text(outer.id, "Новое снаружи")
    out = tmp_path / "out.docx"
    doc.save(out)
    assert texts(load(out)) == ["Новое снаружи", "Внутри"]


def test_fallback_copy_of_text_box_is_auxiliary(tmp_path):
    d = docx.Document()
    p = d.add_paragraph("Тело")
    p._p.append(parse_xml(
        f'<w:r xmlns:w="{W_NS}" xmlns:mc="{MC_NS}" xmlns:v="{V_NS}"><mc:AlternateContent>'
        f"<mc:Fallback><w:pict><v:shape><v:textbox><w:txbxContent>"
        f"<w:p><w:r><w:t>Запасная копия</w:t></w:r></w:p>"
        f"</w:txbxContent></v:textbox></v:shape></w:pict></mc:Fallback>"
        f"</mc:AlternateContent></w:r>"
    ))
    doc = load(save(d, tmp_path))

    assert texts(doc, BlockRole.MAIN) == ["Тело"]
    assert texts(doc, BlockRole.AUXILIARY) == ["Запасная копия"]


def test_footnotes_are_read_and_written(tmp_path):
    d = docx.Document()
    d.add_paragraph("Текст")
    path = save(d, tmp_path)
    add_footnotes(path, ["Сноска — пояснение"])
    doc = load(path)

    (note,) = [b for b in doc.blocks() if b.role is BlockRole.AUXILIARY]
    assert note.text == "Сноска — пояснение"

    doc.replace_text(note.id, "Сноска - пояснение")
    out = tmp_path / "out.docx"
    doc.save(out)
    assert "Сноска - пояснение" in part_xml(out, "word/footnotes.xml")


def test_saving_copy_does_not_touch_source(tmp_path):
    d = docx.Document()
    d.add_paragraph("Исходный — текст")
    src = save(d, tmp_path)
    before = hashlib.sha256(src.read_bytes()).hexdigest()

    doc = load(src)
    for block in doc.blocks():
        doc.replace_text(block.id, "Изменено")
    doc.save(tmp_path / "copy.docx")

    assert hashlib.sha256(src.read_bytes()).hexdigest() == before
    assert texts(load(tmp_path / "copy.docx")) == ["Изменено"]


def test_missing_file_raises_document_error(tmp_path):
    with pytest.raises(DocumentError):
        load(tmp_path / "нет.docx")


def test_not_a_docx_raises_document_error(tmp_path):
    bad = tmp_path / "bad.docx"
    bad.write_text("это не ворд")
    with pytest.raises(DocumentError):
        load(bad)


def test_unknown_block_id_raises(tmp_path):
    d = docx.Document()
    d.add_paragraph("x")
    doc = load(save(d, tmp_path))
    with pytest.raises(KeyError):
        doc.replace_text(999, "y")
