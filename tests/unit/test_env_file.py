import os

from textuniq.interfaces.env_file import load_env_file


def test_loads_values_without_overriding_existing(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(
        "# комментарий\n"
        "TEXTUNIQ_KEY = \"abc:def\"\n"
        "EMPTY=\n"
        "ALREADY=from_file\n"
        "broken line\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("TEXTUNIQ_KEY", raising=False)
    monkeypatch.delenv("EMPTY", raising=False)
    monkeypatch.setenv("ALREADY", "from_env")

    assert load_env_file(env) is True

    assert os.environ.pop("TEXTUNIQ_KEY") == "abc:def"
    assert os.environ["EMPTY"] == ""
    assert os.environ["ALREADY"] == "from_env"


def test_missing_file_is_ignored(tmp_path):
    assert load_env_file(tmp_path / ".env") is False
