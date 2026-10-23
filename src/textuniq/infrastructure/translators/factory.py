from typing import Any, Callable

from textuniq.application.ports import Translator
from textuniq.domain.errors import TranslatorUnavailableError
from textuniq.infrastructure.translators.identity import IdentityTranslator
from textuniq.infrastructure.translators.marian import MarianTranslator
from textuniq.infrastructure.translators.nllb import NllbTranslator
from textuniq.infrastructure.translators.yandex_api import YandexTranslator

_LOCAL_OPTIONS = ("device", "num_beams", "batch_size", "local_files_only")


def _pick(options: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: options[key] for key in keys if key in options}


def _no_model(options: dict[str, Any], engine: str) -> None:
    if options.get("model"):
        raise TranslatorUnavailableError(f"Параметр model не поддерживается движком {engine} (только nllb)")


def _marian(options: dict[str, Any]) -> Translator:
    _no_model(options, "marian")
    return MarianTranslator(**_pick(options, _LOCAL_OPTIONS))


def _nllb(options: dict[str, Any]) -> Translator:
    kwargs = _pick(options, _LOCAL_OPTIONS)
    if options.get("model"):
        kwargs["model_name"] = options["model"]
    return NllbTranslator(**kwargs)


def _yandex(options: dict[str, Any]) -> Translator:
    _no_model(options, "yandex")
    return YandexTranslator()


def _identity(options: dict[str, Any]) -> Translator:
    return IdentityTranslator()


ENGINES: dict[str, Callable[[dict[str, Any]], Translator]] = {
    "marian": _marian,
    "nllb": _nllb,
    "yandex": _yandex,
    "identity": _identity,
}


def create_translator(engine: str, **options: Any) -> Translator:
    try:
        builder = ENGINES[engine]
    except KeyError:
        raise TranslatorUnavailableError(
            f"Неизвестный движок «{engine}». Доступно: {', '.join(ENGINES)}"
        ) from None
    return builder({k: v for k, v in options.items() if v is not None})
