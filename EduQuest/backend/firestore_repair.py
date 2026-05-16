from __future__ import annotations

from database import SessionLocal
from firestore_data_tools import repair_firestore_data
from firestore_primary_store import get_store


def main() -> None:
    db = SessionLocal()
    try:
        report = repair_firestore_data(get_store(), db)
    finally:
        db.close()
    print(report)


if __name__ == "__main__":
    main()
