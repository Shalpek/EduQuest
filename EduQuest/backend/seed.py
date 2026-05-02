from datetime import datetime, timedelta
import json

from database import SessionLocal, engine
import models


COURSE_BLUEPRINTS = [
    {
        "title": "Introduction to Computer Science",
        "description": "Core computer science ideas for new learners, from data representation to algorithmic thinking.",
        "lessons": [
            (
                "Variables and Data Types",
                "Learn how variables hold data, why types matter, and how numbers, strings, and booleans behave in real programs.",
            ),
            (
                "Control Flow and Decisions",
                "Use conditionals and loops to control program behavior, repeat logic, and respond to changing input.",
            ),
            (
                "Functions and Problem Decomposition",
                "Break a larger problem into smaller reusable functions with clear responsibilities and inputs.",
            ),
        ],
    },
    {
        "title": "Programming Fundamentals with Python",
        "description": "A practical Python track focused on syntax, debugging habits, and writing small but complete programs.",
        "lessons": [
            (
                "Reading and Writing Python Statements",
                "Understand indentation, expressions, assignment, and the mental model behind Python's readable syntax.",
            ),
            (
                "Lists, Dictionaries, and Iteration",
                "Work with the most common collection types while practicing loops and simple data transformations.",
            ),
            (
                "Debugging and Basic Testing",
                "Trace runtime issues, inspect outputs, and use small tests to confirm a function behaves correctly.",
            ),
        ],
    },
    {
        "title": "Data Structures and Algorithms Basics",
        "description": "A lightweight introduction to common structures, complexity, and choosing the right approach for a task.",
        "lessons": [
            (
                "Arrays, Lists, and Stacks",
                "Compare linear data structures and understand when ordering, indexing, or push-pop workflows matter most.",
            ),
            (
                "Searching and Sorting",
                "Build intuition for linear search, binary search, and common sorting ideas used in beginner-friendly systems.",
            ),
            (
                "Big-O Thinking",
                "Use time and space complexity as a practical decision tool rather than a purely theoretical label.",
            ),
        ],
    },
    {
        "title": "Web and API Development Basics",
        "description": "Build a product mindset around HTTP, client-server contracts, and the shape of a modern web application.",
        "lessons": [
            (
                "How the Web Request Cycle Works",
                "Follow the path from browser request to backend response and back to the user interface.",
            ),
            (
                "REST APIs and JSON Contracts",
                "Understand routes, payloads, response shapes, and why predictable contracts matter to frontend integration.",
            ),
            (
                "Validation and Error Handling",
                "Design input checks, status codes, and human-readable feedback that keep product flows stable.",
            ),
        ],
    },
    {
        "title": "AI and Machine Learning Foundations",
        "description": "A grounded overview of how machine learning systems learn patterns, where they fail, and how humans guide them.",
        "lessons": [
            (
                "What Artificial Intelligence Really Means",
                "Separate hype from practical concepts by looking at prediction, automation, and pattern recognition.",
            ),
            (
                "Neural Networks and Training Data",
                "See how models learn from examples, why data quality matters, and what overfitting looks like.",
            ),
            (
                "Ethics, Safety, and Responsible Use",
                "Connect AI features to product policy decisions such as safety filters, human review, and auditability.",
            ),
        ],
    },
]


