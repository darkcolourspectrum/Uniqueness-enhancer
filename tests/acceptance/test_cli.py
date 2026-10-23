import shutil
from pathlib import Path

from docx_helpers import all_text_nodes
from textuniq.domain.dashes import contains_dashes
from textuniq.interfaces.cli import main

SAMPLE = Path(__file__).resolve().parents[2] / "samples" / "sample_article.docx"


def test_doc_command_with_identity_engine(tmp_path, capsys):
    src = tmp_path / "in.docx"
    shutil.copy(SAMPLE, src)

    code = main(["doc", str(src), "--engine", "identity", "--show"])

    out = tmp_path / "in_uniq.docx"
    assert code == 0
    assert out.exists()
    assert not any(contains_dashes(t) for texts in all_text_nodes(out).values() for t in texts)
    captured = capsys.readouterr()
    assert "было:" in captured.out
    assert str(out) in captured.err


def test_doc_command_custom_output(tmp_path):
    src = tmp_path / "in.docx"
    shutil.copy(SAMPLE, src)
    target = tmp_path / "out" / "result.docx"

    assert main(["doc", str(src), "-o", str(target), "--engine", "identity"]) == 0
    assert target.exists()


def test_doc_command_refuses_to_overwrite_source(tmp_path, capsys):
    src = tmp_path / "in.docx"
    shutil.copy(SAMPLE, src)

    assert main(["doc", str(src), "-o", str(src), "--engine", "identity"]) == 1
    assert "исходн" in capsys.readouterr().err


def test_missing_file_is_reported(tmp_path, capsys):
    assert main(["doc", str(tmp_path / "нет.docx"), "--engine", "identity"]) == 1
    assert "не найден" in capsys.readouterr().err


def test_bad_chain_is_reported(tmp_path, capsys):
    assert main(["text", "Привет", "--chain", "ru,en", "--engine", "identity"]) == 2


def test_unsupported_pair_fails_before_processing(tmp_path, capsys):
    src = tmp_path / "in.docx"
    shutil.copy(SAMPLE, src)

    assert main(["doc", str(src), "--chain", "ru,ja,ru"]) == 1
    assert not (tmp_path / "in_uniq.docx").exists()


def test_yandex_without_key_explains_what_to_do(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)  # чтобы не подхватить настоящий .env
    monkeypatch.delenv("YANDEX_API_KEY", raising=False)

    assert main(["text", "Привет", "--engine", "yandex"]) == 1
    assert "YANDEX_API_KEY" in capsys.readouterr().err


def test_env_file_in_working_directory_is_loaded(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TEXTUNIQ_TEST_VAR", raising=False)
    (tmp_path / ".env").write_text("TEXTUNIQ_TEST_VAR=ok\n", encoding="utf-8")

    main(["text", "123", "--engine", "identity"])

    import os
    assert os.environ.pop("TEXTUNIQ_TEST_VAR") == "ok"


def test_text_command(capsys):
    assert main(["text", "Утро — лучшее время", "--engine", "identity"]) == 0
    assert capsys.readouterr().out.strip() == "Утро - лучшее время"
