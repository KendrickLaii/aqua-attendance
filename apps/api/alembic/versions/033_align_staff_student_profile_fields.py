"""align staff and student profile fields

Revision ID: 033
Revises: f8e65b7cf82b
Create Date: 2026-07-28

This migration is intentionally defensive because early local copies of
``f8e65b7cf82b`` moved only part of the profile schema. It safely converges
both fresh and already-upgraded databases to the final profile layout:

- student_profiles: gender/date_of_birth, no enrollment/graduation dates
- staff_profiles: gender/date_of_birth
- units: start_date/exit_date are the canonical lifecycle dates
"""
from typing import Sequence, Union

from alembic import op


revision: str = "033"
down_revision: Union[str, None] = "f8e65b7cf82b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE staff_profiles ADD COLUMN IF NOT EXISTS gender VARCHAR(20)")
    op.execute("ALTER TABLE staff_profiles ADD COLUMN IF NOT EXISTS date_of_birth DATE")
    op.execute("ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS gender VARCHAR(20)")
    op.execute("ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS date_of_birth DATE")

    # Preserve any remaining student lifecycle dates on units before removing
    # the profile columns. This block no-ops once those columns are gone.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'student_profiles'
                  AND column_name = 'enrollment_date'
            ) THEN
                UPDATE units
                SET start_date = COALESCE(units.start_date, sp.enrollment_date)
                FROM student_profiles sp
                WHERE units.id = sp.id
                  AND units.unit_type = 'student';
            END IF;

            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'student_profiles'
                  AND column_name = 'graduation_date'
            ) THEN
                UPDATE units
                SET exit_date = COALESCE(units.exit_date, sp.graduation_date)
                FROM student_profiles sp
                WHERE units.id = sp.id
                  AND units.unit_type = 'student';
            END IF;
        END $$;
        """
    )

    # If this migration is run against a database that still has unit-level
    # personal data, backfill both profile tables before dropping those columns.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'units'
                  AND column_name = 'gender'
            ) THEN
                UPDATE student_profiles
                SET gender = COALESCE(student_profiles.gender, u.gender)
                FROM units u
                WHERE student_profiles.id = u.id
                  AND u.unit_type = 'student';

                UPDATE staff_profiles
                SET gender = COALESCE(staff_profiles.gender, u.gender)
                FROM units u
                WHERE staff_profiles.id = u.id
                  AND u.unit_type = 'staff';
            END IF;

            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'units'
                  AND column_name = 'date_of_birth'
            ) THEN
                UPDATE student_profiles
                SET date_of_birth = COALESCE(student_profiles.date_of_birth, u.date_of_birth)
                FROM units u
                WHERE student_profiles.id = u.id
                  AND u.unit_type = 'student';

                UPDATE staff_profiles
                SET date_of_birth = COALESCE(staff_profiles.date_of_birth, u.date_of_birth)
                FROM units u
                WHERE staff_profiles.id = u.id
                  AND u.unit_type = 'staff';
            END IF;
        END $$;
        """
    )

    op.execute("ALTER TABLE student_profiles DROP COLUMN IF EXISTS enrollment_date")
    op.execute("ALTER TABLE student_profiles DROP COLUMN IF EXISTS graduation_date")


def downgrade() -> None:
    op.execute("ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS enrollment_date DATE")
    op.execute("ALTER TABLE student_profiles ADD COLUMN IF NOT EXISTS graduation_date DATE")
    op.execute(
        """
        UPDATE student_profiles
        SET enrollment_date = u.start_date,
            graduation_date = u.exit_date
        FROM units u
        WHERE student_profiles.id = u.id
          AND u.unit_type = 'student'
        """
    )
    op.execute("ALTER TABLE staff_profiles DROP COLUMN IF EXISTS date_of_birth")
    op.execute("ALTER TABLE staff_profiles DROP COLUMN IF EXISTS gender")
