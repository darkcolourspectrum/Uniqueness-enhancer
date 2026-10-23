"""Крошечные случайные модели Marian и NLLB, собранные локально без интернета.

Перевод они выдают бессмысленный, зато проверяют, что адаптеры правильно
работают с установленной версией transformers: загрузка, токенизация,
пакетная генерация, служебные токены языков.
"""

import json
import shutil
from pathlib import Path

_CORPUS = [
    f"Привет мир номер {i}. Hello world number {i}. Hallo Welt Nummer {i}." for i in range(200)
]
_TINY = dict(
    d_model=16,
    encoder_layers=1,
    decoder_layers=1,
    encoder_attention_heads=2,
    decoder_attention_heads=2,
    encoder_ffn_dim=32,
    decoder_ffn_dim=32,
    max_position_embeddings=128,
)


def _train_spm(workdir: Path) -> Path:
    import sentencepiece as spm

    corpus = workdir / "corpus.txt"
    corpus.write_text("\n".join(_CORPUS), encoding="utf-8")
    spm.SentencePieceTrainer.train(
        input=str(corpus),
        model_prefix=str(workdir / "sp"),
        vocab_size=120,
        character_coverage=1.0,
        pad_id=0,
        eos_id=1,
        unk_id=2,
        bos_id=-1,
        minloglevel=2,
    )
    return workdir / "sp.model"


def build_tiny_marian(workdir: Path) -> Path:
    import sentencepiece as spm
    from transformers import MarianConfig, MarianMTModel, MarianTokenizer

    sp_model = _train_spm(workdir)
    out = workdir / "tiny-marian"
    out.mkdir()
    shutil.copy(sp_model, out / "source.spm")
    shutil.copy(sp_model, out / "target.spm")
    sp = spm.SentencePieceProcessor(model_file=str(sp_model))
    vocab = {sp.id_to_piece(i): i for i in range(sp.get_piece_size())}
    (out / "vocab.json").write_text(json.dumps(vocab, ensure_ascii=False), encoding="utf-8")

    tokenizer = MarianTokenizer(
        source_spm=str(out / "source.spm"),
        target_spm=str(out / "target.spm"),
        vocab=str(out / "vocab.json"),
    )
    config = MarianConfig(
        vocab_size=len(tokenizer),
        pad_token_id=tokenizer.pad_token_id,
        eos_token_id=tokenizer.eos_token_id,
        decoder_start_token_id=tokenizer.pad_token_id,
        **_TINY,
    )
    tokenizer.save_pretrained(out)
    MarianMTModel(config).save_pretrained(out)
    return out


def build_tiny_nllb(workdir: Path) -> Path:
    from transformers import M2M100Config, M2M100ForConditionalGeneration, NllbTokenizer

    sp_model = _train_spm(workdir)
    out = workdir / "tiny-nllb"
    out.mkdir()
    tokenizer = NllbTokenizer(vocab_file=str(sp_model))
    config = M2M100Config(
        vocab_size=len(tokenizer),
        pad_token_id=tokenizer.pad_token_id,
        eos_token_id=tokenizer.eos_token_id,
        bos_token_id=tokenizer.bos_token_id,
        decoder_start_token_id=tokenizer.eos_token_id,
        **_TINY,
    )
    tokenizer.save_pretrained(out)
    M2M100ForConditionalGeneration(config).save_pretrained(out)
    return out
