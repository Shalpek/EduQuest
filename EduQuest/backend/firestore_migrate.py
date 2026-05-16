from database import SessionLocal
from firestore_primary_store import get_store


def main() -> None:
    db = SessionLocal()
    try:
        store = get_store()
        store.bootstrap_from_sqlite(db)
        print("Firestore bootstrap migration completed.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
