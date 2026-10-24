from __future__ import annotations

from dataclasses import dataclass

from qa_authoring.application.ports.identity import Identity  # noqa: TC001 — a dataclass field


@dataclass(frozen=True, slots=True)
class ResolveCurrentUserQuery:
    identity: Identity
