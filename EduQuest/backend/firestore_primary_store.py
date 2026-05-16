from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
import logging
import os
import threading
from types import SimpleNamespace
from typing import Any, Iterable

from firebase_admin import firestore
from sqlalchemy.orm import Session, sessionmaker

import models
from firebase_auth_provider import FirebaseConfigurationError, _firebase_app


logger = logging.getLogger("eduquest.firestore")


class PrimaryStoreError(RuntimeError):
    pass


class BackupSyncError(PrimaryStoreError):
    pass


class FirestoreBootstrapError(PrimaryStoreError):
    pass


COLLECTION_MODEL_MAP = {
    "system_config": models.SystemConfig,
    "ai_logs": models.AILog,
    "users": models.User,
    "gamification_profiles": models.GamificationProfile,
    "courses": models.Course,
    "lessons": models.Lesson,
    "completed_lessons": models.CompletedLesson,
    "quizzes": models.Quiz,
    "attempts": models.Attempt,
    "assignments": models.Assignment,
    "e_mode_sessions": models.EModeSession,
    "e_mode_messages": models.EModeMessage,
    "student_ai_sessions": models.StudentAISession,
    "student_ai_messages": models.StudentAIMessage,
}

BOOTSTRAP_ORDER = [
    "system_config",
    "users",
    "gamification_profiles",
    "courses",
    "lessons",
    "completed_lessons",
    "quizzes",
    "attempts",
    "assignments",
    "e_mode_sessions",
    "e_mode_messages",
    "student_ai_sessions",
    "student_ai_messages",
    "ai_logs",
]

ENTITY_COUNTS = [
    "users",
    "gamification_profiles",
    "courses",
    "lessons",
    "completed_lessons",
    "quizzes",
    "attempts",
    "assignments",
    "student_ai_sessions",
    "student_ai_messages",
    "e_mode_sessions",
    "e_mode_messages",
    "ai_logs",
]


def _datetime_fields(model_cls: type[models.Base]) -> set[str]:
    return {
        column.name
        for column in model_cls.__table__.columns
        if column.type.__class__.__name__ == "DateTime"
    }


DATETIME_FIELDS = {
    collection: _datetime_fields(model_cls)
    for collection, model_cls in COLLECTION_MODEL_MAP.items()
}


