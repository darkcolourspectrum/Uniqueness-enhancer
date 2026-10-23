import logging
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Iterable

from textuniq.application.ports import TextTranslator
from textuniq.domain.dashes import normalize_dashes
from textuniq.domain.errors import TranslationError
from textuniq.domain.models import BlockRole, TextBlock
from textuniq.domain.text import is_translatable, split_edges

log = logging.getLogger(__name__)

TextRule = Callable[[str], str]

DEFAULT_RULES: tuple[TextRule, ...] = (normalize_dashes,)


class BlockStatus(Enum):
    TRANSLATED = "translated"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True)
class BlockResult:
    text: str
    status: BlockStatus
    error: str | None = None


class BlockProcessor:
    """Обработка одного абзаца: перевод по цепочке, затем правила очистки.

    Правила очистки (сейчас только тире) применяются ко всем абзацам
    и всегда после перевода, иначе переводчик вернёт тире обратно.
    """

    def __init__(
        self,
        translator: TextTranslator | None,
        rules: Iterable[TextRule] = DEFAULT_RULES,
        translate_roles: Iterable[BlockRole] = (BlockRole.MAIN,),
    ):
        self._translator = translator
        self._rules = tuple(rules)
        self._translate_roles = frozenset(translate_roles)

    def process(self, block: TextBlock) -> BlockResult:
        text, status, error = block.text, BlockStatus.SKIPPED, None

        if self._should_translate(block):
            lead, core, trail = split_edges(block.text)
            try:
                text = lead + self._translator.translate(core) + trail
                status = BlockStatus.TRANSLATED
            except TranslationError as exc:
                log.warning("Абзац %s не переведён: %s", block.id, exc)
                status, error = BlockStatus.FAILED, str(exc)

        return BlockResult(self._apply_rules(text), status, error)

    def _should_translate(self, block: TextBlock) -> bool:
        return (
            self._translator is not None
            and block.role in self._translate_roles
            and is_translatable(block.text)
        )

    def _apply_rules(self, text: str) -> str:
        for rule in self._rules:
            text = rule(text)
        return text
