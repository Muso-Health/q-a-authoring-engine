from __future__ import annotations

from dataclasses import dataclass

from qa_authoring.domain.model.glossary import GlossaryStatus

MAX_GLOSSARY_PAGE = 200


@dataclass(frozen=True, slots=True)
class ListGlossaryTermsQuery:
    """``status`` None lists every term; a blank ``search`` does not filter."""

    status: GlossaryStatus | None = GlossaryStatus.ACTIVE
    search: str | None = None
    limit: int = 50
    offset: int = 0
