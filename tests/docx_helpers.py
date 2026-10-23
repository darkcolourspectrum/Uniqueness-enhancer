"""Утилиты для сборки и независимой проверки .docx в тестах."""

import struct
import zipfile
import zlib
from pathlib import Path

from lxml import etree

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
FOOTNOTES_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"
FOOTNOTES_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes"


def tiny_png() -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    pixels = zlib.compress(b"\x00\xff\x00\x00")
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", pixels) + chunk(b"IEND", b"")


def add_footnotes(docx_path: Path, texts: list[str]) -> None:
    """Дописывает в готовый .docx часть со сносками (python-docx так не умеет)."""
    docx_path = Path(docx_path)
    with zipfile.ZipFile(docx_path) as zin:
        entries = {name: zin.read(name) for name in zin.namelist()}

    notes = "".join(
        f'<w:footnote w:id="{i}"><w:p><w:r><w:t xml:space="preserve">{t}</w:t></w:r></w:p></w:footnote>'
        for i, t in enumerate(texts, start=1)
    )
    entries["word/footnotes.xml"] = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:footnotes xmlns:w="{W_NS}">{notes}</w:footnotes>'
    ).encode("utf-8")
    entries["[Content_Types].xml"] = entries["[Content_Types].xml"].replace(
        b"</Types>",
        f'<Override PartName="/word/footnotes.xml" ContentType="{FOOTNOTES_CT}"/></Types>'.encode(),
    )
    rels = "word/_rels/document.xml.rels"
    entries[rels] = entries[rels].replace(
        b"</Relationships>",
        f'<Relationship Id="rIdFootnotes1" Type="{FOOTNOTES_REL}" Target="footnotes.xml"/>'
        f"</Relationships>".encode(),
    )

    with zipfile.ZipFile(docx_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for name, data in entries.items():
            zout.writestr(name, data)


def all_text_nodes(docx_path: Path) -> dict[str, list[str]]:
    """Все тексты w:t из всех XML-частей пакета — независимо от адаптера."""
    result: dict[str, list[str]] = {}
    with zipfile.ZipFile(docx_path) as z:
        for name in z.namelist():
            if not name.endswith(".xml"):
                continue
            root = etree.fromstring(z.read(name))
            texts = [t.text or "" for t in root.iter(f"{{{W_NS}}}t")]
            if texts:
                result[name] = texts
    return result


def part_xml(docx_path: Path, name: str) -> str:
    with zipfile.ZipFile(docx_path) as z:
        return z.read(name).decode("utf-8")
