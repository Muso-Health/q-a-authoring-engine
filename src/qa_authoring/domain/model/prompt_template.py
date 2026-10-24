from __future__ import annotations

import re
import string
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from datetime import datetime
    from uuid import UUID


class PromptTemplateKey(StrEnum):
    """One key per use of a language model; the set is fixed by the code."""

    COMPLETENESS = "completeness"
    TRANSLATION = "translation"
    VARIANT_GENERATION = "variant_generation"


REQUIRED_PLACEHOLDERS: Mapping[PromptTemplateKey, frozenset[str]] = {
    PromptTemplateKey.COMPLETENESS: frozenset({"documentation", "answers", "language"}),
    PromptTemplateKey.TRANSLATION: frozenset({"source_language", "target_language", "text"}),
    PromptTemplateKey.VARIANT_GENERATION: frozenset({"answer", "context", "language"}),
}

_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class InvalidPromptTemplateError(ValueError):
    def __init__(
        self, reason: str, *, missing: Iterable[str] = (), unknown: Iterable[str] = ()
    ) -> None:
        self.missing = tuple(sorted(missing))
        self.unknown = tuple(sorted(unknown))
        details = [reason]
        if self.missing:
            details.append(f"missing: {', '.join(self.missing)}")
        if self.unknown:
            details.append(f"unknown: {', '.join(self.unknown)}")
        super().__init__("; ".join(details))


class PromptRenderError(ValueError):
    """Raised when the values given do not match the template's placeholders."""

    def __init__(self, *, missing: Iterable[str] = (), unexpected: Iterable[str] = ()) -> None:
        self.missing = tuple(sorted(missing))
        self.unexpected = tuple(sorted(unexpected))
        super().__init__(
            f"prompt values do not match the template (missing: {list(self.missing)}, "
            f"unexpected: {list(self.unexpected)})"
        )


def placeholders(content: str) -> frozenset[str]:
    """The named placeholders of ``content``. ``{{`` and ``}}`` are literal braces. Only plain
    ``{name}`` fields are allowed: no positional fields, attribute or index access, conversions
    or format specs, so rendering can only substitute values."""
    try:
        parsed = list(string.Formatter().parse(content))
    except ValueError as exc:
        raise InvalidPromptTemplateError(f"malformed braces: {exc}") from exc
    names = set()
    for _, field, spec, conversion in parsed:
        if field is None:
            continue
        if not _NAME.fullmatch(field) or spec or conversion:
            raise InvalidPromptTemplateError(
                f"only plain named placeholders like {{name}} are allowed, not {{{field}}}"
            )
        names.add(field)
    return frozenset(names)


class PromptTemplate:
    """The active prompt for one use, shared by everyone. ``updated_by`` is None for the
    seeded default."""

    __slots__ = ("_content", "_key", "_updated_at", "_updated_by")

    def __init__(
        self,
        key: PromptTemplateKey,
        content: str,
        *,
        updated_by: UUID | None,
        updated_at: datetime,
    ) -> None:
        self._key = key
        self._content = _validated(key, content)
        self._updated_by = updated_by
        self._updated_at = _aware(updated_at)

    @classmethod
    def create(
        cls, key: PromptTemplateKey, content: str, *, updated_by: UUID | None, at: datetime
    ) -> PromptTemplate:
        return cls(key, content, updated_by=updated_by, updated_at=at)

    @property
    def key(self) -> PromptTemplateKey:
        return self._key

    @property
    def content(self) -> str:
        return self._content

    @property
    def updated_by(self) -> UUID | None:
        return self._updated_by

    @property
    def updated_at(self) -> datetime:
        return self._updated_at

    @property
    def required_placeholders(self) -> frozenset[str]:
        return REQUIRED_PLACEHOLDERS[self._key]

    def revise(self, content: str, *, updated_by: UUID, at: datetime) -> None:
        self._content = _validated(self._key, content)
        self._updated_by = updated_by
        self._updated_at = _aware(at)

    def render(self, values: Mapping[str, str]) -> str:
        """Substitute ``values`` (one per placeholder, no more, no less); literal braces stay."""
        names = placeholders(self._content)
        missing, unexpected = names - values.keys(), values.keys() - names
        if missing or unexpected:
            raise PromptRenderError(missing=missing, unexpected=unexpected)
        return self._content.format_map(values)

    def __repr__(self) -> str:
        return f"PromptTemplate(key={self._key.value!r})"


def _validated(key: PromptTemplateKey, content: str) -> str:
    if not content.strip():
        raise InvalidPromptTemplateError("a prompt template must not be blank")
    names = placeholders(content)
    required = REQUIRED_PLACEHOLDERS[key]
    missing, unknown = required - names, names - required
    if missing or unknown:
        raise InvalidPromptTemplateError(
            f"the {key.value} template must use exactly its placeholders",
            missing=missing,
            unknown=unknown,
        )
    return content


def _aware(at: datetime) -> datetime:
    if at.tzinfo is None:
        raise ValueError("updated_at must be timezone-aware")
    return at


DEFAULT_TEMPLATES: Mapping[PromptTemplateKey, str] = {
    PromptTemplateKey.COMPLETENESS: """\
You review a clinically validated question-and-answer corpus for a community health programme \
in Mali, to find what it does not yet cover.
Below are the reference documentation of one theme and the answers the corpus already gives for \
that theme. Reason and write in {language}.

Identify the notions in the documentation that no answer covers: clinical facts, instructions, \
doses, warning signs, prevention measures, or situations that a patient, a caregiver or a \
community health worker would need, and that are missing from every answer. Ignore notions that \
an answer already covers, even with different wording. Do not invent notions that are not in the \
documentation.

Documentation:
{documentation}

Answers already in the corpus:
{answers}

List each uncovered notion as one short phrase in {language}.""",
    PromptTemplateKey.TRANSLATION: """\
You are a professional medical translator working for a community health programme in Mali.
Translate the text below from {source_language} into {target_language}.

Rules:
- Translate faithfully: keep every clinical fact, instruction, dose, number and warning. Add \
nothing and omit nothing.
- Preserve the register and tone of the source: plain, respectful language suited to patients \
and community health workers.
- Keep medical terms accurate. When {target_language} has no established term, use the term \
commonly understood locally and keep the meaning unambiguous.
- Keep names, numbers, units and line breaks as they are.
- Return only the translation, with no explanation or commentary.

Text to translate:
{text}""",
    PromptTemplateKey.VARIANT_GENERATION: """\
You help build a clinically reviewed question-and-answer corpus for a community health \
programme in Mali.
Write plausible questions in {language} that a patient, a caregiver or a community health \
worker could ask, and that the answer below fully addresses.

Context:
{context}

Answer:
{answer}

Rules:
- Every question must be fully answered by the answer above. Do not introduce clinical facts, \
symptoms or treatments that the answer does not cover.
- Paraphrase: vary wording, sentence structure and register, from formal to colloquial, as \
real people would ask.
- Write natural {language}; do not translate word for word from another language.
- Return one question per line, with no numbering and no commentary.""",
}
