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


class AnswerNotFoundError(Exception):
    def __init__(self, answer_id: UUID) -> None:
        super().__init__(f"answer {answer_id} not found in this QA set")
        self.answer_id = answer_id


class SelfLinkError(Exception):
    def __init__(self, item_id: UUID) -> None:
        super().__init__(f"{item_id} cannot be linked to itself")
        self.item_id = item_id


class SameLanguageError(Exception):
    """Raised when linking two items written in the same language."""

    def __init__(self, language_id: UUID) -> None:
        super().__init__(f"both items are in language {language_id}; a translation needs two")
        self.language_id = language_id


class LinkAlreadyExistsError(Exception):
    def __init__(self, low_id: UUID, high_id: UUID) -> None:
        super().__init__(f"{low_id} and {high_id} are already linked")
        self.item_ids = (low_id, high_id)


class TranslationLinkNotFoundError(Exception):
    def __init__(self, link_id: UUID) -> None:
        super().__init__(f"translation link {link_id} not found")
        self.link_id = link_id


class IntentNotAttachedError(Exception):
    def __init__(self, variant_id: UUID, intent_id: UUID) -> None:
        super().__init__(f"intent {intent_id} is not attached to question variant {variant_id}")
        self.variant_id = variant_id
        self.intent_id = intent_id


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
    """One phrasing of the question in one language, tagged with catalogue intents (by id, in
    attachment order). Mutated only through its ``QASet``."""

    __slots__ = ("_intent_ids",)
    subject = "question variant"

    def __init__(
        self, variant_id: UUID, language_id: UUID, text: str, intent_ids: Iterable[UUID] = ()
    ) -> None:
        super().__init__(variant_id, language_id, text)
        self._intent_ids: dict[UUID, None] = dict.fromkeys(intent_ids)

    @property
    def intent_ids(self) -> tuple[UUID, ...]:
        return tuple(self._intent_ids)

    def _attach(self, intent_id: UUID) -> bool:
        if intent_id in self._intent_ids:
            return False
        self._intent_ids[intent_id] = None
        return True

    def _detach(self, intent_id: UUID) -> None:
        if intent_id not in self._intent_ids:
            raise IntentNotAttachedError(self.id, intent_id)
        del self._intent_ids[intent_id]


@dataclass(frozen=True, slots=True)
class LanguagePresence:
    """A language's answer and its question variants — derived, never stored."""

    language_id: UUID
    answer: Answer
    variants: tuple[QuestionVariant, ...]

    @property
    def variant_count(self) -> int:
        return len(self.variants)


@dataclass(frozen=True, slots=True)
class TranslationLink:
    """An undirected pair of items, stored canonically (``low_id < high_id``)."""

    id: UUID
    low_id: UUID
    high_id: UUID

    @classmethod
    def between(cls, link_id: UUID, a: UUID, b: UUID) -> TranslationLink:
        low, high = sorted((a, b))
        return cls(link_id, low, high)

    def involves(self, item_id: UUID) -> bool:
        return item_id in (self.low_id, self.high_id)

    def other(self, item_id: UUID) -> UUID:
        return self.high_id if item_id == self.low_id else self.low_id


@dataclass(frozen=True, slots=True)
class Translation:
    """One of an item's links, seen from that item."""

    link_id: UUID
    other_id: UUID
    other_language_id: UUID


class _LinkSet:
    """The translation links between items of one kind. A free graph: an item may have several
    counterparts in the same language, but never itself, its own language, or a pair twice."""

    __slots__ = ("_links",)

    def __init__(self) -> None:
        self._links: dict[UUID, TranslationLink] = {}

    @property
    def all(self) -> tuple[TranslationLink, ...]:
        return tuple(self._links.values())

    def put(self, link: TranslationLink, low: _Text, high: _Text) -> None:
        if low.id == high.id:
            raise SelfLinkError(low.id)
        if low.language_id == high.language_id:
            raise SameLanguageError(low.language_id)
        if any(
            (existing.low_id, existing.high_id) == (link.low_id, link.high_id)
            for existing in self._links.values()
        ):
            raise LinkAlreadyExistsError(link.low_id, link.high_id)
        self._links[link.id] = link

    def remove(self, link_id: UUID) -> None:
        if self._links.pop(link_id, None) is None:
            raise TranslationLinkNotFoundError(link_id)

    def drop_involving(self, item_ids: set[UUID]) -> None:
        self._links = {
            lid: link
            for lid, link in self._links.items()
            if link.low_id not in item_ids and link.high_id not in item_ids
        }

    def of(self, item_id: UUID) -> tuple[TranslationLink, ...]:
        return tuple(link for link in self._links.values() if link.involves(item_id))


