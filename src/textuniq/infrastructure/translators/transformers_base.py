"""Общая часть офлайн-переводчиков на HuggingFace transformers.

torch и transformers импортируются лениво: ядро и тесты работают без них.
Модели скачиваются один раз в кэш HuggingFace, дальше всё работает офлайн
(можно включить строгий офлайн через local_files_only или HF_HUB_OFFLINE=1).
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Sequence

from textuniq.domain.errors import TranslationError, TranslatorUnavailableError

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class GenerationPlan:
    model_name: str
    prefix: str = ""
    tokenizer_attrs: dict[str, Any] = field(default_factory=dict)
    forced_bos_token: str | None = None


class TransformersTranslator:
    def __init__(
        self,
        device: str = "auto",
        num_beams: int = 4,
        batch_size: int = 8,
        max_input_tokens: int = 512,
        cache_dir: str | None = None,
        local_files_only: bool = False,
    ):
        self.device_name = device
        self.num_beams = num_beams
        self.batch_size = batch_size
        self.max_input_tokens = max_input_tokens
        self.cache_dir = cache_dir
        self.local_files_only = local_files_only
        self._models: dict[str, tuple[Any, Any]] = {}
        self._device = None

    def plan(self, source: str, target: str) -> GenerationPlan:
        raise NotImplementedError

    def translate_batch(self, texts: Sequence[str], source: str, target: str) -> list[str]:
        if not texts:
            return []
        plan = self.plan(source, target)
        tokenizer, model = self._load(plan.model_name)
        for attr, value in plan.tokenizer_attrs.items():
            setattr(tokenizer, attr, value)

        gen_kwargs: dict[str, Any] = {}
        if plan.forced_bos_token:
            gen_kwargs["forced_bos_token_id"] = tokenizer.convert_tokens_to_ids(plan.forced_bos_token)

        result: list[str] = []
        for start in range(0, len(texts), self.batch_size):
            batch = [plan.prefix + text for text in texts[start:start + self.batch_size]]
            result.extend(self._generate(tokenizer, model, batch, gen_kwargs))
        return result

    def _generate(self, tokenizer, model, batch: list[str], gen_kwargs: dict) -> list[str]:
        torch = _import("torch")
        try:
            inputs = tokenizer(
                batch,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=self.max_input_tokens,
            ).to(self._device)
            input_len = inputs["input_ids"].shape[1]
            with torch.inference_mode():
                output = model.generate(
                    **inputs,
                    num_beams=self.num_beams,
                    max_new_tokens=min(self.max_input_tokens, input_len * 2 + 16),
                    **gen_kwargs,
                )
            return tokenizer.batch_decode(output, skip_special_tokens=True)
        except Exception as exc:  # ошибки генерации не должны ронять весь документ
            raise TranslationError(f"Ошибка генерации: {exc}") from exc

    def _load(self, model_name: str):
        if model_name in self._models:
            return self._models[model_name]
        transformers = _import("transformers")
        torch = _import("torch")
        if self._device is None:
            self._device = _resolve_device(torch, self.device_name)

        log.info("Загружаю модель %s (%s)…", model_name, self._device)
        options = {"cache_dir": self.cache_dir, "local_files_only": self.local_files_only}
        try:
            tokenizer = transformers.AutoTokenizer.from_pretrained(model_name, **options)
            model = transformers.AutoModelForSeq2SeqLM.from_pretrained(model_name, **options)
        except (OSError, ValueError) as exc:
            raise TranslatorUnavailableError(
                f"Не удалось загрузить модель «{model_name}». При первом запуске нужен интернет "
                f"для скачивания в кэш, дальше работа офлайн. Причина: {exc}"
            ) from exc
        model.to(self._device).eval()
        self._models[model_name] = (tokenizer, model)
        return tokenizer, model


def _resolve_device(torch, name: str):
    if name != "auto":
        return torch.device(name)
    if torch.cuda.is_available():
        return torch.device("cuda")
    mps = getattr(torch.backends, "mps", None)
    if mps is not None and mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def _import(module: str):
    try:
        return __import__(module)
    except ImportError as exc:
        raise TranslatorUnavailableError(
            f"Не установлен пакет «{module}». Установите ML-зависимости: pip install -e \".[ml]\""
        ) from exc
