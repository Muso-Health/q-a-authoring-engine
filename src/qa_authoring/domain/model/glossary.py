from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from qa_authoring.domain.value_objects.naming import clean_description, search_fold

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import datetime


class GlossaryStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class InvalidGlossaryFieldError(ValueError):
    """Raised when a required glossary field (``label``, ``preferred``) is blank."""

    def __init__(self, field: str) -> None:
        super().__init__(f"glossary {field} must not be blank")
        self.field = field


class GlossaryFormNotFoundError(Exception):
    def __init__(self, term_id: UUID, language_id: UUID) -> None:
        super().__init__(f"glossary term {term_id} has no form in language {language_id}")
        self.term_id = term_id
        self.language_id = language_id


def _required(value: str, field: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise InvalidGlossaryFieldError(field)
    return cleaned


def _clean_list(values: Iterable[str]) -> tuple[str, ...]:
    """Trimmed, blanks dropped, duplicates dropped, order kept."""
    return tuple(dict.fromkeys(v.strip() for v in values if v.strip()))


class GlossaryForm:
    """How a term is written in one language: Muso's preferred form, its accepted synonyms and
    the forms to avoid."""

    __slots__ = ("_avoid", "_id", "_language_id", "_note", "_preferred", "_synonyms", "_term_id")

    def __init__(
        self,
        form_id: UUID,
        term_id: UUID,
        language_id: UUID,
        preferred: str,
        synonyms: Iterable[str] = (),
        avoid: Iterable[str] = (),
        note: str | None = None,
    ) -> None:
        self._id = form_id
        self._term_id = term_id
        self._language_id = language_id
        self._preferred = _required(preferred, "preferred")
        self._synonyms = _clean_list(synonyms)
        self._avoid = _clean_list(avoid)
        self._note = clean_description(note)

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def term_id(self) -> UUID:
        return self._term_id

    @property
    def language_id(self) -> UUID:
        return self._language_id

    @property
    def preferred(self) -> str:
        return self._preferred

    @property
    def synonyms(self) -> tuple[str, ...]:
        return self._synonyms

    @property
    def avoid(self) -> tuple[str, ...]:
        return self._avoid

    @property
    def note(self) -> str | None:
        return self._note

    def strings(self) -> tuple[str, ...]:
        return (self._preferred, *self._synonyms, *self._avoid)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, GlossaryForm) and other._id == self._id

    def __hash__(self) -> int:
        return hash(self._id)

    def __repr__(self) -> str:
        return f"GlossaryForm(language_id={self._language_id}, preferred={self._preferred!r})"


class GlossaryTerm:
    """A concept of the global Muso glossary, found by its ``label`` (a handle, not a
    translation), with at most one form per language."""

    __slots__ = ("_created_at", "_forms", "_id", "_label", "_note", "_status", "_updated_at")

    def __init__(
        self,
        term_id: UUID,
        label: str,
        note: str | None,
        status: GlossaryStatus,
        created_at: datetime,
        updated_at: datetime,
        forms: Iterable[GlossaryForm] = (),
    ) -> None:
        self._id = term_id
        self._label = _required(label, "label")
        self._note = clean_description(note)
        self._status = status
        self._created_at = created_at
        self._updated_at = updated_at
        self._forms = {f.language_id: f for f in forms}

    @classmethod
    def create(cls, label: str, note: str | None = None, *, at: datetime) -> GlossaryTerm:
        return cls(uuid4(), label, note, GlossaryStatus.ACTIVE, at, at)

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def label(self) -> str:
        return self._label

    @property
    def note(self) -> str | None:
        return self._note

    @property
    def status(self) -> GlossaryStatus:
        return self._status

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        return self._updated_at

    @property
    def forms(self) -> tuple[GlossaryForm, ...]:
        """Ordered by language id, so the order is stable wherever the term is loaded from."""
        return tuple(sorted(self._forms.values(), key=lambda f: str(f.language_id)))

    def form(self, language_id: UUID) -> GlossaryForm | None:
        return self._forms.get(language_id)

    def relabel(self, label: str, *, at: datetime) -> None:
        cleaned = _required(label, "label")
        if cleaned != self._label:
            self._label = cleaned
            self._updated_at = at

    def annotate(self, note: str | None, *, at: datetime) -> None:
        cleaned = clean_description(note)
        if cleaned != self._note:
            self._note = cleaned
            self._updated_at = at

    def archive(self, *, at: datetime) -> None:
        self._set_status(GlossaryStatus.ARCHIVED, at)

    def unarchive(self, *, at: datetime) -> None:
        self._set_status(GlossaryStatus.ACTIVE, at)

    def _set_status(self, status: GlossaryStatus, at: datetime) -> None:
        if status is not self._status:
            self._status = status
            self._updated_at = at

    def put_form(
        self,
        language_id: UUID,
        preferred: str,
        *,
        synonyms: Iterable[str] = (),
        avoid: Iterable[str] = (),
        note: str | None = None,
        at: datetime,
    ) -> tuple[GlossaryForm, bool]:
        """Set the language's form, replacing the one it had (which keeps its id). The flag says
        whether the language had none."""
        existing = self._forms.get(language_id)
        form = GlossaryForm(
            uuid4() if existing is None else existing.id,
            self._id,
            language_id,
            preferred,
            synonyms,
            avoid,
            note,
        )
        self._forms[language_id] = form
        self._updated_at = at
        return form, existing is None

    def remove_form(self, language_id: UUID, *, at: datetime) -> None:
        if self._forms.pop(language_id, None) is None:
            raise GlossaryFormNotFoundError(self._id, language_id)
        self._updated_at = at

    @property
    def search_text(self) -> str:
        """The label and every form string, folded for search; notes are not searched."""
        strings = [self._label, *(s for f in self._forms.values() for s in f.strings())]
        return "\n".join(search_fold(s) for s in strings)

    def matches(self, query: str) -> bool:
        return search_fold(query) in self.search_text

    def __eq__(self, other: object) -> bool:
        return isinstance(other, GlossaryTerm) and other._id == self._id

    def __hash__(self) -> int:
        return hash(self._id)

    def __repr__(self) -> str:
        return f"GlossaryTerm(id={self._id}, label={self._label!r}, status={self._status})"
