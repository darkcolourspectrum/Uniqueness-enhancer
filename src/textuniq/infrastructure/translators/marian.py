"""MarianMT (OPUS-MT, лицензия CC-BY 4.0): отдельная модель на каждую пару языков."""

from dataclasses import dataclass

from textuniq.domain.errors import TranslatorUnavailableError
from textuniq.infrastructure.translators.transformers_base import (
    GenerationPlan,
    TransformersTranslator,
)


@dataclass(frozen=True)
class MarianModel:
    name: str
    prefix: str = ""  # для многоязычных моделей: токен целевого языка, напр. ">>rus<< "


DEFAULT_MARIAN_MODELS: dict[tuple[str, str], MarianModel] = {
    ("ru", "en"): MarianModel("Helsinki-NLP/opus-mt-ru-en"),
    ("en", "ru"): MarianModel("Helsinki-NLP/opus-mt-en-ru"),
    ("en", "de"): MarianModel("Helsinki-NLP/opus-mt-en-de"),
    ("de", "en"): MarianModel("Helsinki-NLP/opus-mt-de-en"),
    # Прямой модели de→ru в OPUS-MT нет, берём de→восточнославянские с выбором русского.
    ("de", "ru"): MarianModel("Helsinki-NLP/opus-mt-tc-big-de-zle", prefix=">>rus<< "),
    ("ru", "de"): MarianModel("Helsinki-NLP/opus-mt-tc-big-zle-de"),
}


class MarianTranslator(TransformersTranslator):
    def __init__(self, models: dict[tuple[str, str], MarianModel] | None = None, **options):
        super().__init__(**options)
        self.models = dict(DEFAULT_MARIAN_MODELS if models is None else models)

    def plan(self, source: str, target: str) -> GenerationPlan:
        spec = self.models.get((source, target))
        if spec is None:
            supported = ", ".join(f"{s}→{t}" for s, t in sorted(self.models))
            raise TranslatorUnavailableError(
                f"Marian: нет модели для {source}→{target}. Доступно: {supported}"
            )
        return GenerationPlan(model_name=spec.name, prefix=spec.prefix)
