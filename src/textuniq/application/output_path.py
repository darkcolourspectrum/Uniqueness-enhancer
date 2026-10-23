from pathlib import Path


def default_output_path(source: Path, suffix: str = "_uniq") -> Path:
    """`статья.docx` → `статья_uniq.docx` рядом; существующие файлы не трогаем."""
    source = Path(source)
    candidate = source.with_name(f"{source.stem}{suffix}{source.suffix}")
    counter = 2
    while candidate.exists():
        candidate = source.with_name(f"{source.stem}{suffix}_{counter}{source.suffix}")
        counter += 1
    return candidate
