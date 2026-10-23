import pytest

from textuniq.domain.models import TranslationChain


def test_default_chain_matches_specification():
    chain = TranslationChain.default()
    assert chain.languages == ("ru", "en", "de", "ru")
    assert chain.steps == [("ru", "en"), ("en", "de"), ("de", "ru")]
    assert chain.source == "ru"


def test_parse_chain_from_string():
    assert TranslationChain.parse(" ru, en ,ru ").languages == ("ru", "en", "ru")


def test_chain_must_return_to_source_language():
    with pytest.raises(ValueError):
        TranslationChain(("ru", "en", "de"))


@pytest.mark.parametrize("langs", [(), ("ru",), ("ru", "ru")])
def test_chain_needs_at_least_one_foreign_language(langs):
    with pytest.raises(ValueError):
        TranslationChain(langs)


def test_chain_rejects_repeated_neighbour():
    with pytest.raises(ValueError):
        TranslationChain(("ru", "en", "en", "ru"))
