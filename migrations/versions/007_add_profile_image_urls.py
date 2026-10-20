from alembic import op
import sqlalchemy as sa


revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("students", sa.Column("image_url", sa.String(length=500), nullable=True))
    op.alter_column("teachers", "photo_url", new_column_name="image_url")


def downgrade() -> None:
    op.alter_column("teachers", "image_url", new_column_name="photo_url")
    op.drop_column("students", "image_url")