def _quiz_payload(lesson_title: str, title: str) -> list[dict]:
    if "Variables" in lesson_title:
        return [
            {
                "q": "Which option describes a variable best?",
                "options": [
                    "A named container for data",
                    "A repeated loop block",
                    "A syntax error",
                    "A network request",
                ],
                "answer": 0,
            },
            {
                "q": "Which value is a boolean?",
                "options": ["42", "\"hello\"", "true", "3.14"],
                "answer": 2,
            },
        ]
    if "Control" in lesson_title:
        return [
            {
                "q": "Which statement helps a program choose between paths?",
                "options": ["if", "list", "import", "return type"],
                "answer": 0,
            },
            {
                "q": "Which construct repeats code while a condition stays true?",
                "options": ["loop", "while", "variable", "class"],
                "answer": 1,
            },
        ]
    if "Functions" in lesson_title:
        return [
            {
                "q": "Why use functions?",
                "options": [
                    "To reuse logic",
                    "To rename every variable",
                    "To avoid inputs",
                    "To remove all bugs",
                ],
                "answer": 0,
            },
        ]
    if "Python" in title or "Statements" in lesson_title:
        return [
            {
                "q": "What does indentation communicate in Python?",
                "options": [
                    "Program structure",
                    "Network latency",
                    "Database size",
                    "Compiler version",
                ],
                "answer": 0,
            },
        ]
    if "Lists" in lesson_title:
        return [
            {
                "q": "Which structure stores key-value pairs?",
                "options": ["list", "dictionary", "tuple", "string"],
                "answer": 1,
            },
        ]
    if "Debugging" in lesson_title:
        return [
            {
                "q": "What is the main purpose of a basic automated test?",
                "options": [
                    "Confirm expected behavior",
                    "Replace all documentation",
                    "Hide runtime errors",
                    "Optimize every query",
                ],
                "answer": 0,
            },
        ]
    if "Arrays" in lesson_title:
        return [
            {
                "q": "Which structure naturally supports last-in, first-out behavior?",
                "options": ["Queue", "Stack", "Tree", "Graph"],
                "answer": 1,
            },
        ]
    if "Searching" in lesson_title:
        return [
            {
                "q": "When is binary search appropriate?",
                "options": [
                    "Any unsorted data",
                    "Sorted data",
                    "Only images",
                    "Only recursive code",
                ],
                "answer": 1,
            },
        ]
    if "Big-O" in lesson_title:
        return [
            {
                "q": "What does Big-O help estimate?",
                "options": [
                    "Algorithm growth",
                    "Color palette size",
                    "User interface spacing",
                    "SQL table names",
                ],
                "answer": 0,
            },
        ]
    if "Request Cycle" in lesson_title:
        return [
            {
                "q": "What usually triggers a backend response?",
                "options": [
                    "A client request",
                    "A local font",
                    "A CSS variable",
                    "A screenshot",
                ],
                "answer": 0,
            },
        ]
    if "REST APIs" in lesson_title:
        return [
            {
                "q": "Why are stable JSON contracts important?",
                "options": [
                    "So the frontend can parse responses predictably",
                    "So keyboards open faster",
                    "So icons become larger",
                    "So databases stop existing",
                ],
                "answer": 0,
            },
        ]
    if "Validation" in lesson_title:
        return [
            {
                "q": "What should validation primarily protect?",
                "options": [
                    "Input quality and flow safety",
                    "Only dark mode colors",
                    "Random number generation",
                    "Lesson titles from being short",
                ],
                "answer": 0,
            },
        ]
    if "Artificial Intelligence" in lesson_title:
        return [
            {
                "q": "What does AI most often do in product software?",
                "options": [
                    "Recognize patterns or generate outputs",
                    "Replace electricity",
                    "Disable all user input",
                    "Remove data structures",
                ],
                "answer": 0,
            },
        ]
    if "Neural Networks" in lesson_title:
        return [
            {
                "q": "Why does training data quality matter?",
                "options": [
                    "It shapes what the model learns",
                    "It changes screen brightness",
                    "It removes authentication",
                    "It disables retries",
                ],
                "answer": 0,
            },
        ]
    return [
        {
            "q": "Why are AI safety controls useful?",
            "options": [
                "They reduce harmful or off-topic responses",
                "They guarantee perfect model accuracy",
                "They replace all teachers",
                "They remove the need for analytics",
            ],
            "answer": 0,
        },
    ]


