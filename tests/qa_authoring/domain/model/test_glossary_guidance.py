from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from qa_authoring.domain.model.glossary import GlossaryTerm
from qa_authoring.domain.model.glossary_guidance import (
    GlossaryGuidance,
    match_glossary,
    render_glossary,
)

T0 = datetime(2026, 10, 27, tzinfo=UTC)
FR, BM, EN = uuid4(), uuid4(), uuid4()


def _term(
    label: str,
    fr: tuple[str, list[str]] | None,
    bm: tuple[str, list[str]] | None,
) -> GlossaryTerm:
    term = GlossaryTerm.create(label, at=T0)
    if fr is not None:
        term.put_form(FR, fr[0], synonyms=fr[1], avoid=["fr-avoid"], at=T0)
    if bm is not None:
        term.put_form(BM, bm[0], avoid=bm[1], at=T0)
    return term


MALARIA = _term("malaria", ("paludisme", ["palu"]), ("sumaya", ["malaria", "palu"]))
FEVER = _term("fever", ("fièvre", ["température élevée"]), ("farigan", []))
ART = _term("art", ("art", []), ("art-bm", []))


def test_a_term_matches_on_its_preferred_form_or_a_synonym() -> None:
    assert match_glossary("Le paludisme tue.", FR, BM, [MALARIA]) == (
        GlossaryGuidance("paludisme", "sumaya", ("malaria", "palu")),
    )
    assert match_glossary("Contre le palu, dormez sous une moustiquaire.", FR, BM, [MALARIA]) == (
        GlossaryGuidance("paludisme", "sumaya", ("malaria", "palu")),
    )
    assert match_glossary("Une température élevée persiste.", FR, BM, [FEVER]) == (
        GlossaryGuidance("fièvre", "farigan", ()),
    )


def test_matches_fall_on_word_boundaries() -> None:
    assert match_glossary("Prenez l'artésunate.", FR, BM, [ART]) == ()
    assert match_glossary("Le paludismes", FR, BM, [MALARIA]) == ()
    assert match_glossary("(art) et l'art.", FR, BM, [ART]) == (
        GlossaryGuidance("art", "art-bm", ()),
    )


def test_matching_ignores_case_accents_and_spacing() -> None:
    expected = (GlossaryGuidance("fièvre", "farigan", ()),)
    assert match_glossary("FIEVRE forte", FR, BM, [FEVER]) == expected
    assert match_glossary("une Temperature\n  Élevée", FR, BM, [FEVER]) == expected


def test_a_term_needs_a_form_in_both_languages_and_to_be_active() -> None:
    no_target = _term("cough", ("toux", []), None)
    no_source = _term("cough", None, ("sɔgɔsɔgɔ", []))
    archived = _term("fever", ("fièvre", []), ("farigan", []))
    archived.archive(at=T0)
    text = "toux et fièvre"
    assert match_glossary(text, FR, BM, [no_target, no_source, archived]) == ()
    assert match_glossary("Le paludisme", FR, EN, [MALARIA]) == ()


def test_guidance_is_ordered_by_source_and_without_duplicates() -> None:
    twin = _term("malaria again", ("paludisme", []), ("sumaya", ["malaria", "palu"]))
    text = "Paludisme, palu et fièvre : le palu donne de la fièvre."

    guidance = match_glossary(text, FR, BM, [MALARIA, FEVER, twin, MALARIA])

    assert guidance == (
        GlossaryGuidance("fièvre", "farigan", ()),
        GlossaryGuidance("paludisme", "sumaya", ("malaria", "palu")),
    )


def test_nothing_matches() -> None:
    assert match_glossary("Buvez de l'eau.", FR, BM, [MALARIA, FEVER]) == ()
    assert match_glossary("Le paludisme", FR, BM, []) == ()


def test_rendering() -> None:
    assert render_glossary(()) == "(none)"
    assert render_glossary(
        (
            GlossaryGuidance("fièvre", "farigan", ()),
            GlossaryGuidance("paludisme", "sumaya", ("malaria", "palu")),
        )
    ) == ('- "fièvre" → "farigan"\n- "paludisme" → "sumaya" (avoid: "malaria", "palu")')
