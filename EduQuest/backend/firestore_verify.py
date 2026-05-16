import json

from database import SessionLocal
from firestore_primary_store import get_store


def main() -> None:
    db = SessionLocal()
    try:
        store = get_store()
        store.ensure_bootstrapped(db)
        report = store.consistency_report(db)
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    finally:
        db.close()


if __name__ == "__main__":
    main()
