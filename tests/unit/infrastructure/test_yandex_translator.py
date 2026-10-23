import pytest

from textuniq.domain.errors import TranslationError, TranslatorUnavailableError
from textuniq.infrastructure.translators.yandex_api import (
    ENV_API_KEY,
    ENV_FOLDER_ID,
    MAX_REQUEST_CHARS,
    HttpResponse,
    YandexTranslator,
)


class FakeTransport:
    """Отвечает по очереди заготовленными статусами; 200 — «перевод» с пометкой языка."""

    def __init__(self, statuses=(200,), error_body=None):
        self.statuses = list(statuses)
        self.error_body = error_body or {"code": 3, "message": "что-то не так"}
        self.requests: list[tuple[str, dict, dict]] = []

    def __call__(self, url, headers, payload):
        self.requests.append((url, headers, payload))
        status = self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
        if isinstance(status, Exception):
            raise status
        if status != 200:
            return HttpResponse(status, self.error_body)
        target = payload["targetLanguageCode"]
        return HttpResponse(200, {"translations": [{"text": f"<{target}>{t}"} for t in payload["texts"]]})


def make(transport=None, **kwargs):
    transport = transport or FakeTransport()
    kwargs.setdefault("api_key", "секрет")
    return YandexTranslator(transport=transport, sleep=lambda s: None, **kwargs), transport


def test_request_format_for_service_account_key():
    translator, transport = make()

    result = translator.translate_batch(["Привет", "Мир"], "ru", "en")

    assert result == ["<en>Привет", "<en>Мир"]
    (url, headers, payload), = transport.requests
    assert url == "https://translate.api.cloud.yandex.net/translate/v2/translate"
    assert headers["Authorization"] == "Api-Key секрет"
    assert payload == {
        "sourceLanguageCode": "ru",
        "targetLanguageCode": "en",
        "format": "PLAIN_TEXT",
        "texts": ["Привет", "Мир"],
    }


def test_folder_id_is_sent_only_when_configured():
    translator, transport = make(folder_id="b1gfolder")
    translator.translate_batch(["Привет"], "ru", "en")
    assert transport.requests[0][2]["folderId"] == "b1gfolder"


def test_empty_batch_makes_no_request():
    translator, transport = make()
    assert translator.translate_batch([], "ru", "en") == []
    assert transport.requests == []


def test_large_batch_is_split_into_requests_under_the_limit():
    translator, transport = make()
    texts = ["а" * 4000, "б" * 4000, "в" * 4000]

    result = translator.translate_batch(texts, "ru", "en")

    assert result == [f"<en>{t}" for t in texts]
    sizes = [sum(map(len, payload["texts"])) for _, _, payload in transport.requests]
    assert len(sizes) == 2 and all(size <= MAX_REQUEST_CHARS for size in sizes)


@pytest.mark.parametrize("status", [401, 403])
def test_auth_errors_stop_the_run(status):
    translator, transport = make(FakeTransport([status]))
    with pytest.raises(TranslatorUnavailableError, match="ai.translate.user"):
        translator.translate_batch(["Привет"], "ru", "en")
    assert len(transport.requests) == 1


def test_bad_request_fails_only_this_text():
    translator, _ = make(FakeTransport([400]))
    with pytest.raises(TranslationError, match="что-то не так"):
        translator.translate_batch(["Привет"], "ru", "en")


@pytest.mark.parametrize("failure", [429, 503, OSError("сеть упала")])
def test_temporary_failures_are_retried(failure):
    translator, transport = make(FakeTransport([failure, failure, 200]))

    assert translator.translate_batch(["Привет"], "ru", "en") == ["<en>Привет"]
    assert len(transport.requests) == 3


def test_gives_up_after_retries():
    translator, transport = make(FakeTransport([503]), retries=2)
    with pytest.raises(TranslatorUnavailableError):
        translator.translate_batch(["Привет"], "ru", "en")
    assert len(transport.requests) == 3


def test_wrong_number_of_translations_is_an_error():
    def transport(url, headers, payload):
        return HttpResponse(200, {"translations": []})

    translator = YandexTranslator(api_key="k", transport=transport)
    with pytest.raises(TranslationError):
        translator.translate_batch(["Привет"], "ru", "en")


def test_missing_key_fails_immediately(monkeypatch):
    monkeypatch.delenv(ENV_API_KEY, raising=False)
    with pytest.raises(TranslatorUnavailableError, match=ENV_API_KEY):
        YandexTranslator()


def test_key_and_folder_from_environment(monkeypatch):
    monkeypatch.setenv(ENV_API_KEY, "из-окружения")
    monkeypatch.setenv(ENV_FOLDER_ID, "папка")
    transport = FakeTransport()

    YandexTranslator(transport=transport).translate_batch(["Привет"], "ru", "en")

    _, headers, payload = transport.requests[0]
    assert headers["Authorization"] == "Api-Key из-окружения"
    assert payload["folderId"] == "папка"


def test_usage_counts_sent_characters():
    translator, _ = make()
    assert translator.usage() is None

    translator.translate_batch(["Привет", "Мир"], "ru", "en")

    assert translator.usage().startswith("Яндекс Переводчик: отправлено 9 символов")


def test_paragraphs_go_whole_up_to_request_limit():
    assert YandexTranslator.max_text_chars == MAX_REQUEST_CHARS
