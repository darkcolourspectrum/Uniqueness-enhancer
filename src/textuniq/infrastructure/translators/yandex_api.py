"""Яндекс Переводчик: Translate API v2 (Yandex Cloud / AI Studio).

Аутентификация — API-ключ сервисного аккаунта с ролью ai.translate.user
и областью действия yc.ai.translate.execute. Для сервисного аккаунта
folderId не передаётся; он нужен только при работе от пользовательского аккаунта.
Тексты одного запроса переводятся независимо друг от друга.
Работает на стандартной библиотеке, без дополнительных зависимостей.
"""

import json
import logging
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Sequence

from textuniq.domain.errors import TranslationError, TranslatorUnavailableError

log = logging.getLogger(__name__)

API_URL = "https://translate.api.cloud.yandex.net/translate/v2/translate"
ENV_API_KEY = "YANDEX_API_KEY"
ENV_FOLDER_ID = "YANDEX_FOLDER_ID"
MAX_REQUEST_CHARS = 10_000  # суммарная длина texts в одном запросе
PRICE_RUB_PER_MILLION = 500.4  # с НДС, тариф на октябрь 2026; сверяйте с актуальным


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: dict


Transport = Callable[[str, dict, dict], HttpResponse]


class YandexTranslator:
    max_text_chars = MAX_REQUEST_CHARS  # абзац уходит целиком, если влезает в запрос

    def __init__(
        self,
        api_key: str | None = None,
        folder_id: str | None = None,
        api_url: str = API_URL,
        transport: Transport | None = None,
        retries: int = 3,
        backoff: float = 1.0,
        timeout: float = 30.0,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self._api_key = (api_key or os.environ.get(ENV_API_KEY, "")).strip()
        self._folder_id = (folder_id or os.environ.get(ENV_FOLDER_ID, "")).strip() or None
        if not self._api_key:
            raise TranslatorUnavailableError(
                f"Не задан API-ключ Яндекса. Укажите его в переменной окружения {ENV_API_KEY} "
                f"или в файле .env рядом с проектом (см. README)."
            )
        self._api_url = api_url
        self._transport = transport or _UrllibTransport(timeout)
        self._retries = retries
        self._backoff = backoff
        self._sleep = sleep
        self.chars_sent = 0

    def translate_batch(self, texts: Sequence[str], source: str, target: str) -> list[str]:
        result: list[str] = []
        for group in _pack(list(texts), MAX_REQUEST_CHARS):
            result.extend(self._request(group, source, target))
        return result

    def usage(self) -> str | None:
        if not self.chars_sent:
            return None
        cost = self.chars_sent / 1_000_000 * PRICE_RUB_PER_MILLION
        return (
            f"Яндекс Переводчик: отправлено {self.chars_sent:,} символов за запуск "
            f"(≈ {cost:.2f} ₽ по тарифу {PRICE_RUB_PER_MILLION} ₽ за 1 млн)"
        ).replace(",", " ")

    def _request(self, texts: list[str], source: str, target: str) -> list[str]:
        payload = {
            "sourceLanguageCode": source,
            "targetLanguageCode": target,
            "format": "PLAIN_TEXT",
            "texts": texts,
        }
        if self._folder_id:
            payload["folderId"] = self._folder_id
        headers = {"Authorization": f"Api-Key {self._api_key}", "Content-Type": "application/json"}

        last_error = ""
        for attempt in range(self._retries + 1):
            if attempt:
                self._sleep(self._backoff * 2 ** (attempt - 1))
            try:
                response = self._transport(self._api_url, headers, payload)
            except OSError as exc:  # сеть, таймаут, DNS
                last_error = str(exc)
                log.debug("Яндекс: попытка %s не удалась: %s", attempt + 1, exc)
                continue

            if response.status == 200:
                return self._parse(response.body, texts)
            message = _error_message(response.body)
            if response.status in (401, 403):
                raise TranslatorUnavailableError(
                    f"Яндекс отклонил запрос ({response.status}): {message}. Проверьте ключ, "
                    f"роль ai.translate.user у сервисного аккаунта и область действия ключа "
                    f"yc.ai.translate.execute."
                )
            if response.status == 429 or response.status >= 500:
                last_error = f"{response.status}: {message}"
                log.debug("Яндекс: попытка %s, ответ %s", attempt + 1, last_error)
                continue
            raise TranslationError(f"Яндекс вернул ошибку {response.status}: {message}")

        raise TranslatorUnavailableError(f"Яндекс Переводчик недоступен: {last_error}")

    def _parse(self, body: dict, texts: list[str]) -> list[str]:
        translations = body.get("translations") or []
        if len(translations) != len(texts):
            raise TranslationError(
                f"Яндекс вернул {len(translations)} переводов вместо {len(texts)}"
            )
        self.chars_sent += sum(len(t) for t in texts)
        return [item.get("text", "") for item in translations]


class _UrllibTransport:
    def __init__(self, timeout: float):
        self.timeout = timeout

    def __call__(self, url: str, headers: dict, payload: dict) -> HttpResponse:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return HttpResponse(response.status, _json(response.read()))
        except urllib.error.HTTPError as err:
            return HttpResponse(err.code, _json(err.read()))


def _json(raw: bytes) -> dict:
    try:
        parsed = json.loads(raw or b"{}")
    except ValueError:
        return {"message": raw.decode("utf-8", "replace")[:500]}
    return parsed if isinstance(parsed, dict) else {"message": str(parsed)}


def _error_message(body: dict) -> str:
    return str(body.get("message") or body.get("error") or body or "без описания")


def _pack(texts: list[str], limit: int) -> list[list[str]]:
    groups: list[list[str]] = []
    current: list[str] = []
    size = 0
    for text in texts:
        if current and size + len(text) > limit:
            groups.append(current)
            current, size = [], 0
        current.append(text)
        size += len(text)
    if current:
        groups.append(current)
    return groups
