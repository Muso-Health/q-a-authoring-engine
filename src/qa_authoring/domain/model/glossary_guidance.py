from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from qa_authoring.domain.model.glossary import GlossaryStatus
from qa_authoring.domain.value_objects.naming import search_fold

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from uuid import UUID

    from qa_authoring.domain.model.glossary import GlossaryTerm

NO_GUIDANCE = "(none)"


@dataclass(frozen=True, slots=True)
class GlossaryGuidance:
    """For a translation: write ``source`` as ``target``, never as any of ``avoid``."""

    source: str
    target: str
    avoid: tuple[str, ...]


def _occurs(needle: str, folded_text: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", folded_text) is not None


def match_glossary(
    text: str,
    source_language_id: UUID,
    target_language_id: UUID,
    terms: Iterable[GlossaryTerm],
) -> tuple[GlossaryGuidance, ...]:
    """The guidance of every active term with a form in both languages whose source preferred
    form or a synonym occurs in ``text`` as whole words, ignoring case, accents and spacing.
    Ordered by source form, without duplicates."""
    folded = search_fold(text)
    found: set[GlossaryGuidance] = set()
    for term in terms:
        source, target = term.form(source_language_id), term.form(target_language_id)
        if term.status is not GlossaryStatus.ACTIVE or source is None or target is None:
            continue
        needles = {search_fold(s) for s in (source.preferred, *source.synonyms)}
        if any(_occurs(n, folded) for n in needles if n):
            found.add(GlossaryGuidance(source.preferred, target.preferred, target.avoid))
    return tuple(sorted(found, key=lambda g: (search_fold(g.source), g.source, g.target, g.avoid)))


def render_glossary(guidance: Sequence[GlossaryGuidance]) -> str:
    """One line per entry, or ``NO_GUIDANCE`` so a prompt always reads cleanly."""
    lines = []
    for g in guidance:
        avoid = f" (avoid: {', '.join(f'"{a}"' for a in g.avoid)})" if g.avoid else ""
        lines.append(f'- "{g.source}" → "{g.target}"{avoid}')
    return "\n".join(lines) or NO_GUIDANCE
