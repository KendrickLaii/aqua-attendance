import asyncio
from app.database import async_session_factory
from sqlalchemy import text

TABLES = [
    "units", "student_profiles", "staff_profiles", "attendance_events",
    "attendance_summaries", "audit_logs", "locations", "notifications",
    "payroll_records", "refresh_tokens", "users", "unit_scan_locations",
]

async def audit():
    async with async_session_factory() as s:
        for table in TABLES:
            r = await s.execute(text(
                "SELECT column_name, data_type, is_nullable, column_default "
                "FROM information_schema.columns "
                f"WHERE table_name = '{table}' AND table_schema = 'public' "
                "ORDER BY ordinal_position"
            ))
            cols = r.fetchall()
            print(f"\n=== {table} ===")
            for col in cols:
                print(f"  {col[0]:40s} {col[1]:20s} nullable={col[2]:3s} default={col[3]}")

        # Check all constraints
        r = await s.execute(text(
            "SELECT tc.table_name, tc.constraint_name, tc.constraint_type "
            "FROM information_schema.table_constraints tc "
            "WHERE tc.table_schema = 'public' "
            "ORDER BY tc.table_name, tc.constraint_name"
        ))
        print("\n=== CONSTRAINTS ===")
        for row in r.fetchall():
            print(f"  {row[0]:30s} {row[1]:50s} {row[2]}")

        # Check all indexes
        r = await s.execute(text(
            "SELECT schemaname, tablename, indexname, indexdef "
            "FROM pg_indexes WHERE schemaname = 'public' "
            "ORDER BY tablename, indexname"
        ))
        print("\n=== INDEXES ===")
        for row in r.fetchall():
            print(f"  {row[2]:55s} on {row[1]}")

        # Check alembic version
        r = await s.execute(text("SELECT version_num FROM alembic_version"))
        print(f"\n=== ALEMBIC VERSION: {r.scalar()} ===")

import sys
sys.stdout = open("audit_output.txt", "w", encoding="utf-8")
asyncio.run(audit())
sys.stdout.close()
