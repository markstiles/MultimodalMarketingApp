"""drop_conversations_user_fk

Drop the FK constraint on conversations.user_id so local-mode dev works without
a real users row, and so the app doesn't enforce user existence at the DB level.

Revision ID: ee5917e9826f
Revises: c5350ba7d7ac
Create Date: 2026-06-18 11:26:59.967923

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'ee5917e9826f'
down_revision: Union[str, None] = 'c5350ba7d7ac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('conversations_user_id_fkey', 'conversations', type_='foreignkey')


def downgrade() -> None:
    op.create_foreign_key(
        'conversations_user_id_fkey', 'conversations', 'users', ['user_id'], ['id']
    )
