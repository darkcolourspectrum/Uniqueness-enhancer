"""Настоящий HTTP-запрос к локальному серверу, имитирующему API Яндекса."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from textuniq.domain.errors import TranslatorUnavailableError
from textuniq.infrastructure.translators.yandex_api import YandexTranslator


class Handler(BaseHTTPRequestHandler):
    received: list[tuple[dict, dict]] = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        Handler.received.append((dict(self.headers), body))
        if self.headers["Authorization"] != "Api-Key good":
            self._reply(401, {"code": 16, "message": "Unknown api key"})
            return
        texts = [f"[{body['targetLanguageCode']}] {t}" for t in body["texts"]]
        self._reply(200, {"translations": [{"text": t, "detectedLanguageCode": "ru"} for t in texts]})

    def _reply(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


@pytest.fixture
def api_url():
    Handler.received = []
    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/translate/v2/translate"
    server.shutdown()


def test_real_http_round_trip(api_url):
    translator = YandexTranslator(api_key="good", api_url=api_url)

    assert translator.translate_batch(["Привет — мир"], "ru", "en") == ["[en] Привет — мир"]
    headers, body = Handler.received[0]
    assert headers["Content-Type"] == "application/json"
    assert body["texts"] == ["Привет — мир"]


def test_real_http_error_body_is_reported(api_url):
    translator = YandexTranslator(api_key="bad", api_url=api_url)

    with pytest.raises(TranslatorUnavailableError, match="Unknown api key"):
        translator.translate_batch(["Привет"], "ru", "en")


def test_unreachable_server_is_reported_after_retries():
    translator = YandexTranslator(
        api_key="good", api_url="http://127.0.0.1:9/nothing", retries=1, sleep=lambda s: None
    )
    with pytest.raises(TranslatorUnavailableError):
        translator.translate_batch(["Привет"], "ru", "en")
