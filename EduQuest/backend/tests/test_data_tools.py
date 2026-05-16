import database
from firestore_data_tools import backfill_demo_activity, repair_firestore_data
from firestore_primary_store import get_store


def test_demo_backfill_is_additive_and_idempotent(client):
    store = get_store()
    db = database.SessionLocal()
    try:
        first = backfill_demo_activity(store, db)
        second = backfill_demo_activity(store, db)
    finally:
        db.close()

    assert first["attempts_created"] >= 1
    assert first["completed_lessons_created"] >= 1
    assert second == {
        "users_created": 0,
        "completed_lessons_created": 0,
        "attempts_created": 0,
        "assignments_created": 0,
        "ai_logs_created": 0,
    }


def test_repair_firestore_data_fills_missing_user_name_and_flags_broken_attempts(client, seeded_ids):
    store = get_store()
    db = database.SessionLocal()
    try:
        store.ensure_bootstrapped(db)
        store.update_user(seeded_ids["student@eduquest.com"], {"full_name": ""}, db=db)
        store.backend.set_doc(
            "attempts",
            "broken-attempt",
            {"id": "broken-attempt", "user_id": seeded_ids["student@eduquest.com"]},
        )
        report = repair_firestore_data(store, db)
        repaired_user = store.get_user_by_id(seeded_ids["student@eduquest.com"])
    finally:
        db.close()

    assert report["users_repaired"] >= 1
    assert report["attempts_flagged"] >= 1
    assert repaired_user["full_name"]
