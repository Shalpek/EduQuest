from sqlalchemy import Boolean, Column, Integer, String, ForeignKey, Float, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class SystemConfig(Base):
    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True, index=True)
    ai_safety = Column(Boolean, default=True)
    retries_enabled = Column(Boolean, default=True)
    xp_per_quiz = Column(Integer, default=100)
    updated_at = Column(DateTime, default=datetime.utcnow)

class AILog(Base):
    __tablename__ = "ai_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    context = Column(String)
    question = Column(String)
    hint = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    firebase_uid = Column(String, nullable=True, index=True)
    full_name = Column(String)
    hashed_password = Column(String)
    role = Column(String, default="student") # student, teacher, admin
    is_active = Column(Boolean, default=True)

    profile = relationship("GamificationProfile", back_populates="user", uselist=False)
    e_mode_sessions = relationship("EModeSession", back_populates="teacher")

class GamificationProfile(Base):
    __tablename__ = "gamification_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    xp = Column(Integer, default=0)
    level = Column(Integer, default=1)
    streak = Column(Integer, default=0)
    
    user = relationship("User", back_populates="profile")

class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(String)
    
    lessons = relationship("Lesson", back_populates="course")
    assignments = relationship("Assignment", back_populates="course")

class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"))
    title = Column(String, index=True)
    content = Column(String) 
    order = Column(Integer)
    
    course = relationship("Course", back_populates="lessons")

class CompletedLesson(Base):
    __tablename__ = "completed_lessons"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    lesson_id = Column(Integer, ForeignKey("lessons.id"))
    completed_at = Column(DateTime, default=datetime.utcnow)

class Quiz(Base):
    __tablename__ = "quizzes"

    id = Column(Integer, primary_key=True, index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"))
    title = Column(String)
    xp_reward = Column(Integer, default=100)
    questions = Column(String) # Stored as JSON string for simplicity in MVP
    assignments = relationship("Assignment", back_populates="quiz")
    
class Attempt(Base):
    __tablename__ = "attempts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    quiz_id = Column(Integer, ForeignKey("quizzes.id"))
    score = Column(Float)
    earned_xp = Column(Integer)
    student_answers_json = Column(Text, default="[]")
    quiz_questions_snapshot_json = Column(Text, default="[]")
    wrong_answer_indexes_json = Column(Text, default="[]")
    created_at = Column(DateTime, default=datetime.utcnow)


class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"))
    course_id = Column(Integer, ForeignKey("courses.id"))
    title = Column(String, index=True)
    instructions = Column(String, default="")
    due_at = Column(DateTime, nullable=True)
    is_published = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    quiz = relationship("Quiz", back_populates="assignments")
    course = relationship("Course", back_populates="assignments")


class EModeSession(Base):
    __tablename__ = "e_mode_sessions"

    id = Column(Integer, primary_key=True, index=True)
    teacher_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=False, index=True)
    topic = Column(String, nullable=False)
    instructions = Column(Text, default="")
    student_level = Column(String, nullable=True)
    difficulty = Column(String, nullable=True)
    language = Column(String, nullable=True)
    task_count = Column(Integer, nullable=True)
    preferred_types = Column(Text, default="[]")
    quiz_title = Column(String, nullable=True)
    uploaded_file_name = Column(String, nullable=True)
    uploaded_file_type = Column(String, nullable=True)
    extracted_material_text = Column(Text, nullable=True)
    current_draft = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    teacher = relationship("User", back_populates="e_mode_sessions")
    messages = relationship(
        "EModeMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="EModeMessage.created_at",
    )


class EModeMessage(Base):
    __tablename__ = "e_mode_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("e_mode_sessions.id"), nullable=False, index=True)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("EModeSession", back_populates="messages")


class StudentAISession(Base):
    __tablename__ = "student_ai_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    mode = Column(String, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=True)
    attempt_id = Column(Integer, ForeignKey("attempts.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    messages = relationship(
        "StudentAIMessage",
        back_populates="session",
        cascade="all, delete-orphan",
    )


class StudentAIMessage(Base):
    __tablename__ = "student_ai_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("student_ai_sessions.id"))
    role = Column(String)
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("StudentAISession", back_populates="messages")

