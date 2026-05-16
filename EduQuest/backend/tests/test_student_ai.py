import json

import pytest

import database
import models
import routers.ai_tutor as ai_tutor_router
import student_ai_service
from student_ai_service import StudentAIConfigurationError, StudentAIProviderError


def test_student_ai_config_prefers_shared_keys(monkeypatch):
    monkeypatch.setattr(student_ai_service, "_ENV_LOADED", True)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AI_MODEL", "shared-model")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("AI_TIMEOUT_SECONDS", "33")
    monkeypatch.delenv("STUDENT_AI_MODEL", raising=False)
    monkeypatch.delenv("STUDENT_AI_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("E_MODE_MODEL", raising=False)
    monkeypatch.delenv("E_MODE_TIMEOUT_SECONDS", raising=False)

    config = student_ai_service.load_student_ai_config()

    assert config.api_key == "test-key"
    assert config.model == "shared-model"
    assert config.base_url == "https://example.test/v1"
    assert config.timeout_seconds == 33


def test_student_ai_config_falls_back_to_legacy_keys(monkeypatch):
    monkeypatch.setattr(student_ai_service, "_ENV_LOADED", True)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("AI_MODEL", raising=False)
    monkeypatch.delenv("AI_TIMEOUT_SECONDS", raising=False)
    monkeypatch.setenv("STUDENT_AI_MODEL", "legacy-student-model")
    monkeypatch.setenv("STUDENT_AI_TIMEOUT_SECONDS", "27")

    config = student_ai_service.load_student_ai_config()

    assert config.model == "legacy-student-model"
    assert config.timeout_seconds == 27


def test_student_ai_config_error_mentions_shared_keys(monkeypatch):
    monkeypatch.setattr(student_ai_service, "_ENV_LOADED", True)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AI_MODEL", raising=False)
    monkeypatch.delenv("STUDENT_AI_MODEL", raising=False)
    monkeypatch.delenv("E_MODE_MODEL", raising=False)

    with pytest.raises(StudentAIConfigurationError) as exc_info:
        student_ai_service.load_student_ai_config()

    assert "OPENAI_API_KEY" in str(exc_info.value)
    assert "AI_MODEL" in str(exc_info.value)


def test_open_question_session_validates_student_and_lesson_course_link(client, auth_headers):
    ok = client.post(
        "/api/ai-tutor/open-question/sessions",
        headers=auth_headers("student@eduquest.com"),
        json={"course_id": 1, "lesson_id": 1},
    )
    assert ok.status_code == 200
    assert ok.json()["mode"] == "open_question"

    mismatch = client.post(
        "/api/ai-tutor/open-question/sessions",
        headers=auth_headers("student@eduquest.com"),
        json={"course_id": 1, "lesson_id": 14},
    )
    assert mismatch.status_code == 422

    teacher_forbidden = client.post(
        "/api/ai-tutor/open-question/sessions",
        headers=auth_headers("teacher@eduquest.com"),
        json={"course_id": 1, "lesson_id": 1},
    )
    assert teacher_forbidden.status_code == 403


def test_open_question_message_uses_recent_history_and_handles_provider_errors(client, auth_headers, monkeypatch):
    create_response = client.post(
        "/api/ai-tutor/open-question/sessions",
        headers=auth_headers("student@eduquest.com"),
        json={"course_id": 1, "lesson_id": 1},
    )
    session_id = create_response.json()["session_id"]

    for idx in range(3):
        monkeypatch.setattr(
            ai_tutor_router,
            "chat_completion",
            lambda messages, idx=idx: f"answer-{idx}",
        )
        sent = client.post(
            f"/api/ai-tutor/open-question/sessions/{session_id}/message",
            headers=auth_headers("student@eduquest.com"),
            json={"message": f"question-{idx}"},
        )
        assert sent.status_code == 200

    captured = {}

    def _capture(messages):
        captured["messages"] = messages
        return "final-answer"

    monkeypatch.setattr(ai_tutor_router, "chat_completion", _capture)
    final_response = client.post(
        f"/api/ai-tutor/open-question/sessions/{session_id}/message",
        headers=auth_headers("student@eduquest.com"),
        json={"message": "Explain it more simply"},
    )
    assert final_response.status_code == 200
    assert final_response.json()["answer"] == "final-answer"
    assert len(captured["messages"]) == 7

    monkeypatch.setattr(
        ai_tutor_router,
        "chat_completion",
        lambda _: (_ for _ in ()).throw(StudentAIConfigurationError("missing config")),
    )
    no_config = client.post(
        f"/api/ai-tutor/open-question/sessions/{session_id}/message",
        headers=auth_headers("student@eduquest.com"),
        json={"message": "One more question"},
    )
    assert no_config.status_code == 503

    monkeypatch.setattr(
        ai_tutor_router,
        "chat_completion",
        lambda _: (_ for _ in ()).throw(StudentAIProviderError("provider failed")),
    )
    provider_fail = client.post(
        f"/api/ai-tutor/open-question/sessions/{session_id}/message",
        headers=auth_headers("student@eduquest.com"),
        json={"message": "Try again"},
    )
    assert provider_fail.status_code == 502


def test_quiz_submit_persists_answer_snapshot_and_explanation_session(client, auth_headers, monkeypatch):
    submit = client.post(
        "/api/quizzes/2/submit",
        headers=auth_headers("student@eduquest.com"),
        json={"answers": [0, 0, 0, 0, 0, 0, 0]},
    )
    assert submit.status_code == 200
    attempt_id = submit.json()["attempt_id"]

    db = database.SessionLocal()
    try:
        attempt = db.query(models.Attempt).filter(models.Attempt.id == attempt_id).first()
        assert attempt is not None
        assert json.loads(attempt.student_answers_json) == [0, 0, 0, 0, 0, 0, 0]
        assert json.loads(attempt.wrong_answer_indexes_json) == [1]
    finally:
        db.close()

    explanation = client.post(
        "/api/ai-tutor/quiz-explanation/sessions",
        headers=auth_headers("student@eduquest.com"),
        json={"attempt_id": attempt_id},
    )
    assert explanation.status_code == 200
    explanation_body = explanation.json()
    assert explanation_body["mode"] == "quiz_explanation"
    assert explanation_body["summary"]
    assert len(explanation_body["explanations"]) == 1
    assert explanation_body["selected_question_indexes"] == [1]

    monkeypatch.setattr(ai_tutor_router, "chat_completion", lambda _: "Follow-up answer")
    follow_up = client.post(
        f"/api/ai-tutor/quiz-explanation/sessions/{explanation_body['session_id']}/message",
        headers=auth_headers("student@eduquest.com"),
        json={"message": "Why is the last answer wrong?"},
    )
    assert follow_up.status_code == 200
    assert follow_up.json()["answer"] == "Follow-up answer"


def test_quiz_explanation_enforces_attempt_ownership_and_snapshot_presence(client, auth_headers):
    old_attempt = client.post(
        "/api/ai-tutor/quiz-explanation/sessions",
        headers=auth_headers("student@eduquest.com"),
        json={"attempt_id": 1},
    )
    assert old_attempt.status_code == 422

    foreign_submit = client.post(
        "/api/quizzes/4/submit",
        headers=auth_headers("alice@eduquest.com"),
        json={"answers": [0, 0, 0, 0, 0, 0, 0]},
    )
    assert foreign_submit.status_code == 200
    foreign_attempt_id = foreign_submit.json()["attempt_id"]

    forbidden = client.post(
        "/api/ai-tutor/quiz-explanation/sessions",
        headers=auth_headers("student@eduquest.com"),
        json={"attempt_id": foreign_attempt_id},
    )
    assert forbidden.status_code == 403
