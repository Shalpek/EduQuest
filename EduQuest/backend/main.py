from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
import models
from database import engine, SessionLocal
from firestore_primary_store import ensure_firestore_bootstrap


def _ensure_runtime_schema() -> None:
    models.Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)

    if "users" in inspector.get_table_names():
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        with engine.begin() as connection:
            if "firebase_uid" not in user_columns:
                connection.execute(
                    text("ALTER TABLE users ADD COLUMN firebase_uid VARCHAR")
                )

    if "attempts" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("attempts")}
    required_columns = {
        "student_answers_json": "TEXT DEFAULT '[]'",
        "quiz_questions_snapshot_json": "TEXT DEFAULT '[]'",
        "wrong_answer_indexes_json": "TEXT DEFAULT '[]'",
    }

    with engine.begin() as connection:
        for column_name, column_definition in required_columns.items():
            if column_name not in existing_columns:
                connection.execute(
                    text(
                        f"ALTER TABLE attempts ADD COLUMN {column_name} {column_definition}"
                    )
                )


_ensure_runtime_schema()
ensure_firestore_bootstrap(SessionLocal)

app = FastAPI(title="EduQuest API", description="AI-enhanced learning app backend for bachelor thesis MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from routers import auth, courses, ai_tutor, gamification, quizzes, analytics, teacher, admin, app_config, e_mode

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(app_config.router, prefix="/api/app", tags=["App Config"])
app.include_router(courses.router, prefix="/api/courses", tags=["Courses"])
app.include_router(quizzes.router, prefix="/api/quizzes", tags=["Quizzes"])
app.include_router(gamification.router, prefix="/api/gamification", tags=["Gamification"])
app.include_router(ai_tutor.router, prefix="/api/ai-tutor", tags=["AI Tutor"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(teacher.router, prefix="/api/teacher", tags=["Teacher"])
app.include_router(e_mode.router, prefix="/api/teacher/e-mode", tags=["Teacher E-Mode"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])

@app.get("/")
def root():
    return {"message": "Welcome to EduQuest API"}
