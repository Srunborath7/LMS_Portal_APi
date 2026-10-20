from alembic import op
import sqlalchemy as sa


revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "auths",
        sa.Column("role", sa.String(length=20), server_default="student", nullable=False),
    )
    op.create_check_constraint(
        "ck_auths_role",
        "auths",
        "role IN ('student', 'teacher', 'admin')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_auths_role", "auths", type_="check")
    op.drop_column("auths", "role")
