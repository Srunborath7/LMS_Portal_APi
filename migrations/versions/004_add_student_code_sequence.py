from alembic import op


revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE student_code_seq START WITH 1")


def downgrade() -> None:
    op.execute("DROP SEQUENCE student_code_seq")
