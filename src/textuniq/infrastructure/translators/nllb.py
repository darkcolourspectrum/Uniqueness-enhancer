"""NLLB-200 (Meta): одна многоязычная модель на все направления.

Внимание: веса NLLB распространяются по лицензии CC-BY-NC 4.0 (некоммерческая).
"""

from textuniq.domain.errors import TranslatorUnavailableError
from textuniq.infrastructure.translators.transformers_base import (
    GenerationPlan,
    TransformersTranslator,
)

DEFAULT_NLLB_MODEL = "facebook/nllb-200-distilled-600M"

NLLB_CODES = {
    "ru": "rus_Cyrl",
    "en": "eng_Latn",
    "de": "deu_Latn",
    "fr": "fra_Latn",
    "es": "spa_Latn",
    "it": "ita_Latn",
    "uk": "ukr_Cyrl",
    "pl": "pol_Latn",
}


class NllbTranslator(TransformersTranslator):
    def __init__(self, model_name: str = DEFAULT_NLLB_MODEL, codes: dict[str, str] | None = None, **options):
        super().__init__(**options)
        self.model_name = model_name
        self.codes = dict(NLLB_CODES if codes is None else codes)

    def plan(self, source: str, target: str) -> GenerationPlan:
        try:
            src, tgt = self.codes[source], self.codes[target]
        except KeyError as exc:
            raise TranslatorUnavailableError(
                f"NLLB: неизвестный язык {exc}. Доступно: {', '.join(sorted(self.codes))}"
            ) from exc
        return GenerationPlan(
            model_name=self.model_name,
            tokenizer_attrs={"src_lang": src},
            forced_bos_token=tgt,
        )
