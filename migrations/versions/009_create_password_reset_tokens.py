"""Create one-time password reset tokens.

Revision ID: 009_create_password_reset_tokens
Revises: 008_create_table_courses
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("auth_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("auths.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_password_reset_tokens_auth_id", "password_reset_tokens", ["auth_id"])


def downgrade() -> None:
    op.drop_index("ix_password_reset_tokens_auth_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
