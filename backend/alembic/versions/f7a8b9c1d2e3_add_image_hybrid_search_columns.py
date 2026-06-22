"""add_image_hybrid_search_columns

Adds description (TEXT) and search_vector (TSVECTOR) columns to image_embeddings
for hybrid semantic + full-text + trigram search.

Revision ID: f7a8b9c1d2e3
Revises: 10c5b7419334
Create Date: 2026-06-22

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'f7a8b9c1d2e3'
down_revision: Union[str, None] = '10c5b7419334'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.execute("ALTER TABLE image_embeddings ADD COLUMN IF NOT EXISTS description TEXT")
    op.execute("ALTER TABLE image_embeddings ADD COLUMN IF NOT EXISTS search_vector TSVECTOR")

    # GIN index for fast full-text search on the tsvector column
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_image_embeddings_search_vector "
        "ON image_embeddings USING GIN (search_vector)"
    )
    # GIN trigram index on description for fuzzy keyword matching (pg_trgm)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_image_embeddings_desc_trgm "
        "ON image_embeddings USING GIN (description gin_trgm_ops) "
        "WHERE description IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_image_embeddings_desc_trgm")
    op.execute("DROP INDEX IF EXISTS ix_image_embeddings_search_vector")
    op.execute("ALTER TABLE image_embeddings DROP COLUMN IF EXISTS search_vector")
    op.execute("ALTER TABLE image_embeddings DROP COLUMN IF EXISTS description")
