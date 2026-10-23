"""Адаптер Word (.docx): абзацы документа ↔ TextBlock.

Работаем напрямую с XML-абзацами (w:p) всех текстовых частей пакета:
основной текст (включая таблицы и надписи), колонтитулы, сноски, примечания.
Форматирование внутри абзаца по возможности сохраняется, но не гарантируется.
"""

from dataclasses import dataclass
from pathlib import Path

import docx
from docx.opc.constants import CONTENT_TYPE as CT
from docx.opc.exceptions import PackageNotFoundError
from docx.opc.part import PartFactory, XmlPart
from docx.oxml.ns import qn

from textuniq.domain.errors import DocumentError
from textuniq.domain.models import BlockRole, TextBlock

_XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
_MC_FALLBACK = "{http://schemas.openxmlformats.org/markup-compatibility/2006}Fallback"

W_P, W_R, W_T = qn("w:p"), qn("w:r"), qn("w:t")
W_BR = qn("w:br")

# Невидимые для python-docx части со сносками разбираем как XML.
for _ct in (CT.WML_FOOTNOTES, CT.WML_ENDNOTES):
    PartFactory.part_type_for.setdefault(_ct, XmlPart)

_MAIN_TYPES = {CT.WML_DOCUMENT_MAIN}
_AUX_TYPES = {CT.WML_HEADER, CT.WML_FOOTER, CT.WML_FOOTNOTES, CT.WML_ENDNOTES, CT.WML_COMMENTS}

# Элементы внутри w:r, которые Word показывает как символы.
_SPECIAL_TEXT = {
    qn("w:tab"): " ",
    qn("w:br"): " ",
    qn("w:cr"): " ",
    qn("w:noBreakHyphen"): "-",
    qn("w:softHyphen"): "",
}


@dataclass
class _Segment:
    element: object
    text: str
    is_text_node: bool


class DocxDocumentLoader:
    def load(self, path: Path) -> "DocxDocument":
        path = Path(path)
        if not path.is_file():
            raise DocumentError(f"Файл не найден: {path}")
        try:
            document = docx.Document(str(path))
        except (PackageNotFoundError, ValueError, KeyError) as exc:
            raise DocumentError(f"Не удалось открыть как .docx: {path} ({exc})") from exc
        return DocxDocument(document)


class DocxDocument:
    def __init__(self, document):
        self._document = document
        self._paragraphs: dict[int, tuple[object, BlockRole]] = {}
        for p, role in _iter_paragraphs(document):
            self._paragraphs[len(self._paragraphs) + 1] = (p, role)

    def blocks(self) -> list[TextBlock]:
        return [
            TextBlock(block_id, _paragraph_text(p), role)
            for block_id, (p, role) in self._paragraphs.items()
        ]

    def replace_text(self, block_id: int, text: str) -> None:
        p, _ = self._paragraphs[block_id]
        _write_paragraph(p, text)

    def save(self, path: Path) -> None:
        self._document.save(str(path))


def _iter_paragraphs(document):
    parts = list(document.part.package.iter_parts())
    main = [part for part in parts if part.content_type in _MAIN_TYPES]
    aux = [part for part in parts if part.content_type in _AUX_TYPES]

    for part in main:
        for p in part.element.iter(W_P):
            in_fallback = any(True for _ in p.iterancestors(_MC_FALLBACK))
            yield p, BlockRole.AUXILIARY if in_fallback else BlockRole.MAIN
    for part in aux:
        if hasattr(part, "element"):
            for p in part.element.iter(W_P):
                yield p, BlockRole.AUXILIARY


def _segments(p) -> list[_Segment]:
    """Текстовые элементы абзаца по порядку, без вложенных абзацев (надписей)."""
    result: list[_Segment] = []

    def walk(element):
        for child in element:
            tag = child.tag
            if not isinstance(tag, str) or tag == W_P:
                continue
            if tag == W_T:
                result.append(_Segment(child, child.text or "", True))
            elif tag in _SPECIAL_TEXT and child.getparent().tag == W_R:
                result.append(_Segment(child, _SPECIAL_TEXT[tag], False))
            else:
                walk(child)

    walk(p)
    return result


def _paragraph_text(p) -> str:
    return "".join(seg.text for seg in _segments(p))


def _write_paragraph(p, new_text: str) -> None:
    segments = _segments(p)
    old_text = "".join(seg.text for seg in segments)
    if new_text == old_text:
        return
    if len(new_text) == len(old_text) and _write_in_place(segments, new_text):
        return
    _collapse(p, segments, new_text)


def _write_in_place(segments: list[_Segment], new_text: str) -> bool:
    """Посимвольная замена (например, тире → дефис) без потери форматирования."""
    slices, pos = [], 0
    for seg in segments:
        piece = new_text[pos:pos + len(seg.text)]
        if not seg.is_text_node and piece != seg.text:
            return False
        slices.append(piece)
        pos += len(seg.text)
    for seg, piece in zip(segments, slices):
        if seg.is_text_node:
            _set_text(seg.element, piece)
    return True


def _collapse(p, segments: list[_Segment], new_text: str) -> None:
    """Весь новый текст — в первый текстовый узел, остальные очищаются."""
    text_nodes = [seg.element for seg in segments if seg.is_text_node]
    for seg in segments:
        if not seg.is_text_node and _removable(seg.element):
            seg.element.getparent().remove(seg.element)

    if not text_nodes:
        run = p.makeelement(W_R, {})
        run.append(run.makeelement(W_T, {}))
        p.append(run)
        text_nodes = [run[0]]

    _set_text(text_nodes[0], new_text)
    for node in text_nodes[1:]:
        _set_text(node, "")


def _removable(element) -> bool:
    if element.tag != W_BR:
        return True
    return element.get(qn("w:type")) in (None, "textWrapping")


def _set_text(node, value: str) -> None:
    node.text = value
    node.set(_XML_SPACE, "preserve")
