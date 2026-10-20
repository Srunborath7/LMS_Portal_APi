from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "students",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("auth_id", sa.Uuid(), sa.ForeignKey("auths.id", ondelete="SET NULL"), nullable=True),
        sa.Column("student_code", sa.String(20), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("gender", sa.String(20), nullable=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("guardian_name", sa.String(150), nullable=True),
        sa.Column("guardian_phone", sa.String(20), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("enrolled_at", sa.Date(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), sa.ForeignKey("auths.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by_id", sa.Uuid(), sa.ForeignKey("auths.id", ondelete="SET NULL"), nullable=True),
        sa.UniqueConstraint("auth_id", name="uq_students_auth_id"),
        sa.UniqueConstraint("student_code", name="uq_students_student_code"),
    )
    op.create_index("uq_students_email_lower", "students", [sa.text("lower(email)")], unique=True)
    op.create_index("uq_students_phone", "students", ["phone"], unique=True,
                    postgresql_where=sa.text("phone IS NOT NULL"))
    op.create_index("ix_students_status", "students", ["status"])
    op.create_index("ix_students_name", "students", ["last_name", "first_name"])
    op.create_index("ix_students_created_by_id", "students", ["created_by_id"])
    op.create_index("ix_students_updated_by_id", "students", ["updated_by_id"])


def downgrade() -> None:
    op.drop_table("students")  # indexes and constraints go with it
