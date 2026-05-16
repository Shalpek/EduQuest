import pytest
import routers.ai_tutor as ai_tutor_router
import dependencies
from firebase_auth_provider import FirebaseIdentity


def test_legacy_x_user_id_header_is_not_accepted(client):
    response = client.get("/api/auth/me", headers={"X-User-Id": "1"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Bearer token missing"


def test_auth_me_and_profile_update_for_all_roles(client, auth_headers):
    student = client.get("/api/auth/me", headers=auth_headers("student@eduquest.com"))
    teacher = client.get("/api/auth/me", headers=auth_headers("teacher@eduquest.com"))
    admin = client.get("/api/auth/me", headers=auth_headers("admin@eduquest.com"))

    assert student.status_code == 200
    assert teacher.status_code == 200
    assert admin.status_code == 200
    assert student.json()["role"] == "student"
    assert teacher.json()["role"] == "teacher"
    assert admin.json()["role"] == "admin"

    updated = client.put(
        "/api/auth/me",
        headers=auth_headers("teacher@eduquest.com"),
        json={"full_name": "  Teacher Renamed  "},
    )
    assert updated.status_code == 200
    assert updated.json()["full_name"] == "Teacher Renamed"


def test_change_password_validates_current_password(client, auth_headers):
    response = client.put(
        "/api/auth/change-password",
        headers=auth_headers("admin@eduquest.com"),
        json={
            "current_password": "wrong-password",
            "new_password": "new-password-123",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Current password is incorrect"


def test_gamification_profile_access_rules(client, auth_headers, seeded_ids):
    own_profile = client.get(
        f"/api/gamification/profile/{seeded_ids['student@eduquest.com']}",
        headers=auth_headers("student@eduquest.com"),
    )
    assert own_profile.status_code == 200

    forbidden_profile = client.get(
        f"/api/gamification/profile/{seeded_ids['student@eduquest.com']}",
        headers=auth_headers("alice@eduquest.com"),
    )
    assert forbidden_profile.status_code == 403
    assert forbidden_profile.json()["detail"] == "Not authorized to view this profile"

    teacher_profile = client.get(
        f"/api/gamification/profile/{seeded_ids['student@eduquest.com']}",
        headers=auth_headers("teacher@eduquest.com"),
    )
    assert teacher_profile.status_code == 200

    forbidden_completion = client.post(
        f"/api/gamification/profile/{seeded_ids['student@eduquest.com']}/complete_lesson/1",
        headers=auth_headers("alice@eduquest.com"),
    )
    assert forbidden_completion.status_code == 403
    assert (
        forbidden_completion.json()["detail"]
        == "Not authorized to update this profile"
    )


def test_quiz_submission_and_attempt_access_rules(client, auth_headers, seeded_ids):
    submit = client.post(
        "/api/quizzes/2/submit",
        headers=auth_headers("student@eduquest.com"),
        json={"answers": [0, 0, 0, 0, 0, 0, 0]},
    )
    assert submit.status_code == 200
    body = submit.json()
    assert body["score"] == pytest.approx(6 / 7)
    assert "attempt_id" in body
    assert "new_streak" in body
    assert body["correct_answers"] == 6
    assert body["total_questions"] == 7
    assert body["wrong_answer_indexes"] == [1]
    assert len(body["wrong_answers"]) == 1
    assert body["wrong_answers"][0]["correct_answer_index"] == 1

    invalid_submit = client.post(
        "/api/quizzes/2/submit",
        headers=auth_headers("student@eduquest.com"),
        json={"answers": [0]},
    )
    assert invalid_submit.status_code == 400
    assert invalid_submit.json()["detail"] == "Answer count does not match quiz"

    own_attempts = client.get(
        f"/api/quizzes/user/{seeded_ids['student@eduquest.com']}/attempts",
        headers=auth_headers("student@eduquest.com"),
    )
    assert own_attempts.status_code == 200
    assert len(own_attempts.json()) >= 1

    forbidden_attempts = client.get(
        f"/api/quizzes/user/{seeded_ids['student@eduquest.com']}/attempts",
        headers=auth_headers("alice@eduquest.com"),
    )
    assert forbidden_attempts.status_code == 403

    teacher_attempts = client.get(
        f"/api/quizzes/user/{seeded_ids['student@eduquest.com']}/attempts",
        headers=auth_headers("teacher@eduquest.com"),
    )
    assert teacher_attempts.status_code == 200


def test_missing_quiz_returns_404_in_read_and_submit_paths(client, auth_headers):
    missing_quiz = client.get(
        "/api/quizzes/lesson/999",
        headers=auth_headers("student@eduquest.com"),
    )
    assert missing_quiz.status_code == 404
    assert missing_quiz.json()["detail"] == "Quiz not found"

    missing_submit = client.post(
        "/api/quizzes/999/submit",
        headers=auth_headers("student@eduquest.com"),
        json={"answers": [0]},
    )
    assert missing_submit.status_code == 404
    assert missing_submit.json()["detail"] == "Quiz not found"


def test_student_safe_config_and_retry_policy_enforcement(client, auth_headers):
    config = client.get("/api/app/config")
    assert config.status_code == 200
    assert config.json()["retries_enabled"] is True
    assert "xp_per_quiz" in config.json()

    first_submit = client.post(
        "/api/quizzes/4/submit",
        headers=auth_headers("student@eduquest.com"),
        json={"answers": [0, 0, 0, 0, 0, 0, 0]},
    )
    assert first_submit.status_code == 200

    disable_retries = client.put(
        "/api/admin/config",
        headers=auth_headers("admin@eduquest.com"),
        json={
            "ai_safety": True,
            "retries_enabled": False,
            "xp_per_quiz": 100,
        },
    )
    assert disable_retries.status_code == 200

    second_submit = client.post(
        "/api/quizzes/4/submit",
        headers=auth_headers("student@eduquest.com"),
        json={"answers": [0, 0, 0, 0, 0, 0, 0]},
    )
    assert second_submit.status_code == 409
    assert second_submit.json()["detail"] == "Quiz retries are disabled for this lesson"


def test_auth_me_accepts_firebase_bearer_for_existing_user(client, monkeypatch):
    monkeypatch.setattr(
        dependencies,
        "verify_firebase_bearer_token",
        lambda token: FirebaseIdentity(
            uid="firebase-student-uid",
            email="student@eduquest.com",
            full_name="Student Demo",
        ),
    )

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer firebase-token"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == "student@eduquest.com"
    assert response.json()["role"] == "student"


def test_register_profile_creates_local_user_for_firebase_account(client, monkeypatch):
    monkeypatch.setattr(
        dependencies,
        "verify_firebase_bearer_token",
        lambda token: FirebaseIdentity(
            uid="firebase-new-user-uid",
            email="fresh.firebase.user@eduquest.com",
            full_name="Fresh Firebase User",
        ),
    )

    register = client.post(
        "/api/auth/register-profile",
        headers={"Authorization": "Bearer firebase-token"},
        json={"full_name": "Fresh Firebase User"},
    )
    assert register.status_code == 200
    body = register.json()
    assert body["email"] == "fresh.firebase.user@eduquest.com"
    assert body["role"] == "student"

    me = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer firebase-token"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == "fresh.firebase.user@eduquest.com"


def test_ai_review_shapes_and_user_validation(client, auth_headers, seeded_ids, monkeypatch):
    monkeypatch.setattr(ai_tutor_router.time, "sleep", lambda _: None)

    payload = {
        "user_id": seeded_ids["student@eduquest.com"],
        "lesson_title": "Variables and Data Types",
        "wrong_answers": [
            {
                "question": "Which is NOT a standard data type?",
                "options": ["Integer", "String", "Elephant", "Boolean"],
                "user_answer_index": 1,
                "correct_answer_index": 2,
            },
        ],
    }

    review = client.post(
        "/api/ai-tutor/review-mistakes",
        headers=auth_headers("student@eduquest.com"),
        json=payload,
    )
    assert review.status_code == 200
    review_body = review.json()
    assert "summary" in review_body
    assert isinstance(review_body["explanations"], list)

    chat = client.post(
        "/api/ai-tutor/review-chat",
        headers=auth_headers("student@eduquest.com"),
        json={**payload, "user_question": "Why is Elephant wrong?"},
    )
    assert chat.status_code == 200
    assert "answer" in chat.json()

    forbidden = client.post(
        "/api/ai-tutor/review-mistakes",
        headers=auth_headers("student@eduquest.com"),
        json={**payload, "user_id": seeded_ids["alice@eduquest.com"]},
    )
    assert forbidden.status_code == 403
