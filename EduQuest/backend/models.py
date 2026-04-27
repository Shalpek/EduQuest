from sqlalchemy import Boolean, Column, Integer, String, ForeignKey, Float, DateTime
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
    full_name = Column(String)
    hashed_password = Column(String)
    role = Column(String, default="student") # student, teacher, admin
    is_active = Column(Boolean, default=True)

    profile = relationship("GamificationProfile", back_populates="user", uselist=False)

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
    questions = Column(String) # Stored as JSON string for simplicity in MVP
    assignments = relationship("Assignment", back_populates="quiz")
    
class Attempt(Base):
    __tablename__ = "attempts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    quiz_id = Column(Integer, ForeignKey("quizzes.id"))
    score = Column(Float)
    earned_xp = Column(Integer)
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

