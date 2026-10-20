from alembic import op


revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Keep generated codes unique when the sequence is introduced to a database
    # that already contains students. The suffix is globally increasing even
    # though the visible year component changes annually.
    op.execute(
        """
        SELECT setval(
            'student_code_seq',
            COALESCE(MAX((regexp_match(student_code, '-([0-9]+)$'))[1]::bigint), 1),
            MAX((regexp_match(student_code, '-([0-9]+)$'))[1]) IS NOT NULL
        )
        FROM students
        """
    )


def downgrade() -> None:
    # Do not rewind a live sequence: codes generated after this migration may
    # already have been persisted.
    pass
