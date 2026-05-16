from __future__ import annotations

from database import SessionLocal
from firestore_data_tools import backfill_demo_activity
from firestore_primary_store import get_store


def main() -> None:
    db = SessionLocal()
    try:
        report = backfill_demo_activity(get_store(), db)
    finally:
        db.close()
    print(report)


if __name__ == "__main__":
    main()
