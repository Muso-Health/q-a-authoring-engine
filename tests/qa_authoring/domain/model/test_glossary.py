from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from qa_authoring.domain.model.glossary import (
    GlossaryFormNotFoundError,
    GlossaryStatus,
    GlossaryTerm,
    InvalidGlossaryFieldError,
)

T0 = datetime(2026, 10, 27, tzinfo=UTC)
T1 = T0 + timedelta(hours=1)
FR, BM = uuid4(), uuid4()


def _term() -> GlossaryTerm:
    return GlossaryTerm.create(" malaria ", note="  the disease  ", at=T0)


def test_a_new_term_is_active_trimmed_and_has_no_forms() -> None:
    term = _term()
    assert (term.label, term.note, term.status) == ("malaria", "the disease", GlossaryStatus.ACTIVE)
    assert (term.created_at, term.updated_at, term.forms) == (T0, T0, ())
    assert GlossaryTerm.create("fever", at=T0).note is None
    assert GlossaryTerm.create("fever", note="   ", at=T0).note is None


def test_the_label_is_required() -> None:
    with pytest.raises(InvalidGlossaryFieldError) as raised:
        GlossaryTerm.create("  ", at=T0)
    assert raised.value.field == "label"
    term = _term()
    with pytest.raises(InvalidGlossaryFieldError):
        term.relabel("", at=T1)
    assert (term.label, term.updated_at) == ("malaria", T0)


def test_relabel_and_annotate_touch_the_term_only_on_a_change() -> None:
    term = _term()
    term.relabel(" malaria ", at=T1)
    term.annotate("the disease", at=T1)
    assert term.updated_at == T0

    term.relabel("Malaria", at=T1)
    assert (term.label, term.updated_at) == ("Malaria", T1)
    term.annotate(None, at=T1)
    assert term.note is None


def test_archive_and_unarchive() -> None:
    term = _term()
    term.archive(at=T1)
    assert (term.status, term.updated_at) == (GlossaryStatus.ARCHIVED, T1)
    later = T1 + timedelta(minutes=5)
    term.archive(at=later)  # already archived: nothing changes
    assert term.updated_at == T1

    term.unarchive(at=later)
    assert (term.status, term.updated_at) == (GlossaryStatus.ACTIVE, later)
    term.unarchive(at=later + timedelta(minutes=5))
    assert term.updated_at == later


def test_form_strings_are_trimmed_and_lists_cleaned_in_order() -> None:
    term = _term()
    form, created = term.put_form(
        FR,
        " paludisme ",
        synonyms=[" palu ", "", "fièvre des marais", "palu", "  "],
        avoid=["malaria ", "malaria", " "],
        note=" medical term ",
        at=T1,
    )
    assert created
    assert (form.term_id, form.language_id, form.preferred) == (term.id, FR, "paludisme")
    assert form.synonyms == ("palu", "fièvre des marais")
    assert form.avoid == ("malaria",)
    assert form.note == "medical term"
    assert term.forms == (form,)
    assert term.updated_at == T1


def test_the_preferred_form_is_required() -> None:
    term = _term()
    with pytest.raises(InvalidGlossaryFieldError) as raised:
        term.put_form(FR, "  ", at=T1)
    assert raised.value.field == "preferred"
    assert term.forms == ()


def test_putting_a_form_for_a_language_replaces_it() -> None:
    term = _term()
    first, _ = term.put_form(FR, "paludisme", synonyms=["palu"], note="n", at=T0)
    term.put_form(BM, "sumaya", at=T0)

    second, created = term.put_form(FR, "malaria", avoid=["palu"], at=T1)

    assert not created
    assert second.id == first.id
    assert (second.preferred, second.synonyms, second.avoid, second.note) == (
        "malaria",
        (),
        ("palu",),
        None,
    )
    assert len(term.forms) == 2
    assert term.form(FR) == second


def test_removing_a_form() -> None:
    term = _term()
    term.put_form(FR, "paludisme", at=T0)
    term.remove_form(FR, at=T1)
    assert (term.forms, term.updated_at, term.form(FR)) == ((), T1, None)
    with pytest.raises(GlossaryFormNotFoundError):
        term.remove_form(FR, at=T1)


def test_search_matches_label_and_form_strings_ignoring_case_and_accents() -> None:
    term = _term()
    term.put_form(FR, "Paludisme", synonyms=["fièvre des marais"], avoid=["Palu"], at=T0)
    term.annotate("notes are not searched", at=T0)

    for query in ("MALARIA", "ludis", "FIEVRE  des", "palu", "Fièvre"):
        assert term.matches(query), query
    assert not term.matches("notes")
    assert not term.matches("sumaya")
