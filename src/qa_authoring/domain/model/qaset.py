from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from qa_authoring.domain.value_objects.naming import clean_text

if TYPE_CHECKING:
    from collections.abc import Iterable


class LanguageAlreadyPresentError(Exception):
    def __init__(self, language_id: UUID) -> None:
        super().__init__(f"language {language_id} already has an answer in this QA set")
        self.language_id = language_id


class LanguageNotPresentError(Exception):
    def __init__(self, language_id: UUID) -> None:
        super().__init__(f"language {language_id} is not present in this QA set")
        self.language_id = language_id


class LanguagePresenceRequiredError(Exception):
    """Raised when adding a question variant in a language that has no answer yet."""

    def __init__(self, language_id: UUID) -> None:
        super().__init__(f"language {language_id} needs an answer before question variants")
        self.language_id = language_id


class QuestionVariantNotFoundError(Exception):
    def __init__(self, variant_id: UUID) -> None:
        super().__init__(f"question variant {variant_id} not found")
        self.variant_id = variant_id


class _Text:
    __slots__ = ("_id", "_language_id", "_text")
    subject = "text"

    def __init__(self, entity_id: UUID, language_id: UUID, text: str) -> None:
        self._id = entity_id
        self._language_id = language_id
        self._text = clean_text(text, subject=self.subject)

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def language_id(self) -> UUID:
        return self._language_id

    @property
    def text(self) -> str:
        return self._text

    def _replace_text(self, text: str) -> None:
        self._text = clean_text(text, subject=self.subject)


class Answer(_Text):
    """The single answer of a QA set in one language. Mutated only through its ``QASet``."""

    __slots__ = ()
    subject = "answer"


class QuestionVariant(_Text):
    """One phrasing of the question in one language. Mutated only through its ``QASet``."""

    __slots__ = ()
    subject = "question variant"


@dataclass(frozen=True, slots=True)
class LanguagePresence:
    """A language's answer and its question variants — derived, never stored."""

    language_id: UUID
    answer: Answer
    variants: tuple[QuestionVariant, ...]

    @property
    def variant_count(self) -> int:
        return len(self.variants)


class QASet:
    """Aggregate root: a question/answer set within a theme, across languages.

    Invariants: at most one answer per language, and every question variant's language has an
    answer. Removing a language's answer removes its variants. Answers and variants keep their
    creation order: rehydrate them in that order.
    """

    __slots__ = ("_answers", "_id", "_theme_id", "_variants")

    def __init__(
        self,
        qaset_id: UUID,
        theme_id: UUID,
        *,
        answers: Iterable[Answer],
        variants: Iterable[QuestionVariant],
    ) -> None:
        self._id = qaset_id
        self._theme_id = theme_id
        self._answers: dict[UUID, Answer] = {}
        self._variants: dict[UUID, QuestionVariant] = {}
        for answer in answers:
            self._put_answer(answer)
        for variant in variants:
            self._put_variant(variant)

    @classmethod
    def create(cls, *, theme_id: UUID, language_id: UUID, answer_text: str) -> QASet:
        return cls(
            uuid4(), theme_id, answers=(Answer(uuid4(), language_id, answer_text),), variants=()
        )

    @property
    def id(self) -> UUID:
        return self._id

    @property
    def theme_id(self) -> UUID:
        return self._theme_id

    @property
    def answers(self) -> tuple[Answer, ...]:
        return tuple(self._answers.values())

    @property
    def variants(self) -> tuple[QuestionVariant, ...]:
        return tuple(self._variants.values())

    def presences(self) -> tuple[LanguagePresence, ...]:
        return tuple(self._presence_of(answer) for answer in self.answers)

    def presence(self, language_id: UUID) -> LanguagePresence:
        return self._presence_of(self._answer(language_id))

    def add_language(self, language_id: UUID, answer_text: str) -> Answer:
        answer = Answer(uuid4(), language_id, answer_text)
        self._put_answer(answer)
        return answer

    def update_answer(self, language_id: UUID, text: str) -> Answer:
        answer = self._answer(language_id)
        answer._replace_text(text)
        return answer

    def remove_language(self, language_id: UUID) -> None:
        del self._answers[self._answer(language_id).language_id]
        self._variants = {
            vid: v for vid, v in self._variants.items() if v.language_id != language_id
        }

    def add_variant(self, language_id: UUID, text: str) -> QuestionVariant:
        variant = QuestionVariant(uuid4(), language_id, text)
        self._put_variant(variant)
        return variant

    def update_variant(self, variant_id: UUID, text: str) -> QuestionVariant:
        variant = self._variant(variant_id)
        variant._replace_text(text)
        return variant

    def remove_variant(self, variant_id: UUID) -> None:
        del self._variants[self._variant(variant_id).id]

    def _put_answer(self, answer: Answer) -> None:
        if answer.language_id in self._answers:
            raise LanguageAlreadyPresentError(answer.language_id)
        self._answers[answer.language_id] = answer

    def _put_variant(self, variant: QuestionVariant) -> None:
        if variant.language_id not in self._answers:
            raise LanguagePresenceRequiredError(variant.language_id)
        self._variants[variant.id] = variant

    def _answer(self, language_id: UUID) -> Answer:
        answer = self._answers.get(language_id)
        if answer is None:
            raise LanguageNotPresentError(language_id)
        return answer

    def _variant(self, variant_id: UUID) -> QuestionVariant:
        variant = self._variants.get(variant_id)
        if variant is None:
            raise QuestionVariantNotFoundError(variant_id)
        return variant

    def _presence_of(self, answer: Answer) -> LanguagePresence:
        variants = tuple(v for v in self.variants if v.language_id == answer.language_id)
        return LanguagePresence(answer.language_id, answer, variants)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, QASet) and other._id == self._id

    def __hash__(self) -> int:
        return hash(self._id)

    def __repr__(self) -> str:
        return f"QASet(id={self._id}, languages={len(self._answers)})"
