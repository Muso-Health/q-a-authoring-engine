from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    PrimaryKeyConstraint,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
)

from qa_authoring.infrastructure.persistence.metadata import metadata

_STATES = "('validated', 'rejected', 'pending')"
_DECISIONS = "('validated', 'rejected')"

# Exactly one subject column is set, and it is the one the kind validates.
SUBJECT_MATCHES_KIND = (
    "(kind = 'clinical' AND qaset_id IS NOT NULL AND answer_id IS NULL"
    " AND variant_id IS NULL AND audio_id IS NULL)"
    " OR (kind = 'translation' AND qaset_id IS NULL AND audio_id IS NULL"
    " AND (answer_id IS NULL) <> (variant_id IS NULL))"
    " OR (kind = 'audio' AND audio_id IS NOT NULL AND qaset_id IS NULL"
    " AND answer_id IS NULL AND variant_id IS NULL)"
)

validations = Table(
    "validations",
    metadata,
    Column("id", Uuid, nullable=False),
    Column("kind", Text, nullable=False),
    Column("qaset_id", Uuid, ForeignKey("qasets.id", ondelete="CASCADE"), nullable=True),
    Column("answer_id", Uuid, ForeignKey("answers.id", ondelete="CASCADE"), nullable=True),
    Column(
        "variant_id", Uuid, ForeignKey("question_variants.id", ondelete="CASCADE"), nullable=True
    ),
    Column("audio_id", Uuid, ForeignKey("audios.id", ondelete="CASCADE"), nullable=True),
    Column("current_state", Text, nullable=False, index=True),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint("id"),
    # One validation per subject; each also serves as that column's index.
    UniqueConstraint("qaset_id"),
    UniqueConstraint("answer_id"),
    UniqueConstraint("variant_id"),
    UniqueConstraint("audio_id"),
    CheckConstraint(SUBJECT_MATCHES_KIND, name="subject_matches_kind"),
    CheckConstraint(f"current_state IN {_STATES}", name="current_state"),
)

validation_events = Table(
    "validation_events",
    metadata,
    Column("id", Uuid, nullable=False),
    Column("validation_id", Uuid, ForeignKey("validations.id", ondelete="CASCADE"), nullable=False),
    Column("sequence", Integer, nullable=False),
    Column("from_state", Text, nullable=True),
    Column("to_state", Text, nullable=False),
    Column("note", Text, nullable=True),
    Column(
        "actor_user_id",
        Uuid,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    ),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint("id"),
    # Orders the history; also the index on validation_id.
    UniqueConstraint("validation_id", "sequence"),
    CheckConstraint(
        # A history starts with a decision; pending is only reached by a reset.
        f"to_state IN {_STATES} AND (from_state IS NOT NULL OR to_state IN {_DECISIONS})"
        f" AND (from_state IS NULL OR from_state IN {_STATES})",
        name="states",
    ),
)
