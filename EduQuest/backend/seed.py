from database import SessionLocal, engine
import models
import json
from datetime import datetime, timedelta

def seed_db():
    print("Dropping all tables to reset state...")
    models.Base.metadata.drop_all(bind=engine)
    print("Recreating tables...")
    models.Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    
    print("Seeding system config...")
    sys_config = models.SystemConfig()
    db.add(sys_config)
    db.commit()

    print("Seeding users...")
    users_data = [
        {"email": "student@eduquest.com", "full_name": "Demo Student", "role": "student"},
        {"email": "alice@eduquest.com", "full_name": "Alice Smith", "role": "student"},
        {"email": "bob@eduquest.com", "full_name": "Bob Jones", "role": "student"},
        {"email": "teacher@eduquest.com", "full_name": "Demo Teacher", "role": "teacher"},
        {"email": "admin@eduquest.com", "full_name": "Demo Admin", "role": "admin"}
    ]
    
    users = []
    for ud in users_data:
        user = models.User(
            email=ud["email"],
            full_name=ud["full_name"],
            hashed_password="mock_hash_password123",
            role=ud["role"]
        )
        db.add(user)
        users.append(user)
        
    db.commit()
    for user in users:
        db.refresh(user)
        profile = models.GamificationProfile(user_id=user.id)
        if user.role == "student":
            if user.email == "student@eduquest.com":
                profile.xp = 1250
                profile.level = 3
                profile.streak = 5
            elif user.email == "alice@eduquest.com":
                profile.xp = 800
                profile.level = 2
                profile.streak = 2
            else:
                profile.xp = 350
                profile.level = 1
                profile.streak = 1
        db.add(profile)
        
    db.commit()

    print("Seeding courses...")
    course1 = models.Course(
        title="Introduction to Computer Science",
        description="Learn the basics of programming and computer systems."
    )
    course2 = models.Course(
        title="AI and Machine Learning 101",
        description="A foundational course on how AI learns and makes decisions."
    )
    db.add(course1)
    db.add(course2)
    db.commit()
    db.refresh(course1)
    db.refresh(course2)
    
    print("Seeding lessons and quizzes...")
    
    # Course 1 Lessons
    c1_lesson1 = models.Lesson(
        course_id=course1.id,
        title="Variables and Data Types",
        content="Variables are containers for storing data values. In programming, data types specify what kind of data can be stored and manipulated within a program.",
        order=1
    )
    c1_lesson2 = models.Lesson(
        course_id=course1.id,
        title="Control Structures (Loops)",
        content="Control structures determine the flow of execution in a program. Loops (like 'for' and 'while') allow you to repeat a block of code.",
        order=2
    )
    c1_lesson3 = models.Lesson(
        course_id=course1.id,
        title="Functions and Methods",
        content="A function is a block of code which only runs when it is called. You can pass data, known as parameters, into a function.",
        order=3
    )

    # Course 2 Lessons
    c2_lesson1 = models.Lesson(
        course_id=course2.id,
        title="What is Artificial Intelligence?",
        content="AI is intelligence demonstrated by machines, as opposed to natural intelligence displayed by animals including humans.",
        order=1
    )
    c2_lesson2 = models.Lesson(
        course_id=course2.id,
        title="Neural Networks",
        content="Neural networks are a set of algorithms, modeled loosely after the human brain, that are designed to recognize patterns.",
        order=2
    )
    
    db.add_all([c1_lesson1, c1_lesson2, c1_lesson3, c2_lesson1, c2_lesson2])
    db.commit()
    
    db.refresh(c1_lesson1)
    db.refresh(c1_lesson2)
    db.refresh(c1_lesson3)
    db.refresh(c2_lesson1)
    db.refresh(c2_lesson2)

    # Quizzes for Course 1
    quiz1 = models.Quiz(
        lesson_id=c1_lesson1.id,
        title="Variables Quiz",
        questions=json.dumps([
            {"q": "What is a variable?", "options": ["A data container", "A loop", "A function", "An error"], "answer": 0},
            {"q": "Which is NOT a standard data type?", "options": ["Integer", "String", "Elephant", "Boolean"], "answer": 2}
        ])
    )
    quiz2 = models.Quiz(
        lesson_id=c1_lesson2.id,
        title="Loops Quiz",
        questions=json.dumps([
            {"q": "Which loop is best when you know the number of iterations?", "options": ["while loop", "do-while loop", "for loop", "infinite loop"], "answer": 2}
        ])
    )
    quiz3 = models.Quiz(
        lesson_id=c1_lesson3.id,
        title="Functions Quiz",
        questions=json.dumps([
            {"q": "What do you pass to a function?", "options": ["Methods", "Parameters", "Classes", "Loops"], "answer": 1}
        ])
    )
    
    # Quizzes for Course 2
    quiz4 = models.Quiz(
        lesson_id=c2_lesson1.id,
        title="Intro to AI Quiz",
        questions=json.dumps([
            {"q": "What does AI stand for?", "options": ["Artificial Intelligence", "Automated Information", "Applied Imagination", "Artificial Intuition"], "answer": 0}
        ])
    )
    
    db.add_all([quiz1, quiz2, quiz3, quiz4])
    db.commit()
    db.refresh(quiz1)
    db.refresh(quiz2)
    db.refresh(quiz3)
    db.refresh(quiz4)

    print("Seeding progress (completed lessons and attempts)...")
    student = next(u for u in users if u.email == "student@eduquest.com")
    alice = next(u for u in users if u.email == "alice@eduquest.com")
    
    now = datetime.utcnow()

    print("Seeding assignments...")
    assignment1 = models.Assignment(
        quiz_id=quiz2.id,
        course_id=course1.id,
        title="Loop mastery check",
        instructions="Complete the quiz after revising for-loops and while-loops.",
        due_at=now + timedelta(days=3),
        is_published=True,
    )
    db.add(assignment1)
    db.commit()

    # Student completed lessons
    db.add(models.CompletedLesson(user_id=student.id, lesson_id=c1_lesson1.id, completed_at=now - timedelta(days=5)))
    db.add(models.CompletedLesson(user_id=student.id, lesson_id=c1_lesson2.id, completed_at=now - timedelta(days=2)))
    db.add(models.CompletedLesson(user_id=student.id, lesson_id=c2_lesson1.id, completed_at=now - timedelta(days=1)))
    
    # Alice completed lessons
    db.add(models.CompletedLesson(user_id=alice.id, lesson_id=c1_lesson1.id, completed_at=now - timedelta(days=3)))

    # Attempts
    db.add(models.Attempt(user_id=student.id, quiz_id=quiz1.id, score=1.0, earned_xp=100, created_at=now - timedelta(days=5)))
    db.add(models.Attempt(user_id=student.id, quiz_id=quiz2.id, score=0.0, earned_xp=10, created_at=now - timedelta(days=3))) # Failed once
    db.add(models.Attempt(user_id=student.id, quiz_id=quiz2.id, score=1.0, earned_xp=100, created_at=now - timedelta(days=2)))
    db.add(models.Attempt(user_id=student.id, quiz_id=quiz4.id, score=1.0, earned_xp=100, created_at=now - timedelta(days=1)))
    
    db.add(models.Attempt(user_id=alice.id, quiz_id=quiz1.id, score=1.0, earned_xp=100, created_at=now - timedelta(days=3)))

    db.commit()

    print("Seeding AI Logs...")
    db.add(models.AILog(
        user_id=student.id,
        context="What is Artificial Intelligence?",
        question="Can you give me a simple example of AI?",
        hint="Sure! A great example is the recommendation system on YouTube.",
        timestamp=now - timedelta(hours=2)
    ))
    db.commit()

    print("Database seeded successfully with demo content!")

if __name__ == "__main__":
    seed_db()
