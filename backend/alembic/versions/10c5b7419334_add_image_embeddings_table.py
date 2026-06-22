"""add_image_embeddings_table

Adds the image_embeddings table used by the semantic image search feature.

Prerequisites:
    The pgvector PostgreSQL extension must be installed on the database server.
    This migration enables it automatically via CREATE EXTENSION IF NOT EXISTS.

Revision ID: 10c5b7419334
Revises: ee5917e9826f
Create Date: 2026-06-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '10c5b7419334'
down_revision: Union[str, None] = 'ee5917e9826f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_EMBEDDING_DIM = 1024


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        'image_embeddings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('item_id', sa.String(), nullable=False),
        sa.Column('environment', sa.String(), nullable=False),
        sa.Column('site_id', sa.String(), nullable=False),
        sa.Column('collection', sa.String(), nullable=False),
        sa.Column('media_path', sa.String(), nullable=False),
        sa.Column('item_name', sa.String(), nullable=False),
        sa.Column('alt_text', sa.String(), nullable=True),
        sa.Column('embedding', sa.Text(), nullable=False),
        sa.Column('indexed_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    # Alter the embedding column to the vector type after the extension is active
    op.execute(
        f"ALTER TABLE image_embeddings "
        f"ALTER COLUMN embedding TYPE vector({_EMBEDDING_DIM}) "
        f"USING embedding::vector({_EMBEDDING_DIM})"
    )

    op.create_index('ix_image_embeddings_item_id', 'image_embeddings', ['item_id'])
    op.create_index(
        'ix_image_embeddings_site', 'image_embeddings',
        ['site_id', 'environment', 'collection'],
    )
    op.create_unique_constraint(
        'uq_image_embedding', 'image_embeddings',
        ['item_id', 'environment', 'site_id'],
    )
    # IVFFlat index for approximate cosine similarity search
    # lists=100 suits up to ~1M vectors; adjust proportionally for larger datasets
    op.execute(
        "CREATE INDEX ix_image_embeddings_cosine "
        "ON image_embeddings USING ivfflat (embedding vector_cosine_ops) "
        "WITH (lists = 100)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_image_embeddings_cosine")
    op.drop_constraint('uq_image_embedding', 'image_embeddings', type_='unique')
    op.drop_index('ix_image_embeddings_site', table_name='image_embeddings')
    op.drop_index('ix_image_embeddings_item_id', table_name='image_embeddings')
    op.drop_table('image_embeddings')
