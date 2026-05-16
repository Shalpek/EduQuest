import io
import json
import zipfile

import pytest

import e_mode_llm
import routers.e_mode as e_mode_router
from e_mode_llm import EModeLLMConfigError, EModeLLMProviderError
from e_mode_schema import EModeValidationError, normalize_draft


def _create_session(client, auth_headers, lesson_id=1):
    return client.post(
        "/api/teacher/e-mode/sessions",
        headers=auth_headers("teacher@eduquest.com"),
        json={
            "course_id": 1,
            "lesson_id": lesson_id,
            "topic": "Variables and data types",
            "instructions": "Focus on fundamentals for beginners",
            "student_level": "beginner",
            "difficulty": "easy",
            "language": "English",
            "task_count": 4,
            "preferred_types": ["mcq", "true_false"],
            "quiz_title": "AI-generated Variables Quiz",
        },
    )


def test_e_mode_session_requires_teacher_auth(client, auth_headers):
    teacher = _create_session(client, auth_headers)
    assert teacher.status_code == 200
    body = teacher.json()
    assert body["topic"] == "Variables and data types"
    assert set(body["supported_types"]) == {
        "mcq",
        "true_false",
        "code_output",
        "fill_gap",
        "ordering",
    }

    student = client.post(
        "/api/teacher/e-mode/sessions",
        headers=auth_headers("student@eduquest.com"),
        json={
            "course_id": 1,
            "lesson_id": 1,
            "topic": "Should fail",
        },
    )
    assert student.status_code == 403


def test_e_mode_upload_validation_and_txt_extraction(client, auth_headers):
    session = _create_session(client, auth_headers).json()

    unsupported = client.post(
        f"/api/teacher/e-mode/sessions/{session['id']}/upload",
        headers=auth_headers("teacher@eduquest.com"),
        files={"file": ("lesson.md", b"# Unsupported", "text/markdown")},
    )
    assert unsupported.status_code == 400

    uploaded = client.post(
        f"/api/teacher/e-mode/sessions/{session['id']}/upload",
        headers=auth_headers("teacher@eduquest.com"),
        files={"file": ("material.txt", b"Variables store values.\n\nBooleans hold true or false.", "text/plain")},
    )
    assert uploaded.status_code == 200
    body = uploaded.json()
    assert body["material_ready"] is True
    assert body["uploaded_file_name"] == "material.txt"
    assert body["extracted_char_count"] > 10


def test_e_mode_generate_can_use_lesson_content_without_upload(client, auth_headers, monkeypatch):
    session = _create_session(client, auth_headers).json()

    monkeypatch.setattr(
        e_mode_router,
        "generate_draft_from_llm",
        lambda _messages: {
            "title": "Lesson-content draft",
            "xp_reward": 95,
            "assistant_message": "Drafted from lesson content.",
            "questions": [
                {
                    "type": "mcq",
                    "q": "What do variables store?",
                    "options": ["Values", "Errors"],
                    "answer": 0,
                    "difficulty": "easy",
                    "topicTag": "variables",
                    "hint": "Think about memory.",
                    "explanation": "Variables store values for later use.",
                }
            ],
        },
    )

    generated = client.post(
        f"/api/teacher/e-mode/sessions/{session['id']}/generate",
        headers=auth_headers("teacher@eduquest.com"),
    )
    assert generated.status_code == 200
    body = generated.json()
    assert body["draft"]["title"] == "Lesson-content draft"
    assert body["generation_source"] == "lesson_content"


