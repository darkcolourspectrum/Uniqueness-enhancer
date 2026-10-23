import argparse
import logging
import sys
import time
from pathlib import Path

from textuniq.application.processing import BlockResult, BlockStatus
from textuniq.bootstrap import Settings, build_chain_translator, build_translator, build_uniquify
from textuniq.domain.dashes import normalize_dashes
from textuniq.domain.errors import TextUniqError
from textuniq.domain.models import TextBlock, TranslationChain
from textuniq.domain.text import is_translatable
from textuniq.infrastructure.translators import ENGINES
from textuniq.interfaces.env_file import load_env_file

_STATUS = {
    BlockStatus.TRANSLATED: "переведён",
    BlockStatus.SKIPPED: "пропущен",
    BlockStatus.FAILED: "ОШИБКА",
}


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    _setup_output(args.verbose)
    load_env_file(Path.cwd() / ".env")
    try:
        settings = _settings(args)
    except ValueError as exc:
        print(f"Ошибка параметров: {exc}", file=sys.stderr)
        return 2
    try:
        if args.command == "doc":
            return _run_doc(args, settings)
        return _run_text(args, settings)
    except TextUniqError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1


def _run_doc(args, settings: Settings) -> int:
    translator = build_translator(settings)
    use_case = build_uniquify(settings, translator)
    print(f"Файл: {args.input}\nЦепочка: {settings.chain}, движок: {settings.engine}", file=sys.stderr)
    started = time.monotonic()

    def on_block(index: int, total: int, block: TextBlock, result: BlockResult) -> None:
        if not block.text.strip():
            return
        print(f"[{index}/{total}] {_STATUS[result.status]}", file=sys.stderr)
        if args.show and result.status is not BlockStatus.SKIPPED:
            print(f"  было:  {block.text}\n  стало: {result.text}\n")

    summary = use_case.execute(Path(args.input), Path(args.output) if args.output else None, on_block)

    print(
        f"\nГотово за {time.monotonic() - started:.1f} с: переведено {summary.translated}, "
        f"пропущено {summary.skipped}, ошибок {summary.failed}.\nРезультат: {summary.output}",
        file=sys.stderr,
    )
    for block_id, error in summary.errors:
        print(f"  абзац {block_id}: {error}", file=sys.stderr)
    _print_usage(translator)
    return 0


def _run_text(args, settings: Settings) -> int:
    text = sys.stdin.read() if args.text == "-" else args.text
    if not is_translatable(text):
        print(normalize_dashes(text))
        return 0
    translator = build_translator(settings)
    print(normalize_dashes(build_chain_translator(settings, translator).translate(text.strip())))
    _print_usage(translator)
    return 0


def _print_usage(translator) -> None:
    usage = getattr(translator, "usage", None)
    report = usage() if usage else None
    if report:
        print(report, file=sys.stderr)


def _settings(args) -> Settings:
    return Settings(
        engine=args.engine,
        chain=TranslationChain.parse(args.chain),
        device=args.device,
        num_beams=args.beams,
        batch_size=args.batch_size,
        max_chunk_chars=args.max_chunk,
        model=args.model,
        local_files_only=args.offline,
    )


def _parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--engine", choices=list(ENGINES), default="marian",
                        help="движок перевода: marian, nllb (локальные), yandex (облако, ключ "
                             "в YANDEX_API_KEY или в файле .env), identity (без перевода, для отладки)")
    common.add_argument("--chain", default="ru,en,de,ru", help="цепочка языков через запятую")
    common.add_argument("-v", "--verbose", action="store_true", help="подробный лог, включая каждый шаг цепочки")

    local = common.add_argument_group("локальные модели (marian, nllb)")
    local.add_argument("--device", default="auto", help="auto, cpu, cuda, mps")
    local.add_argument("--beams", type=int, default=4, help="ширина beam search")
    local.add_argument("--batch-size", type=int, default=8)
    local.add_argument("--max-chunk", type=int, default=600,
                       help="макс. длина куска абзаца в символах для одного запроса к модели")
    local.add_argument("--model", help="имя или путь модели (только для nllb)")
    local.add_argument("--offline", action="store_true",
                       help="не обращаться в интернет, брать модели только из кэша")

    parser = argparse.ArgumentParser(
        prog="textuniq",
        description="Повышение уникальности текста: перевод по цепочке языков и замена тире.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    doc = sub.add_parser("doc", parents=[common], help="обработать Word-файл (.docx)")
    doc.add_argument("input", help="исходный .docx (не изменяется)")
    doc.add_argument("-o", "--output", help="куда сохранить копию (по умолчанию <имя>_uniq.docx рядом)")
    doc.add_argument("--show", action="store_true", help="печатать каждый абзац: было / стало")

    text = sub.add_parser("text", parents=[common], help="прогнать по цепочке произвольный текст")
    text.add_argument("text", help="текст или «-» для чтения из stdin")
    return parser


def _setup_output(verbose: bool) -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger = logging.getLogger("textuniq")
    logger.handlers[:] = [handler]
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.propagate = False


if __name__ == "__main__":
    sys.exit(main())
