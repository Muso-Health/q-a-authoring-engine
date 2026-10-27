"""translation guided by the Muso glossary — {glossary} placeholder

Revision ID: 0019_translation_glossary
Revises: 0018_glossary
Create Date: 2026-10-27

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0019_translation_glossary"
down_revision: str | None = "0018_glossary"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copies: the defaults as of this revision, never imported from the app.
_OLD_DEFAULT = """\
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
{text}"""

_NEW_DEFAULT = """\
You are a professional medical translator working for a community health programme in Mali.
Translate the text below from {source_language} into {target_language}.

Rules:
- Translate faithfully: keep every clinical fact, instruction, dose, number and warning. Add \
nothing and omit nothing.
- Preserve the register and tone of the source: plain, respectful language suited to patients \
and community health workers.
- Keep medical terms accurate. When {target_language} has no established term, use the term \
commonly understood locally and keep the meaning unambiguous.
- Follow the Muso glossary below: when a listed source term appears in the text, translate it \
with the {target_language} form given, and never use the alternatives listed to avoid. These \
preferred translations take precedence over any other wording.
- Keep names, numbers, units and line breaks as they are.
- Return only the translation, with no explanation or commentary.

Muso glossary (source term → preferred {target_language} form):
{glossary}

Text to translate:
{text}"""

# Appended to an edited template, which must now use the new placeholder to stay valid.
_SUFFIX = (
    "\n\nMuso glossary: when a source term listed below appears in the text, translate it with "
    "the {target_language} form given and never use the alternatives listed to avoid.\n"
    "{glossary}"
)

_KEY = "translation"


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("UPDATE prompt_templates SET content = :new WHERE key = :key AND content = :old"),
        {"new": _NEW_DEFAULT, "old": _OLD_DEFAULT, "key": _KEY},
    )
    bind.execute(
        sa.text(
            "UPDATE prompt_templates SET content = content || :suffix "
            "WHERE key = :key AND strpos(content, '{glossary}') = 0"
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
            "UPDATE prompt_templates SET content = replace(content, '{glossary}', '') "
            "WHERE key = :key"
        ),
        {"key": _KEY},
    )
