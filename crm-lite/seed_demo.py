"""Load 21 synthetic demonstration records bundled with the application."""

import csv
from pathlib import Path

from app import db, init_db


SAMPLE = Path(__file__).resolve().parent / "demo" / "crm_sample.csv"
FIELDS = (
    "name", "company", "email", "phone", "source", "industry", "country",
    "status", "stage", "amount", "probability", "close_date", "assignee",
    "priority", "satisfaction", "case_status",
)


def main():
    init_db()
    with SAMPLE.open(newline="", encoding="utf-8") as handle:
        records = list(csv.DictReader(handle))
    with db() as conn:
        if conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]:
            print("База уже содержит клиентов; импорт пропущен.")
            return
        placeholders = ", ".join("?" for _ in FIELDS)
        for row in records:
            values = [None if field == "satisfaction" and row[field] == "" else row[field] for field in FIELDS]
            conn.execute(f"INSERT INTO leads ({', '.join(FIELDS)}) VALUES ({placeholders})", values)
    print(f"Импортировано {len(records)} демонстрационных клиентов.")


if __name__ == "__main__":
    main()
