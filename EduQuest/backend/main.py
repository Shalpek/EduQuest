from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import models
from database import engine

# Create the database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="EduQuest API", description="AI-enhanced learning app backend for bachelor thesis MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from routers import auth, courses, ai_tutor, gamification, quizzes, analytics, teacher, admin, app_config

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(app_config.router, prefix="/api/app", tags=["App Config"])
app.include_router(courses.router, prefix="/api/courses", tags=["Courses"])
app.include_router(quizzes.router, prefix="/api/quizzes", tags=["Quizzes"])
app.include_router(gamification.router, prefix="/api/gamification", tags=["Gamification"])
app.include_router(ai_tutor.router, prefix="/api/ai-tutor", tags=["AI Tutor"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(teacher.router, prefix="/api/teacher", tags=["Teacher"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])

@app.get("/")
def root():
    return {"message": "Welcome to EduQuest API"}
