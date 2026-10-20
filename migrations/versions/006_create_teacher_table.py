from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS teacher_code_seq START 1")
    op.create_table(
        "teachers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("auth_id", sa.Uuid(), sa.ForeignKey("auths.id", ondelete="SET NULL")),
        sa.Column("teacher_code", sa.String(20), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("date_of_birth", sa.Date()),
        sa.Column("gender", sa.String(20)),
        sa.Column("nationality", sa.String(50)),
        sa.Column("photo_url", sa.String(500)),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(20)),
        sa.Column("address", sa.Text()),
        sa.Column("emergency_contact_name", sa.String(150)),
        sa.Column("emergency_contact_phone", sa.String(20)),
        sa.Column("title", sa.String(50)),
        sa.Column("highest_degree", sa.String(100)),
        sa.Column("specialization", sa.String(150)),
        sa.Column("years_of_experience", sa.Integer()),
        sa.Column("bio", sa.Text()),
        sa.Column("employment_type", sa.String(20), nullable=False, server_default="full_time"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("hire_date", sa.Date()),
        sa.Column("end_date", sa.Date()),
        sa.Column("hourly_rate", sa.Numeric(10, 2)),
        sa.Column("note", sa.Text()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), sa.ForeignKey("auths.id", ondelete="SET NULL")),
        sa.Column("updated_by_id", sa.Uuid(), sa.ForeignKey("auths.id", ondelete="SET NULL")),
        sa.UniqueConstraint("auth_id", name="uq_teachers_auth_id"),
        sa.UniqueConstraint("teacher_code", name="uq_teachers_teacher_code"),
    )
    op.create_index("uq_teachers_email_lower", "teachers", [sa.text("lower(email)")], unique=True)
    op.create_index("uq_teachers_phone", "teachers", ["phone"], unique=True,
                    postgresql_where=sa.text("phone IS NOT NULL"))
    op.create_index("ix_teachers_status", "teachers", ["status"])
    op.create_index("ix_teachers_name", "teachers", ["last_name", "first_name"])
    op.create_index("ix_teachers_created_by_id", "teachers", ["created_by_id"])
    op.create_index("ix_teachers_updated_by_id", "teachers", ["updated_by_id"])


def downgrade() -> None:
    op.drop_table("teachers")
    op.execute("DROP SEQUENCE IF EXISTS teacher_code_seq")