def test_e_mode_upload_docx_extraction(client, auth_headers):
    session = _create_session(client, auth_headers).json()

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "word/document.xml",
            (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                "<w:body>"
                "<w:p><w:r><w:t>Functions group reusable logic.</w:t></w:r></w:p>"
                "<w:p><w:r><w:t>Parameters pass input values.</w:t></w:r></w:p>"
                "</w:body>"
                "</w:document>"
            ),
        )

    uploaded = client.post(
        f"/api/teacher/e-mode/sessions/{session['id']}/upload",
        headers=auth_headers("teacher@eduquest.com"),
        files={
            "file": (
                "material.docx",
                buffer.getvalue(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert uploaded.status_code == 200
    body = uploaded.json()
    assert body["material_ready"] is True
    assert body["extracted_char_count"] > 20


def test_e_mode_prompt_uses_recent_messages_and_current_draft(client, auth_headers, monkeypatch):
    session = _create_session(client, auth_headers).json()
    upload = client.post(
        f"/api/teacher/e-mode/sessions/{session['id']}/upload",
        headers=auth_headers("teacher@eduquest.com"),
        files={"file": ("material.txt", b"Variables store values. True/false checks booleans.", "text/plain")},
    )
    assert upload.status_code == 200

    captured_payloads = []

    def fake_llm(messages):
        captured_payloads.append(json.loads(messages[-1]["content"]))
        return {
            "title": "Variables quiz",
            "xp_reward": 90,
            "assistant_message": "I generated a first draft.",
            "questions": [
                {
                    "type": "mcq",
                    "q": "What does a variable do?",
                    "options": ["Stores a value", "Deletes code"],
                    "answer": 0,
                    "difficulty": "easy",
                    "topicTag": "variables",
                    "hint": "Think about memory.",
                    "explanation": "Variables keep data for later use.",
                }
            ],
        }

    monkeypatch.setattr(e_mode_router, "generate_draft_from_llm", fake_llm)

    initial_generate = client.post(
        f"/api/teacher/e-mode/sessions/{session['id']}/generate",
        headers=auth_headers("teacher@eduquest.com"),
    )
    assert initial_generate.status_code == 200
    assert captured_payloads[-1]["current_draft"] is None

    follow_up = client.post(
        f"/api/teacher/e-mode/sessions/{session['id']}/chat",
        headers=auth_headers("teacher@eduquest.com"),
        json={"message": "Make it easier and add more true/false questions."},
    )
    assert follow_up.status_code == 200
    payload = captured_payloads[-1]
    assert payload["teacher_message"] == "Make it easier and add more true/false questions."
    assert payload["current_draft"]["title"] == "Variables quiz"
    assert len(payload["recent_messages"]) >= 2


def test_e_mode_save_creates_standard_quiz_record(client, auth_headers, monkeypatch):
    session = _create_session(client, auth_headers).json()
    existing_quiz = client.get(
        "/api/quizzes/lesson/1",
        headers=auth_headers("teacher@eduquest.com"),
    )
    assert existing_quiz.status_code == 200
    original_quiz_id = existing_quiz.json()["id"]

    upload = client.post(
        f"/api/teacher/e-mode/sessions/{session['id']}/upload",
        headers=auth_headers("teacher@eduquest.com"),
        files={"file": ("material.txt", b"Loops repeat code. Variables store values.", "text/plain")},
    )
    assert upload.status_code == 200

    monkeypatch.setattr(
        e_mode_router,
        "generate_draft_from_llm",
        lambda _messages: {
            "title": "Teacher AI Quiz",
            "xp_reward": 120,
            "assistant_message": "Draft updated.",
            "questions": [
                {
                    "type": "true_false",
                    "q": "True or false: variables store data.",
                    "options": ["True", "False"],
                    "answer": 0,
                    "difficulty": "easy",
                    "topicTag": "variables",
                    "hint": "Recall the definition.",
                    "explanation": "Variables store values for later use.",
                }
            ],
        },
    )

    generate = client.post(
        f"/api/teacher/e-mode/sessions/{session['id']}/generate",
        headers=auth_headers("teacher@eduquest.com"),
    )
    assert generate.status_code == 200

    saved = client.post(
        f"/api/teacher/e-mode/sessions/{session['id']}/save",
        headers=auth_headers("teacher@eduquest.com"),
        json={},
    )
    assert saved.status_code == 200
    body = saved.json()
    assert body["saved"] is True
    assert body["quiz"]["title"] == "Teacher AI Quiz"
    assert body["quiz"]["question_count"] == 1
    assert body["quiz"]["id"] == original_quiz_id
    assert body["replaced_existing_quiz"] is True


def test_e_mode_generate_returns_503_when_ai_is_not_configured(client, auth_headers, monkeypatch):
    session = _create_session(client, auth_headers).json()
    upload = client.post(
        f"/api/teacher/e-mode/sessions/{session['id']}/upload",
        headers=auth_headers("teacher@eduquest.com"),
        files={"file": ("material.txt", b"Variables store values.", "text/plain")},
    )
    assert upload.status_code == 200

    def fail_with_missing_config(_messages):
        raise EModeLLMConfigError("E-Mode AI is not configured. Set AI_MODEL in backend/.env.")

    monkeypatch.setattr(e_mode_router, "generate_draft_from_llm", fail_with_missing_config)

    generated = client.post(
        f"/api/teacher/e-mode/sessions/{session['id']}/generate",
        headers=auth_headers("teacher@eduquest.com"),
    )
    assert generated.status_code == 503
    assert "AI_MODEL" in generated.json()["detail"]


def test_e_mode_generate_returns_502_when_provider_fails(client, auth_headers, monkeypatch):
    session = _create_session(client, auth_headers).json()
    upload = client.post(
        f"/api/teacher/e-mode/sessions/{session['id']}/upload",
        headers=auth_headers("teacher@eduquest.com"),
        files={"file": ("material.txt", b"Variables store values.", "text/plain")},
    )
    assert upload.status_code == 200

    def fail_with_provider_error(_messages):
        raise EModeLLMProviderError("E-Mode AI request failed due to a network or timeout problem.")

    monkeypatch.setattr(e_mode_router, "generate_draft_from_llm", fail_with_provider_error)

    generated = client.post(
        f"/api/teacher/e-mode/sessions/{session['id']}/generate",
        headers=auth_headers("teacher@eduquest.com"),
    )
    assert generated.status_code == 502


def test_e_mode_config_prefers_shared_keys(monkeypatch):
    monkeypatch.setattr(e_mode_llm, "_load_env_files", lambda: None)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AI_MODEL", "shared-model")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("AI_TIMEOUT_SECONDS", "21")
    monkeypatch.delenv("E_MODE_MODEL", raising=False)
    monkeypatch.delenv("E_MODE_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("STUDENT_AI_MODEL", raising=False)
    monkeypatch.delenv("STUDENT_AI_TIMEOUT_SECONDS", raising=False)

    captured = {}

    class _Parsed:
        def model_dump(self):
            return {
                "title": "Shared key draft",
                "xp_reward": 100,
                "assistant_message": "ok",
                "questions": [
                    {
                        "type": "mcq",
                        "q": "Question",
                        "options": ["A", "B"],
                        "answer": 0,
                        "difficulty": "easy",
                        "topicTag": "topic",
                        "hint": "hint",
                        "explanation": "explanation",
                        "code": None,
                    }
                ],
            }

    class _Message:
        parsed = _Parsed()
        content = '{"ok":true}'

    class _Completions:
        def parse(self, **kwargs):
            captured.update(kwargs)
            return type("Completion", (), {"choices": [type("Choice", (), {"message": _Message()})()]})()

    class _Chat:
        completions = _Completions()

    class _Beta:
        chat = _Chat()

    class _Client:
        def __init__(self, api_key, base_url, timeout):
            captured["api_key"] = api_key
            captured["base_url"] = base_url
            captured["timeout"] = timeout
            self.beta = _Beta()

    monkeypatch.setattr(e_mode_llm, "OpenAI", _Client)

    draft = e_mode_llm.generate_draft_from_llm([{"role": "user", "content": "test"}])

    assert draft["title"] == "Shared key draft"
    assert captured["api_key"] == "test-key"
    assert captured["base_url"] == "https://example.test/v1"
    assert captured["timeout"] == 21
    assert captured["model"] == "shared-model"


def test_e_mode_config_falls_back_to_legacy_keys(monkeypatch):
    monkeypatch.setattr(e_mode_llm, "_load_env_files", lambda: None)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("AI_MODEL", raising=False)
    monkeypatch.delenv("AI_TIMEOUT_SECONDS", raising=False)
    monkeypatch.setenv("E_MODE_MODEL", "legacy-e-mode-model")
    monkeypatch.setenv("E_MODE_TIMEOUT_SECONDS", "29")

    captured = {}

    class _Parsed:
        def model_dump(self):
            return {
                "title": "Legacy key draft",
                "xp_reward": 100,
                "assistant_message": "ok",
                "questions": [
                    {
                        "type": "mcq",
                        "q": "Question",
                        "options": ["A", "B"],
                        "answer": 0,
                        "difficulty": "easy",
                        "topicTag": "topic",
                        "hint": "hint",
                        "explanation": "explanation",
                        "code": None,
                    }
                ],
            }

    class _Message:
        parsed = _Parsed()
        content = '{"ok":true}'

    class _Completions:
        def parse(self, **kwargs):
            captured.update(kwargs)
            return type("Completion", (), {"choices": [type("Choice", (), {"message": _Message()})()]})()

    class _Chat:
        completions = _Completions()

    class _Beta:
        chat = _Chat()

    class _Client:
        def __init__(self, api_key, base_url, timeout):
            captured["timeout"] = timeout
            self.beta = _Beta()

    monkeypatch.setattr(e_mode_llm, "OpenAI", _Client)

    e_mode_llm.generate_draft_from_llm([{"role": "user", "content": "test"}])

    assert captured["model"] == "legacy-e-mode-model"
    assert captured["timeout"] == 29


def test_e_mode_rejects_invalid_ai_output():
    with pytest.raises(EModeValidationError):
        normalize_draft(
            {
                "title": "Bad quiz",
                "xp_reward": 100,
                "questions": [
                    {
                        "type": "text_answer",
                        "q": "Unsupported",
                        "options": ["A", "B"],
                        "answer": 0,
                    }
                ],
            },
            fallback_title="Fallback",
        )