class QASet:
    """Aggregate root: a question/answer set within a theme, across languages.

    Invariants: at most one answer per language, and every question variant's language has an
    answer. Removing a language's answer removes its variants. Translation links pair two answers
    or two variants of this QA set in different languages; removing an item removes its links.
    Answers, variants and links keep their creation order: rehydrate them in that order.
    """

    __slots__ = ("_answer_links", "_answers", "_id", "_theme_id", "_variant_links", "_variants")

    def __init__(
        self,
        qaset_id: UUID,
        theme_id: UUID,
        *,
        answers: Iterable[Answer],
        variants: Iterable[QuestionVariant],
        answer_links: Iterable[TranslationLink] = (),
        variant_links: Iterable[TranslationLink] = (),
    ) -> None:
        self._id = qaset_id
        self._theme_id = theme_id
        self._answers: dict[UUID, Answer] = {}
        self._variants: dict[UUID, QuestionVariant] = {}
        self._answer_links = _LinkSet()
        self._variant_links = _LinkSet()
        for answer in answers:
            self._put_answer(answer)
        for variant in variants:
            self._put_variant(variant)
        for link in answer_links:
            self._answer_links.put(
                link, self._answer_by_id(link.low_id), self._answer_by_id(link.high_id)
            )
        for link in variant_links:
            self._variant_links.put(link, self._variant(link.low_id), self._variant(link.high_id))

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

    @property
    def answer_links(self) -> tuple[TranslationLink, ...]:
        return self._answer_links.all

    @property
    def variant_links(self) -> tuple[TranslationLink, ...]:
        return self._variant_links.all

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
        answer = self._answer(language_id)
        removed_variants = {v.id for v in self._variants.values() if v.language_id == language_id}
        del self._answers[language_id]
        self._variants = {
            vid: v for vid, v in self._variants.items() if vid not in removed_variants
        }
        self._answer_links.drop_involving({answer.id})
        self._variant_links.drop_involving(removed_variants)

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
        self._variant_links.drop_involving({variant_id})

    def link_answers(self, answer_a_id: UUID, answer_b_id: UUID) -> TranslationLink:
        link = TranslationLink.between(uuid4(), answer_a_id, answer_b_id)
        self._answer_links.put(
            link, self._answer_by_id(link.low_id), self._answer_by_id(link.high_id)
        )
        return link

    def unlink_answers(self, link_id: UUID) -> None:
        self._answer_links.remove(link_id)

    def link_variants(self, variant_a_id: UUID, variant_b_id: UUID) -> TranslationLink:
        link = TranslationLink.between(uuid4(), variant_a_id, variant_b_id)
        self._variant_links.put(link, self._variant(link.low_id), self._variant(link.high_id))
        return link

    def unlink_variants(self, link_id: UUID) -> None:
        self._variant_links.remove(link_id)

    def attach_intent(self, variant_id: UUID, intent_id: UUID) -> bool:
        """Tag a variant with a catalogue intent; False if it already was (idempotent)."""
        return self._variant(variant_id)._attach(intent_id)

    def detach_intent(self, variant_id: UUID, intent_id: UUID) -> None:
        self._variant(variant_id)._detach(intent_id)

    def uses_intent(self, intent_id: UUID) -> bool:
        return any(intent_id in v.intent_ids for v in self._variants.values())

    def answer_translations(self, answer_id: UUID) -> tuple[Translation, ...]:
        return tuple(
            Translation(link.id, other, self._answer_by_id(other).language_id)
            for link in self._answer_links.of(answer_id)
            for other in (link.other(answer_id),)
        )

    def variant_translations(self, variant_id: UUID) -> tuple[Translation, ...]:
        return tuple(
            Translation(link.id, other, self._variant(other).language_id)
            for link in self._variant_links.of(variant_id)
            for other in (link.other(variant_id),)
        )

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

    def _answer_by_id(self, answer_id: UUID) -> Answer:
        answer = next((a for a in self._answers.values() if a.id == answer_id), None)
        if answer is None:
            raise AnswerNotFoundError(answer_id)
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
