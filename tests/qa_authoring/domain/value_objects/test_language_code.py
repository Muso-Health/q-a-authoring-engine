from __future__ import annotations

import pytest

from qa_authoring.domain.value_objects.language_code import InvalidLanguageCodeError, LanguageCode


@pytest.mark.parametrize("value", ["fr", "bm", "en", "bm_fr", "a", "abc_def_ghi"])
def test_accepts_lowercase_ascii_segments(value: str) -> None:
    assert LanguageCode(value).value == value


@pytest.mark.parametrize(
    "value",
    ["", "FR", "Fr", "fr-FR", "bm__fr", "_fr", "fr_", "fr1", "f r", " fr", "fr ", "é", "bm_FR"],
)
def test_rejects_anything_else(value: str) -> None:
    with pytest.raises(InvalidLanguageCodeError):
        LanguageCode(value)


def test_is_compared_by_value() -> None:
    assert LanguageCode("bm_fr") == LanguageCode("bm_fr")
    assert LanguageCode("fr") != LanguageCode("en")
