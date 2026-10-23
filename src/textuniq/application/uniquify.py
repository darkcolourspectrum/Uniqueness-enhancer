from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from textuniq.application.output_path import default_output_path
from textuniq.application.ports import DocumentLoader
from textuniq.application.processing import BlockProcessor, BlockResult, BlockStatus
from textuniq.domain.errors import DocumentError
from textuniq.domain.models import TextBlock

ProgressCallback = Callable[[int, int, TextBlock, BlockResult], None]


@dataclass
class ProcessingSummary:
    output: Path
    total: int = 0
    translated: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[tuple[int, str]] = field(default_factory=list)


class UniquifyDocument:
    """Сценарий: открыть документ, обработать каждый абзац, сохранить копию."""

    def __init__(self, loader: DocumentLoader, processor: BlockProcessor):
        self._loader = loader
        self._processor = processor

    def execute(
        self,
        source: Path,
        target: Path | None = None,
        on_block: ProgressCallback | None = None,
    ) -> ProcessingSummary:
        source = Path(source)
        target = Path(target) if target else default_output_path(source)
        if _same_file(source, target):
            raise DocumentError("Выходной файл совпадает с исходным: исходник менять нельзя")

        document = self._loader.load(source)
        blocks = document.blocks()
        summary = ProcessingSummary(output=target, total=len(blocks))

        for index, block in enumerate(blocks, start=1):
            result = self._processor.process(block)
            if result.text != block.text:
                document.replace_text(block.id, result.text)
            _count(summary, block, result)
            if on_block:
                on_block(index, len(blocks), block, result)

        target.parent.mkdir(parents=True, exist_ok=True)
        document.save(target)
        return summary


def _same_file(a: Path, b: Path) -> bool:
    return a.resolve() == b.resolve()


def _count(summary: ProcessingSummary, block: TextBlock, result: BlockResult) -> None:
    if result.status is BlockStatus.TRANSLATED:
        summary.translated += 1
    elif result.status is BlockStatus.FAILED:
        summary.failed += 1
        summary.errors.append((block.id, result.error or ""))
    else:
        summary.skipped += 1
