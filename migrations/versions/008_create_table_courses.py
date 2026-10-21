from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS course_code_seq START 1")
    op.create_table(
        "courses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("course_code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("objectives", sa.Text()),
        sa.Column("category", sa.String(100)),
        sa.Column("level", sa.String(20), nullable=False, server_default="all_levels"),
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("thumbnail_url", sa.String(500)),
        sa.Column("duration_hours", sa.Numeric(6, 1)),
        sa.Column("fee", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), sa.ForeignKey("auths.id", ondelete="SET NULL")),
        sa.Column("updated_by_id", sa.Uuid(), sa.ForeignKey("auths.id", ondelete="SET NULL")),
        sa.UniqueConstraint("course_code", name="uq_courses_course_code"),
        sa.CheckConstraint("fee >= 0", name="ck_courses_fee_nonneg"),
        sa.CheckConstraint("duration_hours IS NULL OR duration_hours > 0", name="ck_courses_duration_pos"),
    )
    op.create_index("uq_courses_name_lower", "courses", [sa.text("lower(name)")], unique=True,
                    postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("ix_courses_status", "courses", ["status"])
    op.create_index("ix_courses_category", "courses", ["category"])
    op.create_index("ix_courses_level", "courses", ["level"])
    op.create_index("ix_courses_created_by_id", "courses", ["created_by_id"])
    op.create_index("ix_courses_updated_by_id", "courses", ["updated_by_id"])


def downgrade() -> None:
    op.drop_table("courses")
    op.execute("DROP SEQUENCE IF EXISTS course_code_seq")