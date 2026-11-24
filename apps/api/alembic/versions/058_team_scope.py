"""per-team services, jobs, shift templates, and user team assignment

Revision ID: 058
Revises: 057
Create Date: 2026-11-23

Copies each existing service, invoice job, and shift template onto every
team, then those lists diverge. A line item that already names a team stays
on that team's copy of the service. A line item with no team is kept on the
oldest team and copied to the others with a suffixed code.
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa

revision: str = "058"
down_revision: Union[str, None] = "057"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _copy_catalogs(bind, locations: list) -> None:
    spus = bind.execute(
        sa.text(
            "SELECT id, code, name_zh, name_en, subject, description, is_active, created_at, updated_at "
            "FROM course_spus WHERE location_id IS NULL"
        )
    ).mappings().all()
    spu_for = {}
    for spu in spus:
        for loc in locations:
            new_id = uuid.uuid4()
            bind.execute(
                sa.text(
                    "INSERT INTO course_spus "
                    "(id, code, name_zh, name_en, subject, description, is_active, created_at, updated_at, location_id) "
                    "VALUES (:id, :code, :name_zh, :name_en, :subject, :description, :is_active, :created_at, :updated_at, :location_id)"
                ),
                {**dict(spu), "id": new_id, "location_id": loc},
            )
            spu_for[(spu["id"], loc)] = new_id

    skus = bind.execute(sa.text("SELECT * FROM course_skus")).mappings().all()
    for sku in skus:
        home = sku["location_id"] if sku["location_id"] in locations else locations[0]
        bind.execute(
            sa.text("UPDATE course_skus SET spu_id = :spu_id, location_id = :location_id WHERE id = :id"),
            {"id": sku["id"], "spu_id": spu_for[(sku["spu_id"], home)], "location_id": home},
        )
        if sku["location_id"] in locations:
            continue
        code = sku["code"]
        for loc in locations:
            if loc == home:
                continue
            copy = dict(sku)
            copy["id"] = uuid.uuid4()
            copy["spu_id"] = spu_for[(sku["spu_id"], loc)]
            copy["location_id"] = loc
            suffix = str(loc).replace("-", "")[:6]
            copy["code"] = f"{code}-{suffix}"[:100]
            columns = ", ".join(copy.keys())
            params = ", ".join(f":{key}" for key in copy.keys())
            bind.execute(sa.text(f"INSERT INTO course_skus ({columns}) VALUES ({params})"), copy)

    bind.execute(sa.text("DELETE FROM course_spus WHERE location_id IS NULL"))

    jobs = bind.execute(
        sa.text("SELECT id, name, created_at FROM invoice_job_options WHERE location_id IS NULL")
    ).mappings().all()
    for job in jobs:
        for loc in locations:
            bind.execute(
                sa.text(
                    "INSERT INTO invoice_job_options (id, name, created_at, location_id) "
                    "VALUES (:id, :name, :created_at, :location_id)"
                ),
                {"id": uuid.uuid4(), "name": job["name"], "created_at": job["created_at"], "location_id": loc},
            )
    if jobs:
        bind.execute(sa.text("DELETE FROM invoice_job_options WHERE location_id IS NULL"))

    templates = bind.execute(
        sa.text(
            "SELECT id, name, start_time, end_time, color, sort_order, created_at, updated_at "
            "FROM shift_templates WHERE location_id IS NULL"
        )
    ).mappings().all()
    template_for = {}
    for template in templates:
        for loc in locations:
            new_id = uuid.uuid4()
            bind.execute(
                sa.text(
                    "INSERT INTO shift_templates "
                    "(id, name, start_time, end_time, color, sort_order, created_at, updated_at, location_id) "
                    "VALUES (:id, :name, :start_time, :end_time, :color, :sort_order, :created_at, :updated_at, :location_id)"
                ),
                {**dict(template), "id": new_id, "location_id": loc},
            )
            template_for[(template["id"], loc)] = new_id
    shifts = bind.execute(
        sa.text("SELECT id, template_id, location_id FROM shifts WHERE template_id IS NOT NULL")
    ).mappings().all()
    for shift in shifts:
        new_template = template_for.get((shift["template_id"], shift["location_id"]))
        if new_template is None:
            continue
        bind.execute(
            sa.text("UPDATE shifts SET template_id = :template_id WHERE id = :id"),
            {"id": shift["id"], "template_id": new_template},
        )
    if templates:
        bind.execute(sa.text("DELETE FROM shift_templates WHERE location_id IS NULL"))


def upgrade() -> None:
    op.create_table(
        "user_locations",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "location_id"),
    )
    op.add_column("course_spus", sa.Column("location_id", sa.Uuid(), nullable=True))
    op.add_column("invoice_job_options", sa.Column("location_id", sa.Uuid(), nullable=True))
    op.add_column("shift_templates", sa.Column("location_id", sa.Uuid(), nullable=True))
    op.drop_constraint("course_spus_code_key", "course_spus", type_="unique")
    op.drop_constraint("invoice_job_options_name_key", "invoice_job_options", type_="unique")

    bind = op.get_bind()
    locations = [row[0] for row in bind.execute(sa.text("SELECT id FROM locations ORDER BY created_at"))]
    if locations:
        _copy_catalogs(bind, locations)

    op.alter_column("course_spus", "location_id", nullable=False)
    op.alter_column("invoice_job_options", "location_id", nullable=False)
    op.alter_column("shift_templates", "location_id", nullable=False)
    op.alter_column("course_skus", "location_id", nullable=False)
    op.create_foreign_key("fk_course_spus_location_id", "course_spus", "locations", ["location_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key(
        "fk_invoice_job_options_location_id", "invoice_job_options", "locations", ["location_id"], ["id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "fk_shift_templates_location_id", "shift_templates", "locations", ["location_id"], ["id"], ondelete="CASCADE"
    )
    op.create_unique_constraint("uq_course_spus_location_code", "course_spus", ["location_id", "code"])
    op.create_unique_constraint("uq_invoice_jobs_location_name", "invoice_job_options", ["location_id", "name"])
    op.create_index("ix_course_spus_location_id", "course_spus", ["location_id"])
    op.create_index("ix_invoice_job_options_location_id", "invoice_job_options", ["location_id"])
    op.create_index("ix_shift_templates_location_id", "shift_templates", ["location_id"])


def downgrade() -> None:
    op.drop_index("ix_shift_templates_location_id", table_name="shift_templates")
    op.drop_index("ix_invoice_job_options_location_id", table_name="invoice_job_options")
    op.drop_index("ix_course_spus_location_id", table_name="course_spus")
    op.drop_constraint("uq_invoice_jobs_location_name", "invoice_job_options", type_="unique")
    op.drop_constraint("uq_course_spus_location_code", "course_spus", type_="unique")
    op.drop_constraint("fk_shift_templates_location_id", "shift_templates", type_="foreignkey")
    op.drop_constraint("fk_invoice_job_options_location_id", "invoice_job_options", type_="foreignkey")
    op.drop_constraint("fk_course_spus_location_id", "course_spus", type_="foreignkey")
    op.execute(
        sa.text(
            "DELETE FROM course_spus a USING course_spus b "
            "WHERE a.code = b.code AND a.id <> b.id AND a.created_at > b.created_at"
        )
    )
    op.drop_column("course_spus", "location_id")
    op.drop_column("invoice_job_options", "location_id")
    op.drop_column("shift_templates", "location_id")
    op.create_unique_constraint("course_spus_code_key", "course_spus", ["code"])
    op.create_unique_constraint("invoice_job_options_name_key", "invoice_job_options", ["name"])
    op.drop_table("user_locations")
