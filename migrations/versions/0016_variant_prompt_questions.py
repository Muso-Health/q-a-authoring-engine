"""variant generation seeded with the question-answer pair — {existing_questions} placeholder

Revision ID: 0016_variant_prompt_questions
Revises: 0015_scoped_role_assignments
Create Date: 2026-10-26

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0016_variant_prompt_questions"
down_revision: str | None = "0015_scoped_role_assignments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copies: the defaults as of this revision, never imported from the app.
_OLD_DEFAULT = """\
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
- Return one question per line, with no numbering and no commentary."""

_NEW_DEFAULT = """\
You help build a clinically reviewed question-and-answer corpus for a community health \
programme in Mali.
Below are an answer and the questions already associated with it (there may be none yet). Write \
several new, distinct questions in {language} that a patient, a caregiver or a community health \
worker could ask to obtain this answer.

Context:
{context}

Answer:
{answer}

Questions already associated with this answer:
{existing_questions}

Rules:
- Every question must be fully answered by the answer above. Do not introduce clinical facts, \
symptoms or treatments that the answer does not cover.
- Do not repeat or merely reword any question already associated with the answer, and make each \
new question distinct from the others.
- Match the style and register of the existing questions, while varying wording and sentence \
structure as real people would ask. With no existing question, vary the register from formal to \
colloquial.
- Write natural {language}; do not translate word for word from another language.
- Return one question per line, with no numbering and no commentary."""

# Appended to an edited template, which must now use the new placeholder to stay valid.
_SUFFIX = "\n\nQuestions already associated with this answer:\n{existing_questions}"

_KEY = "variant_generation"


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("UPDATE prompt_templates SET content = :new WHERE key = :key AND content = :old"),
        {"new": _NEW_DEFAULT, "old": _OLD_DEFAULT, "key": _KEY},
    )
    bind.execute(
        sa.text(
            "UPDATE prompt_templates SET content = content || :suffix "
            "WHERE key = :key AND strpos(content, '{existing_questions}') = 0"
        ),
        {"suffix": _SUFFIX, "key": _KEY},
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("UPDATE prompt_templates SET content = :old WHERE key = :key AND content = :new"),
        {"new": _NEW_DEFAULT, "old": _OLD_DEFAULT, "key": _KEY},
    )
    bind.execute(
        sa.text(
            "UPDATE prompt_templates SET content = replace(content, :suffix, '') "
            "WHERE key = :key AND right(content, length(:suffix)) = :suffix"
        ),
        {"suffix": _SUFFIX, "key": _KEY},
    )
    # Any remaining use of the placeholder would not validate against the previous revision.
    bind.execute(
        sa.text(
            "UPDATE prompt_templates SET content = replace(content, '{existing_questions}', '') "
            "WHERE key = :key"
        ),
        {"key": _KEY},
    )
