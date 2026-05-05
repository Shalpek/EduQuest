def test_teacher_content_validation_and_assignment_flow(client, auth_headers):
    invalid_lesson = client.post(
        "/api/teacher/lessons",
        headers=auth_headers("teacher@eduquest.com"),
        json={
            "course_id": 999,
            "title": "Invalid lesson",
            "content": "Should fail",
            "order": 1,
        },
    )
    assert invalid_lesson.status_code == 404

    invalid_quiz = client.post(
        "/api/teacher/quizzes",
        headers=auth_headers("teacher@eduquest.com"),
        json={
            "lesson_id": 999,
            "title": "Invalid quiz",
            "questions": [],
        },
    )
    assert invalid_quiz.status_code == 404

    created_course = client.post(
        "/api/teacher/courses",
        headers=auth_headers("teacher@eduquest.com"),
        json={"title": "Backend Systems", "description": "New course"},
    )
    assert created_course.status_code == 200
    course_id = created_course.json()["id"]

    created_lesson = client.post(
        "/api/teacher/lessons",
        headers=auth_headers("teacher@eduquest.com"),
        json={
            "course_id": course_id,
            "title": "API Contracts",
            "content": "Contracts and validation",
            "order": 1,
        },
    )
    assert created_lesson.status_code == 200
    lesson_id = created_lesson.json()["id"]

    created_quiz = client.post(
        "/api/teacher/quizzes",
        headers=auth_headers("teacher@eduquest.com"),
        json={
            "lesson_id": lesson_id,
            "title": "API Quiz",
            "questions": [
                {"q": "What is an API?", "options": ["Contract", "Loop"], "answer": 0},
            ],
        },
    )
    assert created_quiz.status_code == 200
    quiz_body = created_quiz.json()
    assert quiz_body["lesson_id"] == lesson_id
    assert quiz_body["question_count"] == 1

    created_assignment = client.post(
        "/api/teacher/assignments",
        headers=auth_headers("teacher@eduquest.com"),
        json={
            "quiz_id": quiz_body["id"],
            "course_id": course_id,
            "title": "Assignment 1",
            "instructions": "Complete after the lesson",
            "due_at": None,
        },
    )
    assert created_assignment.status_code == 200
    assignment_id = created_assignment.json()["id"]

    listed_assignments = client.get(
        "/api/teacher/assignments",
        headers=auth_headers("teacher@eduquest.com"),
    )
    assert listed_assignments.status_code == 200
    assert any(item["id"] == assignment_id for item in listed_assignments.json())

    updated_assignment = client.put(
        f"/api/teacher/assignments/{assignment_id}",
        headers=auth_headers("teacher@eduquest.com"),
        json={
            "quiz_id": quiz_body["id"],
            "course_id": course_id,
            "title": "Assignment 1 updated",
            "instructions": "Review the lesson and submit",
            "due_at": None,
        },
    )
    assert updated_assignment.status_code == 200
    assert updated_assignment.json()["title"] == "Assignment 1 updated"

    published_assignment = client.put(
        f"/api/teacher/assignments/{assignment_id}/publish",
        headers=auth_headers("teacher@eduquest.com"),
    )
    assert published_assignment.status_code == 200
    assert published_assignment.json()["is_published"] is True

    analytics_summary = client.get(
        "/api/teacher/analytics-summary",
        headers=auth_headers("teacher@eduquest.com"),
    )
    assert analytics_summary.status_code == 200
    assert set(analytics_summary.json().keys()) == {
        "weak_topics",
        "recent_completion_rate",
        "average_score",
        "students_needing_attention",
    }


def test_course_content_map_returns_teacher_friendly_lesson_and_quiz_data(client):
    courses = client.get("/api/courses/")
    assert courses.status_code == 200
    course = courses.json()[0]

    content_map = client.get(f"/api/courses/{course['id']}/content-map")
    assert content_map.status_code == 200

    body = content_map.json()
    assert body["course"]["id"] == course["id"]
    assert {"lesson_count", "quiz_count", "difficulty", "estimated_effort"}.issubset(
        body["course"].keys()
    )
    assert len(body["lessons"]) >= 1

    first_lesson = body["lessons"][0]
    assert {
        "id",
        "title",
        "content",
        "order",
        "quiz_count",
        "has_quiz",
        "estimated_minutes",
        "summary",
        "quizzes",
    }.issubset(first_lesson.keys())
    if first_lesson["quizzes"]:
        assert {"id", "title", "question_count"}.issubset(first_lesson["quizzes"][0].keys())

    missing_course = client.get("/api/courses/999/content-map")
    assert missing_course.status_code == 404


def test_admin_governance_depth(client, auth_headers):
    users = client.get("/api/admin/users", headers=auth_headers("admin@eduquest.com"))
    assert users.status_code == 200
    first_user = users.json()[0]
    assert {"xp", "level", "streak"}.issubset(first_user.keys())

    target_user_id = first_user["id"]
    status_update = client.put(
        f"/api/admin/users/{target_user_id}/status?active=false",
        headers=auth_headers("admin@eduquest.com"),
    )
    assert status_update.status_code == 200
    assert "user" in status_update.json()

    role_update = client.put(
        f"/api/admin/users/{target_user_id}/role?role=teacher",
        headers=auth_headers("admin@eduquest.com"),
    )
    assert role_update.status_code == 200
    assert role_update.json()["user"]["role"] == "teacher"

    config = client.get("/api/admin/config", headers=auth_headers("admin@eduquest.com"))
    assert config.status_code == 200
    assert {"ai_safety", "retries_enabled", "xp_per_quiz"}.issubset(config.json().keys())

    platform_status = client.get(
        "/api/admin/platform-status",
        headers=auth_headers("admin@eduquest.com"),
    )
    assert platform_status.status_code == 200
    assert {
        "services",
        "metrics",
        "role_distribution",
        "active_vs_inactive_users",
        "config_snapshot",
        "recent_ai_activity_count",
    }.issubset(platform_status.json().keys())
