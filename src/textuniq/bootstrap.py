"""Корень композиции: собирает слои в готовые сценарии.

CLI сейчас и веб-сервис потом используют одни и те же функции сборки.
"""

from dataclasses import dataclass, field

from textuniq.application.ports import Translator
from textuniq.application.processing import BlockProcessor
from textuniq.application.translation import ChainTranslator, SegmentingTranslator
from textuniq.application.uniquify import UniquifyDocument
from textuniq.domain.models import TranslationChain
from textuniq.infrastructure.docx_document import DocxDocumentLoader
from textuniq.infrastructure.translators import create_translator


@dataclass
class Settings:
    engine: str = "marian"
    chain: TranslationChain = field(default_factory=TranslationChain.default)
    # локальные модели
    device: str = "auto"
    num_beams: int = 4
    batch_size: int = 8
    max_chunk_chars: int = 600
    model: str | None = None
    local_files_only: bool = False


def build_translator(settings: Settings) -> Translator:
    translator = create_translator(
        settings.engine,
        device=settings.device,
        num_beams=settings.num_beams,
        batch_size=settings.batch_size,
        local_files_only=settings.local_files_only,
        model=settings.model,
    )
    _check_chain_supported(translator, settings.chain)
    return translator


def build_chain_translator(settings: Settings, translator: Translator | None = None) -> ChainTranslator:
    translator = translator or build_translator(settings)
    # Переводчик может сам объявить лимит длины текста (облачные API — свой лимит запроса,
    # None — без лимита). Локальным моделям длинный абзац подаём кусками из настроек.
    limit = getattr(translator, "max_text_chars", settings.max_chunk_chars)
    if limit:
        translator = SegmentingTranslator(translator, max_chars=limit)
    return ChainTranslator(translator, settings.chain)


def build_uniquify(settings: Settings, translator: Translator | None = None) -> UniquifyDocument:
    processor = BlockProcessor(build_chain_translator(settings, translator))
    return UniquifyDocument(DocxDocumentLoader(), processor)


def _check_chain_supported(translator: Translator, chain: TranslationChain) -> None:
    """Проверяем пары языков до загрузки моделей, чтобы падать сразу, а не на середине."""
    plan = getattr(translator, "plan", None)
    if plan is None:
        return
    for source, target in chain.steps:
        plan(source, target)
