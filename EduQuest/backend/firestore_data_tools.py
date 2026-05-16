from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from firestore_primary_store import EduQuestPrimaryStore


def _find_user_by_email(store: EduQuestPrimaryStore, email: str) -> dict[str, Any] | None:
    return store.get_user_by_email(email.lower())


def _attempt_signature(attempt: dict[str, Any]) -> tuple[Any, ...]:
    created_at = attempt.get("created_at")
    created_key = created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at)
    return (
        attempt.get("user_id"),
        attempt.get("quiz_id"),
        round(float(attempt.get("score") or 0), 4),
        int(attempt.get("earned_xp") or 0),
        created_key,
    )


def backfill_demo_activity(
    store: EduQuestPrimaryStore,
    db: Session,
    *,
    now: datetime | None = None,
) -> dict[str, int]:
    store.ensure_bootstrapped(db)
    now = (now or datetime.utcnow()).replace(hour=12, minute=0, second=0, microsecond=0)
    report = {
        "users_created": 0,
        "completed_lessons_created": 0,
        "attempts_created": 0,
        "assignments_created": 0,
        "ai_logs_created": 0,
    }

    demo_users = [
        ("carol@eduquest.com", "Carol Nguyen", "student"),
        ("daniyar@eduquest.com", "Daniyar Omar", "student"),
    ]
    user_lookup: dict[str, dict[str, Any]] = {}
    for email, full_name, role in demo_users:
        user = _find_user_by_email(store, email)
        if not user:
            user = store.create_user(
                email=email,
                full_name=full_name,
                hashed_password="mock_hash_password123",
                role=role,
                db=db,
            )
            report["users_created"] += 1
        user_lookup[email] = user

    for email in [
        "student@eduquest.com",
        "alice@eduquest.com",
        "bob@eduquest.com",
        "carol@eduquest.com",
        "daniyar@eduquest.com",
    ]:
        user = _find_user_by_email(store, email)
        if user:
            user_lookup[email] = user

    lessons_by_title = {
        lesson["title"]: lesson
        for lesson in store.list_lessons()
    }
    quizzes_by_title = {
        quiz["title"]: quiz
        for quiz in store.list_quizzes()
    }

    completion_plan = [
        ("carol@eduquest.com", "Variables and Data Types", now - timedelta(days=8)),
        ("carol@eduquest.com", "Lists and Loops", now - timedelta(days=6)),
        ("carol@eduquest.com", "Functions and Problem Decomposition", now - timedelta(days=3)),
        ("daniyar@eduquest.com", "HTML Structure", now - timedelta(days=4)),
        ("daniyar@eduquest.com", "CSS Fundamentals", now - timedelta(days=3)),
        ("daniyar@eduquest.com", "Client-Server Communication", now - timedelta(days=1)),
        ("alice@eduquest.com", "Client-Server Communication", now - timedelta(days=2)),
    ]
    for email, lesson_title, completed_at in completion_plan:
        user = user_lookup.get(email)
        lesson = lessons_by_title.get(lesson_title)
        if not user or not lesson:
            continue
        existing = store.get_completed_lesson(user["id"], lesson["id"])
        if existing:
            continue
        store.create_completed_lesson(user["id"], lesson["id"], db=db)
        report["completed_lessons_created"] += 1

    existing_attempt_signatures = {
        _attempt_signature(attempt)
        for attempt in store.list_attempts()
        if attempt.get("user_id") is not None and attempt.get("quiz_id") is not None
    }

    attempt_plan = [
        ("carol@eduquest.com", "Variables and Data Types Quiz", 0.71, 71, now - timedelta(days=8)),
        ("carol@eduquest.com", "Lists and Loops Quiz", 0.57, 57, now - timedelta(days=7)),
        ("carol@eduquest.com", "Lists and Loops Quiz", 0.86, 86, now - timedelta(days=6)),
        ("carol@eduquest.com", "Functions and Problem Decomposition Quiz", 0.8, 80, now - timedelta(days=3)),
        ("daniyar@eduquest.com", "HTML Structure Quiz", 0.71, 71, now - timedelta(days=4)),
        ("daniyar@eduquest.com", "CSS Fundamentals Quiz", 0.86, 86, now - timedelta(days=3)),
        ("daniyar@eduquest.com", "Client-Server Communication Quiz", 0.71, 71, now - timedelta(days=1)),
        ("alice@eduquest.com", "Client-Server Communication Quiz", 0.86, 86, now - timedelta(days=2)),
        ("bob@eduquest.com", "Forms and Validation Quiz", 0.75, 75, now - timedelta(hours=18)),
    ]
    for email, quiz_title, score, xp, created_at in attempt_plan:
        user = user_lookup.get(email)
        quiz = quizzes_by_title.get(quiz_title)
        if not user or not quiz:
            continue
        signature = (
            user["id"],
            quiz["id"],
            round(float(score), 4),
            int(xp),
            created_at.isoformat(),
        )
        if signature in existing_attempt_signatures:
            continue
        profile = store.get_profile_by_user_id(user["id"])
        if not profile:
            continue
        current_xp = int(profile.get("xp") or 0) + int(xp)
        current_level = int(profile.get("level") or 1)
        new_level = current_level + 1 if current_xp > current_level * 500 else current_level
        store.create_attempt(
            payload={
                "user_id": user["id"],
                "quiz_id": quiz["id"],
                "score": score,
                "earned_xp": xp,
                "student_answers_json": "[]",
                "quiz_questions_snapshot_json": quiz.get("questions") or "[]",
                "wrong_answer_indexes_json": "[]",
                "created_at": created_at,
            },
            profile_updates={
                "xp": current_xp,
                "streak": int(profile.get("streak") or 0) + 1,
                "level": new_level,
            },
            db=db,
        )
        existing_attempt_signatures.add(signature)
        report["attempts_created"] += 1

    existing_assignments = {
        (item.get("course_id"), item.get("quiz_id"), item.get("title"))
        for item in store.list_assignments()
    }
    assignment_plan = [
        ("Python Programming Basics", "Lists and Loops Quiz", "Loop mastery check", True, 4),
        ("Web Development Fundamentals", "Forms and Validation Quiz", "Validation review checkpoint", True, 6),
        ("Web Development Fundamentals", "CSS Fundamentals Quiz", "Responsive styling practice", False, 8),
    ]
    courses_by_title = {course["title"]: course for course in store.list_courses()}
    for course_title, quiz_title, title, is_published, due_in_days in assignment_plan:
        course = courses_by_title.get(course_title)
        quiz = quizzes_by_title.get(quiz_title)
        if not course or not quiz:
            continue
        key = (course["id"], quiz["id"], title)
        if key in existing_assignments:
            continue
        store.create_assignment(
            {
                "quiz_id": quiz["id"],
                "course_id": course["id"],
                "title": title,
                "instructions": f"Complete {title.lower()} after revising the lesson.",
                "due_at": now + timedelta(days=due_in_days),
                "is_published": is_published,
            },
            db=db,
        )
        existing_assignments.add(key)
        report["assignments_created"] += 1

    existing_log_keys = {
        (item.get("user_id"), item.get("context"), item.get("question"))
        for item in store.list_ai_logs()
    }
    ai_log_plan = [
        ("carol@eduquest.com", "Lists and Loops", "Why does the retry score improve after practice?", "Because repeated attempts reinforce recall and pattern recognition.", 40),
        ("daniyar@eduquest.com", "Client-Server Communication", "Why should API contracts stay stable for mobile screens?", "Stable response fields prevent frontend parsing from breaking after deploys.", 22),
        ("student@eduquest.com", "Forms and Validation", "Why do we validate on the server too?", "Server validation protects shared data even when client checks are bypassed.", 10),
    ]
    for email, context, question, hint, hours_ago in ai_log_plan:
        user = user_lookup.get(email)
        if not user:
            continue
        key = (user["id"], context, question)
        if key in existing_log_keys:
            continue
        store.create_ai_log(
            {
                "user_id": user["id"],
                "context": context,
                "question": question,
                "hint": hint,
                "timestamp": now - timedelta(hours=hours_ago),
            },
            db=db,
        )
        existing_log_keys.add(key)
        report["ai_logs_created"] += 1

    return report


def repair_firestore_data(
    store: EduQuestPrimaryStore,
    db: Session,
) -> dict[str, int]:
    store.ensure_bootstrapped(db)
    report = {
        "users_repaired": 0,
        "legacy_users_repaired": 0,
        "attempts_flagged": 0,
    }

    for user in store.list_users():
        patched = dict(user)
        changed = False
        if not str(user.get("full_name") or "").strip():
            patched["full_name"] = store.user_display_name(user)
            changed = True
        if not str(user.get("email") or "").strip() and str(user.get("firebase_uid") or "").strip():
            patched["email"] = store.user_email(user)
            changed = True
        if not changed:
            continue

        user_id = user.get("id")
        if isinstance(user_id, int) or (isinstance(user_id, str) and user_id.isdigit()):
            store.update_user(int(user_id), patched, db=db)
            report["users_repaired"] += 1
        else:
            store.backend.set_doc("users", str(user_id), patched)
            report["legacy_users_repaired"] += 1

    for attempt in store.list_attempts():
        if attempt.get("quiz_id") is None or attempt.get("user_id") is None or attempt.get("score") is None:
            report["attempts_flagged"] += 1

    return report