def seed_db():
    print("Dropping all tables to reset state...")
    models.Base.metadata.drop_all(bind=engine)
    print("Recreating tables...")
    models.Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    now = datetime.utcnow()

    print("Seeding system config...")
    sys_config = models.SystemConfig(ai_safety=True, retries_enabled=True, xp_per_quiz=100)
    db.add(sys_config)
    db.commit()

    print("Seeding users...")
    users_data = [
        {"email": "student@eduquest.com", "full_name": "Demo Student", "role": "student"},
        {"email": "alice@eduquest.com", "full_name": "Alice Smith", "role": "student"},
        {"email": "bob@eduquest.com", "full_name": "Bob Jones", "role": "student"},
        {"email": "teacher@eduquest.com", "full_name": "Demo Teacher", "role": "teacher"},
        {"email": "admin@eduquest.com", "full_name": "Demo Admin", "role": "admin"},
    ]

    users = {}
    for user_data in users_data:
        user = models.User(
            email=user_data["email"],
            full_name=user_data["full_name"],
            hashed_password="mock_hash_password123",
            role=user_data["role"],
        )
        db.add(user)
        db.flush()
        profile = models.GamificationProfile(user_id=user.id)
        if user.role == "student":
            if user.email == "student@eduquest.com":
                profile.xp = 1450
                profile.level = 4
                profile.streak = 6
            elif user.email == "alice@eduquest.com":
                profile.xp = 980
                profile.level = 3
                profile.streak = 3
            else:
                profile.xp = 620
                profile.level = 2
                profile.streak = 2
        db.add(profile)
        users[user.email] = user
    db.commit()

    print("Seeding courses, lessons, and quizzes...")
    quizzes_by_lesson = {}
    quizzes_by_title = {}
    courses_by_title = {}

    for course_index, course_blueprint in enumerate(COURSE_BLUEPRINTS, start=1):
        course = models.Course(
            title=course_blueprint["title"],
            description=course_blueprint["description"],
        )
        db.add(course)
        db.flush()
        courses_by_title[course.title] = course

        for lesson_index, (lesson_title, lesson_content) in enumerate(
            course_blueprint["lessons"],
            start=1,
        ):
            lesson = models.Lesson(
                course_id=course.id,
                title=lesson_title,
                content=lesson_content,
                order=lesson_index,
            )
            db.add(lesson)
            db.flush()

            quiz = models.Quiz(
                lesson_id=lesson.id,
                title=f"{lesson_title} Quiz",
                questions=json.dumps(_quiz_payload(lesson_title, course.title)),
            )
            db.add(quiz)
            db.flush()
            quizzes_by_lesson[lesson.id] = quiz
            quizzes_by_title[quiz.title] = quiz

    db.commit()

    print("Seeding assignments...")
    assignments = [
        models.Assignment(
            quiz_id=quizzes_by_title["Control Flow and Decisions Quiz"].id,
            course_id=courses_by_title["Introduction to Computer Science"].id,
            title="Control flow mastery check",
            instructions="Complete this quiz after revising loops and branching examples.",
            due_at=now + timedelta(days=3),
            is_published=True,
        ),
        models.Assignment(
            quiz_id=quizzes_by_title["REST APIs and JSON Contracts Quiz"].id,
            course_id=courses_by_title["Web and API Development Basics"].id,
            title="API contract checkpoint",
            instructions="Review request-response structure and submit before the next teacher walkthrough.",
            due_at=now + timedelta(days=5),
            is_published=True,
        ),
        models.Assignment(
            quiz_id=quizzes_by_title["Ethics, Safety, and Responsible Use Quiz"].id,
            course_id=courses_by_title["AI and Machine Learning Foundations"].id,
            title="AI policy reflection task",
            instructions="Use the quiz and follow-up discussion to reinforce safe AI usage principles.",
            due_at=now + timedelta(days=7),
            is_published=False,
        ),
    ]
    db.add_all(assignments)
    db.commit()

    print("Seeding completed lessons and attempts...")
    student = users["student@eduquest.com"]
    alice = users["alice@eduquest.com"]
    bob = users["bob@eduquest.com"]

    all_lessons = db.query(models.Lesson).order_by(models.Lesson.id).all()
    lesson_lookup = {lesson.title: lesson for lesson in all_lessons}

    completions = [
        (student.id, lesson_lookup["Variables and Data Types"].id, now - timedelta(days=9)),
        (student.id, lesson_lookup["Control Flow and Decisions"].id, now - timedelta(days=7)),
        (student.id, lesson_lookup["Functions and Problem Decomposition"].id, now - timedelta(days=5)),
        (student.id, lesson_lookup["What Artificial Intelligence Really Means"].id, now - timedelta(days=2)),
        (alice.id, lesson_lookup["Variables and Data Types"].id, now - timedelta(days=6)),
        (alice.id, lesson_lookup["Lists, Dictionaries, and Iteration"].id, now - timedelta(days=3)),
        (bob.id, lesson_lookup["How the Web Request Cycle Works"].id, now - timedelta(days=1)),
    ]
    for user_id, lesson_id, completed_at in completions:
        db.add(
            models.CompletedLesson(
                user_id=user_id,
                lesson_id=lesson_id,
                completed_at=completed_at,
            )
        )

    def add_attempt(user_email: str, quiz_title: str, score: float, xp: int, offset_days: int):
        db.add(
            models.Attempt(
                user_id=users[user_email].id,
                quiz_id=quizzes_by_title[quiz_title].id,
                score=score,
                earned_xp=xp,
                created_at=now - timedelta(days=offset_days),
            )
        )

    add_attempt("student@eduquest.com", "Variables and Data Types Quiz", 1.0, 100, 9)
    add_attempt("student@eduquest.com", "Control Flow and Decisions Quiz", 0.5, 40, 7)
    add_attempt("student@eduquest.com", "Control Flow and Decisions Quiz", 0.9, 100, 6)
    add_attempt("student@eduquest.com", "Functions and Problem Decomposition Quiz", 0.8, 95, 5)
    add_attempt("student@eduquest.com", "What Artificial Intelligence Really Means Quiz", 0.7, 85, 2)
    add_attempt("alice@eduquest.com", "Variables and Data Types Quiz", 0.9, 100, 6)
    add_attempt("alice@eduquest.com", "Lists, Dictionaries, and Iteration Quiz", 0.6, 55, 3)
    add_attempt("alice@eduquest.com", "Debugging and Basic Testing Quiz", 0.75, 80, 1)
    add_attempt("bob@eduquest.com", "How the Web Request Cycle Works Quiz", 0.65, 60, 1)
    add_attempt("bob@eduquest.com", "REST APIs and JSON Contracts Quiz", 0.55, 45, 0)
    db.commit()

    print("Seeding AI logs...")
    ai_logs = [
        models.AILog(
            user_id=student.id,
            context="Variables and Data Types",
            question="Why does a boolean only have two values?",
            hint="Because booleans model a true or false condition used in logic and control flow.",
            timestamp=now - timedelta(hours=20),
        ),
        models.AILog(
            user_id=alice.id,
            context="REST APIs and JSON Contracts",
            question="Why do frontend screens break when the API field names change?",
            hint="Because the UI parser expects a stable contract and cannot infer renamed fields reliably.",
            timestamp=now - timedelta(hours=12),
        ),
        models.AILog(
            user_id=bob.id,
            context="Ethics, Safety, and Responsible Use",
            question="What is the role of a safety filter in an AI tutor?",
            hint="It blocks unsafe or off-topic outputs so the learning product stays aligned with policy.",
            timestamp=now - timedelta(hours=4),
        ),
    ]
    db.add_all(ai_logs)
    db.commit()

    print("Database seeded successfully with expanded Software Engineering and AI content!")


if __name__ == "__main__":
    seed_db()