def _parse_datetime(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return value
    return value


def _sortable_id(value: Any) -> tuple[int, int | str]:
    if isinstance(value, int):
        return (0, value)
    if isinstance(value, str) and value.isdigit():
        return (0, int(value))
    return (1, str(value))


def _sortable_int(value: Any, *, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _sortable_datetime(value: Any) -> datetime:
    if isinstance(value, str):
        value = _parse_datetime(value)
    if not isinstance(value, datetime):
        return datetime.min.replace(tzinfo=timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _safe_display_name(user: dict[str, Any] | None) -> str:
    if not user:
        return "Unknown user"
    full_name = str(user.get("full_name") or "").strip()
    if full_name:
        return full_name
    email = str(user.get("email") or "").strip()
    if email:
        local_part = email.split("@", 1)[0].strip()
        return local_part or email
    firebase_uid = str(user.get("firebase_uid") or "").strip()
    if firebase_uid:
        return firebase_uid
    return "Unknown user"


def _safe_email(user: dict[str, Any] | None) -> str:
    if not user:
        return ""
    email = str(user.get("email") or "").strip()
    if email:
        return email
    firebase_uid = str(user.get("firebase_uid") or "").strip()
    return firebase_uid


def _attempt_has_required_fields(attempt: dict[str, Any], *required_fields: str) -> bool:
    for field in required_fields:
        if attempt.get(field) is None:
            return False
    return True


def _normalize_for_json(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_normalize_for_json(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize_for_json(item) for key, item in value.items()}
    return value


def _restore_doc(collection: str, data: dict[str, Any]) -> dict[str, Any]:
    restored = dict(data)
    for field in DATETIME_FIELDS.get(collection, set()):
        if field in restored:
            restored[field] = _parse_datetime(restored[field])
    return restored


def _model_to_doc(instance: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for column in instance.__table__.columns:
        payload[column.name] = getattr(instance, column.name)
    return payload


def _doc_to_record(data: dict[str, Any] | None) -> SimpleNamespace | None:
    if data is None:
        return None
    return SimpleNamespace(**data)


class JsonDocumentBackend:
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _read(self) -> dict[str, Any]:
        if not self.file_path.exists():
            return {"collections": {}, "_meta": {"counters": {}}}
        with self.file_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _write(self, payload: dict[str, Any]) -> None:
        with self.file_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

    def exists_any(self, collection: str) -> bool:
        with self._lock:
            data = self._read()
            return bool(data["collections"].get(collection))

    def all_docs(self, collection: str) -> list[dict[str, Any]]:
        with self._lock:
            data = self._read()
            collection_data = data["collections"].get(collection, {})
            return [
                _restore_doc(collection, dict(document))
                for document in collection_data.values()
            ]

    def get_doc(self, collection: str, document_id: int | str) -> dict[str, Any] | None:
        with self._lock:
            data = self._read()
            collection_data = data["collections"].get(collection, {})
            document = collection_data.get(str(document_id))
            if document is None:
                return None
            return _restore_doc(collection, dict(document))

    def set_doc(self, collection: str, document_id: int | str, payload: dict[str, Any]) -> None:
        with self._lock:
            data = self._read()
            data["collections"].setdefault(collection, {})
            data["collections"][collection][str(document_id)] = _normalize_for_json(payload)
            self._write(data)

    def next_id(self, collection: str) -> int:
        with self._lock:
            data = self._read()
            counters = data["_meta"].setdefault("counters", {})
            next_id = int(counters.get(collection, 0)) + 1
            counters[collection] = next_id
            self._write(data)
            return next_id

    def set_counter(self, collection: str, value: int) -> None:
        with self._lock:
            data = self._read()
            counters = data["_meta"].setdefault("counters", {})
            counters[collection] = max(int(counters.get(collection, 0)), int(value))
            self._write(data)


class FirestoreDocumentBackend:
    def __init__(self):
        try:
            self.client = firestore.client(app=_firebase_app())
        except FirebaseConfigurationError:
            raise
        except Exception as exc:  # pragma: no cover - SDK specific
            raise PrimaryStoreError(f"Unable to initialize Firestore client: {exc}") from exc

    def exists_any(self, collection: str) -> bool:
        docs = self.client.collection(collection).limit(1).stream()
        return any(True for _ in docs)

    def all_docs(self, collection: str) -> list[dict[str, Any]]:
        payload = []
        for snapshot in self.client.collection(collection).stream():
            document = snapshot.to_dict() or {}
            document.setdefault("id", int(snapshot.id) if snapshot.id.isdigit() else snapshot.id)
            payload.append(document)
        return payload

    def get_doc(self, collection: str, document_id: int | str) -> dict[str, Any] | None:
        snapshot = (
            self.client.collection(collection).document(str(document_id)).get()
        )
        if not snapshot.exists:
            return None
        document = snapshot.to_dict() or {}
        document.setdefault("id", int(snapshot.id) if snapshot.id.isdigit() else snapshot.id)
        return document

    def set_doc(self, collection: str, document_id: int | str, payload: dict[str, Any]) -> None:
        self.client.collection(collection).document(str(document_id)).set(payload)

    def next_id(self, collection: str) -> int:
        transaction = self.client.transaction()
        counter_ref = self.client.collection("_meta_counters").document(collection)

        @firestore.transactional
        def _allocate(transaction_obj):
            snapshot = counter_ref.get(transaction=transaction_obj)
            current_value = int(snapshot.get("value")) if snapshot.exists else 0
            next_value = current_value + 1
            transaction_obj.set(counter_ref, {"value": next_value})
            return next_value

        return int(_allocate(transaction))

    def set_counter(self, collection: str, value: int) -> None:
        counter_ref = self.client.collection("_meta_counters").document(collection)
        snapshot = counter_ref.get()
        current = int(snapshot.get("value")) if snapshot.exists else 0
        if value > current:
            counter_ref.set({"value": int(value)})


class SQLiteMirror:
    def sync_document(self, collection: str, payload: dict[str, Any], db: Session) -> None:
        model_cls = COLLECTION_MODEL_MAP[collection]
        row = db.query(model_cls).filter(model_cls.id == payload["id"]).first()
        if row is None:
            row = model_cls()
            db.add(row)

        for column in model_cls.__table__.columns:
            if column.name in payload:
                setattr(row, column.name, payload[column.name])

    def count_rows(self, collection: str, db: Session) -> int:
        model_cls = COLLECTION_MODEL_MAP[collection]
        return db.query(model_cls).count()


@dataclass
class WriteObservation:
    operation: str
    collection: str
    entity_id: int | str
    firestore_ok: bool
    sqlite_backup_ok: bool


class EduQuestPrimaryStore:
    def __init__(self):
        local_store_path = os.getenv("EDUQUEST_LOCAL_FIRESTORE_PATH")
        if local_store_path:
            self.backend = JsonDocumentBackend(Path(local_store_path))
        else:
            self.backend = FirestoreDocumentBackend()
        self.mirror = SQLiteMirror()
        self._bootstrapped = False

    def reset_bootstrap_state(self) -> None:
        self._bootstrapped = False

    def ensure_bootstrapped(self, db: Session) -> None:
        if self._bootstrapped:
            return
        if any(self.backend.exists_any(collection) for collection in ("users", "courses", "quizzes")):
            self._bootstrapped = True
            return
        has_sqlite_data = any(
            db.query(COLLECTION_MODEL_MAP[collection]).first() is not None
            for collection in ("users", "courses", "quizzes", "system_config")
        )
        if not has_sqlite_data:
            self._bootstrapped = True
            return
        self.bootstrap_from_sqlite(db)
        self._bootstrapped = True

    def bootstrap_from_sqlite(self, db: Session) -> None:
        try:
            for collection in BOOTSTRAP_ORDER:
                model_cls = COLLECTION_MODEL_MAP[collection]
                rows = db.query(model_cls).order_by(model_cls.id.asc()).all()
                max_id = 0
                for row in rows:
                    payload = _model_to_doc(row)
                    self.backend.set_doc(collection, payload["id"], payload)
                    max_id = max(max_id, int(payload["id"]))
                if max_id:
                    self.backend.set_counter(collection, max_id)
            logger.info("Firestore bootstrap completed from SQLite seed/runtime data")
        except Exception as exc:  # pragma: no cover - defensive
            raise FirestoreBootstrapError(
                f"Failed to migrate SQLite seed/runtime data into Firestore: {exc}"
            ) from exc

    def _write_with_backup(
        self,
        *,
        operation: str,
        writes: list[tuple[str, dict[str, Any]]],
        db: Session,
    ) -> None:
        observations: list[WriteObservation] = []
        for collection, payload in writes:
            self.backend.set_doc(collection, payload["id"], payload)
            observations.append(
                WriteObservation(
                    operation=operation,
                    collection=collection,
                    entity_id=payload["id"],
                    firestore_ok=True,
                    sqlite_backup_ok=False,
                )
            )

        try:
            for collection, payload in writes:
                self.mirror.sync_document(collection, payload, db)
            db.commit()
            for item in observations:
                item.sqlite_backup_ok = True
        except Exception as exc:
            db.rollback()
            for item in observations:
                logger.error(
                    "storage_write operation=%s entity=%s collection=%s firestore_ok=%s sqlite_backup_ok=%s",
                    item.operation,
                    item.entity_id,
                    item.collection,
                    item.firestore_ok,
                    item.sqlite_backup_ok,
                )
            raise BackupSyncError(
                f"Firestore write succeeded but SQLite backup failed during {operation}: {exc}"
            ) from exc

        for item in observations:
            logger.info(
                "storage_write operation=%s entity=%s collection=%s firestore_ok=%s sqlite_backup_ok=%s",
                item.operation,
                item.entity_id,
                item.collection,
                item.firestore_ok,
                item.sqlite_backup_ok,
            )

    def _all(self, collection: str) -> list[dict[str, Any]]:
        return [
            _restore_doc(collection, document)
            for document in self.backend.all_docs(collection)
        ]

    def _get(self, collection: str, document_id: int | str) -> dict[str, Any] | None:
        document = self.backend.get_doc(collection, document_id)
        if document is None:
            return None
        return _restore_doc(collection, document)

    def _find_one(self, collection: str, **criteria: Any) -> dict[str, Any] | None:
        for document in self._all(collection):
            if all(document.get(field) == value for field, value in criteria.items()):
                return document
        return None

    def _find_many(self, collection: str, **criteria: Any) -> list[dict[str, Any]]:
        matches = []
        for document in self._all(collection):
            if all(document.get(field) == value for field, value in criteria.items()):
                matches.append(document)
        return matches

    def _next_id(self, collection: str) -> int:
        return int(self.backend.next_id(collection))

    def _create(
        self,
        collection: str,
        payload: dict[str, Any],
        *,
        db: Session,
        operation: str,
    ) -> dict[str, Any]:
        payload = dict(payload)
        payload["id"] = self._next_id(collection)
        self._write_with_backup(operation=operation, writes=[(collection, payload)], db=db)
        return payload

    def _update(
        self,
        collection: str,
        document_id: int,
        fields: dict[str, Any],
        *,
        db: Session,
        operation: str,
    ) -> dict[str, Any]:
        existing = self._get(collection, document_id)
        if not existing:
            raise KeyError(f"{collection}:{document_id} not found")
        updated = {**existing, **fields, "id": document_id}
        self._write_with_backup(operation=operation, writes=[(collection, updated)], db=db)
        return updated

    def get_user_by_id(self, user_id: int) -> dict[str, Any] | None:
        return self._get("users", user_id)

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        return self._find_one("users", email=email.lower())

    def get_user_by_firebase_uid(self, firebase_uid: str) -> dict[str, Any] | None:
        return self._find_one("users", firebase_uid=firebase_uid)

    def list_users(self) -> list[dict[str, Any]]:
        return sorted(self._all("users"), key=lambda item: _sortable_id(item.get("id")))

    def user_display_name(self, user: dict[str, Any] | None) -> str:
        return _safe_display_name(user)

    def user_email(self, user: dict[str, Any] | None) -> str:
        return _safe_email(user)

    def create_user(
        self,
        *,
        email: str,
        full_name: str,
        hashed_password: str,
        role: str = "student",
        is_active: bool = True,
        firebase_uid: str | None = None,
        db: Session,
    ) -> dict[str, Any]:
        user = {
            "email": email.lower(),
            "firebase_uid": firebase_uid,
            "full_name": full_name,
            "hashed_password": hashed_password,
            "role": role,
            "is_active": is_active,
        }
        user["id"] = self._next_id("users")
        profile = {
            "id": self._next_id("gamification_profiles"),
            "user_id": user["id"],
            "xp": 0,
            "level": 1,
            "streak": 0,
        }
        self._write_with_backup(
            operation="create_user",
            writes=[("users", user), ("gamification_profiles", profile)],
            db=db,
        )
        return user

    def update_user(self, user_id: int, fields: dict[str, Any], db: Session) -> dict[str, Any]:
        if "email" in fields and fields["email"]:
            fields = {**fields, "email": str(fields["email"]).lower()}
        return self._update("users", user_id, fields, db=db, operation="update_user")

    def get_profile_by_user_id(self, user_id: int) -> dict[str, Any] | None:
        return self._find_one("gamification_profiles", user_id=user_id)

    def update_profile(self, profile_id: int, fields: dict[str, Any], db: Session) -> dict[str, Any]:
        return self._update(
            "gamification_profiles",
            profile_id,
            fields,
            db=db,
            operation="update_profile",
        )

    def get_system_config(self) -> dict[str, Any] | None:
        return self._get("system_config", 1) or next(iter(self._all("system_config")), None)

    def upsert_system_config(self, payload: dict[str, Any], db: Session) -> dict[str, Any]:
        config = self.get_system_config()
        if config:
            updated = {
                **config,
                **payload,
                "updated_at": datetime.utcnow(),
            }
            self._write_with_backup(
                operation="update_system_config",
                writes=[("system_config", updated)],
                db=db,
            )
            return updated
        config = {
            "id": 1,
            "ai_safety": payload.get("ai_safety", True),
            "retries_enabled": payload.get("retries_enabled", True),
            "xp_per_quiz": payload.get("xp_per_quiz", 100),
            "updated_at": datetime.utcnow(),
        }
        self._write_with_backup(
            operation="create_system_config",
            writes=[("system_config", config)],
            db=db,
        )
        self.backend.set_counter("system_config", 1)
        return config

    def list_courses(self) -> list[dict[str, Any]]:
        return sorted(self._all("courses"), key=lambda item: _sortable_id(item.get("id")))

    def get_course(self, course_id: int) -> dict[str, Any] | None:
        return self._get("courses", course_id)

    def create_course(self, title: str, description: str, db: Session) -> dict[str, Any]:
        return self._create(
            "courses",
            {"title": title, "description": description},
            db=db,
            operation="create_course",
        )

    def list_lessons_for_course(self, course_id: int) -> list[dict[str, Any]]:
        lessons = self._find_many("lessons", course_id=course_id)
        return sorted(lessons, key=lambda item: _sortable_int(item.get("order", 0)))

    def list_lessons(self) -> list[dict[str, Any]]:
        return sorted(
            self._all("lessons"),
            key=lambda item: (
                _sortable_int(item.get("course_id", 0)),
                _sortable_int(item.get("order", 0)),
                _sortable_id(item.get("id")),
            ),
        )

    def get_lesson(self, lesson_id: int) -> dict[str, Any] | None:
        return self._get("lessons", lesson_id)

    def create_lesson(
        self,
        *,
        course_id: int,
        title: str,
        content: str,
        order: int,
        db: Session,
    ) -> dict[str, Any]:
        return self._create(
            "lessons",
            {
                "course_id": course_id,
                "title": title,
                "content": content,
                "order": order,
            },
            db=db,
            operation="create_lesson",
        )

    def list_quizzes(self) -> list[dict[str, Any]]:
        return sorted(self._all("quizzes"), key=lambda item: _sortable_id(item.get("id")))

    def list_quizzes_for_lesson(self, lesson_id: int) -> list[dict[str, Any]]:
        quizzes = self._find_many("quizzes", lesson_id=lesson_id)
        return sorted(quizzes, key=lambda item: _sortable_id(item.get("id")))

    def get_quiz(self, quiz_id: int) -> dict[str, Any] | None:
        return self._get("quizzes", quiz_id)

    def get_quiz_by_lesson(self, lesson_id: int) -> dict[str, Any] | None:
        quizzes = self.list_quizzes_for_lesson(lesson_id)
        return quizzes[0] if quizzes else None

    def create_or_update_quiz(
        self,
        *,
        lesson_id: int,
        title: str,
        questions: str,
        xp_reward: int,
        db: Session,
    ) -> tuple[dict[str, Any], bool]:
        existing = self.get_quiz_by_lesson(lesson_id)
        if existing:
            updated = {
                **existing,
                "title": title,
                "questions": questions,
                "xp_reward": xp_reward,
            }
            self._write_with_backup(
                operation="update_quiz",
                writes=[("quizzes", updated)],
                db=db,
            )
            return updated, True
        created = self._create(
            "quizzes",
            {
                "lesson_id": lesson_id,
                "title": title,
                "questions": questions,
                "xp_reward": xp_reward,
            },
            db=db,
            operation="create_quiz",
        )
        return created, False

    def list_completed_lessons_for_user(self, user_id: int) -> list[dict[str, Any]]:
        completions = self._find_many("completed_lessons", user_id=user_id)
        return sorted(
            completions,
            key=lambda item: _sortable_datetime(item.get("completed_at")),
        )

    def get_completed_lesson(self, user_id: int, lesson_id: int) -> dict[str, Any] | None:
        return self._find_one("completed_lessons", user_id=user_id, lesson_id=lesson_id)

    def create_completed_lesson(self, user_id: int, lesson_id: int, db: Session) -> dict[str, Any]:
        return self._create(
            "completed_lessons",
            {
                "user_id": user_id,
                "lesson_id": lesson_id,
                "completed_at": datetime.utcnow(),
            },
            db=db,
            operation="create_completed_lesson",
        )

    def list_attempts(self) -> list[dict[str, Any]]:
        return sorted(
            self._all("attempts"),
            key=lambda item: _sortable_datetime(item.get("created_at")),
            reverse=True,
        )

    def list_valid_attempts(self, *required_fields: str) -> list[dict[str, Any]]:
        attempts = self.list_attempts()
        if not required_fields:
            return attempts
        return [
            attempt for attempt in attempts
            if _attempt_has_required_fields(attempt, *required_fields)
        ]

    def list_attempts_for_user(self, user_id: int) -> list[dict[str, Any]]:
        attempts = self._find_many("attempts", user_id=user_id)
        return sorted(
            attempts,
            key=lambda item: _sortable_datetime(item.get("created_at")),
            reverse=True,
        )

    def get_attempt(self, attempt_id: int) -> dict[str, Any] | None:
        return self._get("attempts", attempt_id)

    def find_attempt_by_user_quiz(self, user_id: int, quiz_id: int) -> dict[str, Any] | None:
        attempts = self._find_many("attempts", user_id=user_id, quiz_id=quiz_id)
        attempts.sort(key=lambda item: _sortable_datetime(item.get("created_at")))
        return attempts[0] if attempts else None

    def create_attempt(
        self,
        *,
        payload: dict[str, Any],
        profile_updates: dict[str, Any] | None,
        db: Session,
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        payload = dict(payload)
        payload["id"] = self._next_id("attempts")
        writes: list[tuple[str, dict[str, Any]]] = [("attempts", payload)]
        updated_profile = None
        if profile_updates:
            profile = self.get_profile_by_user_id(payload["user_id"])
            if not profile:
                raise PrimaryStoreError("Gamification profile not found for attempt write")
            updated_profile = {**profile, **profile_updates, "id": profile["id"]}
            writes.append(("gamification_profiles", updated_profile))
        self._write_with_backup(operation="create_attempt", writes=writes, db=db)
        return payload, updated_profile

    def list_assignments(self) -> list[dict[str, Any]]:
        return sorted(
            self._all("assignments"),
            key=lambda item: _sortable_datetime(item.get("created_at")),
            reverse=True,
        )

    def get_assignment(self, assignment_id: int) -> dict[str, Any] | None:
        return self._get("assignments", assignment_id)

    def create_assignment(self, payload: dict[str, Any], db: Session) -> dict[str, Any]:
        merged = dict(payload)
        merged.setdefault("created_at", datetime.utcnow())
        merged.setdefault("is_published", False)
        return self._create("assignments", merged, db=db, operation="create_assignment")

    def update_assignment(self, assignment_id: int, payload: dict[str, Any], db: Session) -> dict[str, Any]:
        return self._update(
            "assignments",
            assignment_id,
            payload,
            db=db,
            operation="update_assignment",
        )

    def create_ai_log(self, payload: dict[str, Any], db: Session) -> dict[str, Any]:
        merged = dict(payload)
        merged.setdefault("timestamp", datetime.utcnow())
        return self._create("ai_logs", merged, db=db, operation="create_ai_log")

    def list_ai_logs(self) -> list[dict[str, Any]]:
        return sorted(
            self._all("ai_logs"),
            key=lambda item: _sortable_datetime(item.get("timestamp")),
            reverse=True,
        )

    def create_student_ai_session(self, payload: dict[str, Any], db: Session) -> dict[str, Any]:
        merged = dict(payload)
        now = datetime.utcnow()
        merged.setdefault("created_at", now)
        merged.setdefault("updated_at", now)
        return self._create(
            "student_ai_sessions",
            merged,
            db=db,
            operation="create_student_ai_session",
        )

    def get_student_ai_session(self, session_id: int) -> dict[str, Any] | None:
        return self._get("student_ai_sessions", session_id)

    def update_student_ai_session(self, session_id: int, fields: dict[str, Any], db: Session) -> dict[str, Any]:
        merged = dict(fields)
        merged["updated_at"] = datetime.utcnow()
        return self._update(
            "student_ai_sessions",
            session_id,
            merged,
            db=db,
            operation="update_student_ai_session",
        )

    def list_student_ai_messages(self, session_id: int) -> list[dict[str, Any]]:
        messages = self._find_many("student_ai_messages", session_id=session_id)
        return sorted(messages, key=lambda item: _sortable_datetime(item.get("created_at")))

    def add_student_ai_message(self, payload: dict[str, Any], db: Session) -> dict[str, Any]:
        merged = dict(payload)
        merged.setdefault("created_at", datetime.utcnow())
        message = self._create(
            "student_ai_messages",
            merged,
            db=db,
            operation="create_student_ai_message",
        )
        self.update_student_ai_session(
            payload["session_id"],
            {},
            db=db,
        )
        return message

    def create_e_mode_session(self, payload: dict[str, Any], db: Session) -> dict[str, Any]:
        merged = dict(payload)
        now = datetime.utcnow()
        merged.setdefault("created_at", now)
        merged.setdefault("updated_at", now)
        return self._create(
            "e_mode_sessions",
            merged,
            db=db,
            operation="create_e_mode_session",
        )

    def get_e_mode_session(self, session_id: int) -> dict[str, Any] | None:
        return self._get("e_mode_sessions", session_id)

    def update_e_mode_session(self, session_id: int, fields: dict[str, Any], db: Session) -> dict[str, Any]:
        merged = dict(fields)
        merged["updated_at"] = datetime.utcnow()
        return self._update(
            "e_mode_sessions",
            session_id,
            merged,
            db=db,
            operation="update_e_mode_session",
        )

    def list_e_mode_messages(self, session_id: int) -> list[dict[str, Any]]:
        messages = self._find_many("e_mode_messages", session_id=session_id)
        return sorted(messages, key=lambda item: _sortable_datetime(item.get("created_at")))

    def add_e_mode_message(self, payload: dict[str, Any], db: Session) -> dict[str, Any]:
        merged = dict(payload)
        merged.setdefault("created_at", datetime.utcnow())
        message = self._create(
            "e_mode_messages",
            merged,
            db=db,
            operation="create_e_mode_message",
        )
        self.update_e_mode_session(payload["session_id"], {}, db=db)
        return message

    def list_by_role(self, role: str) -> list[dict[str, Any]]:
        return [user for user in self.list_users() if user.get("role") == role]

    def consistency_report(self, db: Session) -> dict[str, Any]:
        self.ensure_bootstrapped(db)
        report: dict[str, Any] = {"collections": {}}
        mismatches = []
        for collection in ENTITY_COUNTS:
            firestore_count = len(self._all(collection))
            sqlite_count = self.mirror.count_rows(collection, db)
            match = firestore_count == sqlite_count
            report["collections"][collection] = {
                "firestore_count": firestore_count,
                "sqlite_count": sqlite_count,
                "match": match,
            }
            if not match:
                mismatches.append(collection)
        report["healthy"] = not mismatches
        report["mismatches"] = mismatches
        return report


_STORE: EduQuestPrimaryStore | None = None


def get_store() -> EduQuestPrimaryStore:
    global _STORE
    if _STORE is None:
        _STORE = EduQuestPrimaryStore()
    return _STORE


def reset_store_for_tests() -> None:
    global _STORE
    _STORE = None


def ensure_firestore_bootstrap(session_factory: sessionmaker) -> None:
    db = session_factory()
    try:
        get_store().ensure_bootstrapped(db)
    finally:
        db.close()


def as_record(data: dict[str, Any] | None) -> SimpleNamespace | None:
    return _doc_to_record(data)
