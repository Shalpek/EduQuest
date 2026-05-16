from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import re
from typing import Iterable
from urllib import error, request

import models


class StudentAIConfigurationError(Exception):
    pass


class StudentAIProviderError(Exception):
    pass


@dataclass
class StudentAIConfig:
    api_key: str
    model: str
    base_url: str
    timeout_seconds: int


_ENV_LOADED = False
BACKEND_DIR = Path(__file__).resolve().parent
ENV_PATH = BACKEND_DIR / ".env"
OPEN_QUESTION_SYSTEM_PROMPT = (
    "You are an AI Tutor for students inside an educational platform. "
    "Help the student understand the selected course and lesson. "
    "Base your answer mainly on the provided lesson and course content. "
    "Be clear, educational, supportive, and sufficiently detailed. "
    "Adapt explanations to the student's level when that level is provided. "
    "Use examples when helpful. "
    "If the material is not enough, say that clearly and only then provide additional general context labelled as additional explanation. "
    "Do not invent facts. "
    "Do not expose hidden teacher or admin information. "
    "Do not give direct answers to active unfinished quizzes."
)

QUIZ_REVIEW_SYSTEM_PROMPT = (
    "You are an AI Tutor helping a student work on quiz mistakes after quiz completion. "
    "Use the completed attempt data, question, options, student answer, correct answer, lesson material, and the last four messages. "
    "Explain what the question is asking, why the student's answer was wrong or incomplete, why the correct answer is correct, and how to think about this concept next time. "
    "Be supportive, patient, and educational. "
    "Use step-by-step reasoning when useful. "
    "Do not shame the student. "
    "Focus only on the completed attempt and do not introduce unrelated private data."
)


def _load_backend_env_once() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return

    if ENV_PATH.exists():
        for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ[key.strip()] = value.strip().strip('"').strip("'")

    _ENV_LOADED = True


def _first_env(*keys: str, default: str = "") -> str:
    for key in keys:
        value = os.getenv(key, "").strip()
        if value:
            return value
    return default


def load_student_ai_config() -> StudentAIConfig:
    _load_backend_env_once()
    api_key = _first_env("OPENAI_API_KEY")
    model = _first_env("AI_MODEL", "STUDENT_AI_MODEL", "E_MODE_MODEL")
    base_url = _first_env("OPENAI_BASE_URL", default="https://api.openai.com/v1")
    timeout_raw = _first_env(
        "AI_TIMEOUT_SECONDS",
        "STUDENT_AI_TIMEOUT_SECONDS",
        "E_MODE_TIMEOUT_SECONDS",
        default="45",
    )

    if not api_key or not model:
        raise StudentAIConfigurationError(
            f"Student AI is not configured. Set OPENAI_API_KEY and AI_MODEL in {ENV_PATH}."
        )

    try:
        timeout_seconds = max(5, int(timeout_raw))
    except ValueError as exc:
        raise StudentAIConfigurationError(
            f"AI_TIMEOUT_SECONDS in {ENV_PATH} must be an integer."
        ) from exc

    return StudentAIConfig(
        api_key=api_key,
        model=model,
        base_url=base_url.rstrip("/"),
        timeout_seconds=timeout_seconds,
    )


def _chat_completions_url(base_url: str) -> str:
    if base_url.endswith("/chat/completions"):
        return base_url
    if base_url.endswith("/v1"):
        return f"{base_url}/chat/completions"
    return f"{base_url}/v1/chat/completions"


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _split_content_chunks(text: str) -> list[str]:
    if not text:
        return []

    raw_chunks = [
        _normalize_whitespace(chunk)
        for chunk in re.split(r"\n\s*\n|(?<=[.!?])\s+", text)
    ]
    return [chunk for chunk in raw_chunks if chunk]


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-zA-Z0-9_]+", (text or "").lower()) if len(token) > 2}


def select_relevant_chunks(text: str, query: str, limit: int = 3) -> list[str]:
    chunks = _split_content_chunks(text)
    if not chunks:
        return []

    query_tokens = _tokenize(query)
    if not query_tokens:
        return chunks[:limit]

    scored_chunks = []
    for index, chunk in enumerate(chunks):
        chunk_tokens = _tokenize(chunk)
        overlap = len(query_tokens & chunk_tokens)
        scored_chunks.append((overlap, -index, chunk))

    scored_chunks.sort(reverse=True)
    selected = [chunk for score, _, chunk in scored_chunks if score > 0][:limit]
    return selected or chunks[:limit]


def recent_session_messages(session: models.StudentAISession, limit: int = 4) -> list[models.StudentAIMessage]:
    messages = sorted(session.messages, key=lambda item: item.created_at or datetime.utcnow())
    return messages[-limit:]


def build_open_question_prompt(
    course: models.Course,
    lesson: models.Lesson,
    lesson_chunks: list[str],
    recent_messages: Iterable[models.StudentAIMessage],
    student_message: str,
    student_level: int | None = None,
) -> list[dict[str, str]]:
    material_context = {
        "student_level": student_level,
        "course": {
            "id": course.id,
            "title": course.title,
            "description": course.description,
        },
        "lesson": {
            "id": lesson.id,
            "title": lesson.title,
            "content_excerpt_count": len(lesson_chunks),
            "content_excerpts": lesson_chunks or ["No additional lesson excerpt available."],
        },
    }

    messages = [
        {"role": "system", "content": OPEN_QUESTION_SYSTEM_PROMPT},
        {"role": "system", "content": json.dumps(material_context, ensure_ascii=False)},
    ]
    for item in recent_messages:
        role = "assistant" if item.role == "assistant" else "user"
        messages.append({"role": role, "content": item.content})
    messages.append({"role": "user", "content": student_message})
    return messages


def build_quiz_follow_up_prompt(
    course: models.Course,
    lesson: models.Lesson,
    attempt: models.Attempt,
    explanation_items: list[dict],
    recent_messages: Iterable[models.StudentAIMessage],
    student_message: str,
    student_level: int | None = None,
) -> list[dict[str, str]]:
    mistakes = [item for item in explanation_items if item.get("is_correct") is False]
    attempt_summary = {
        "student_level": student_level,
        "course": {
            "id": course.id,
            "title": course.title,
            "description": course.description,
        },
        "lesson": {
            "id": lesson.id,
            "title": lesson.title,
        },
        "attempt": {
            "attempt_id": attempt.id,
            "quiz_id": attempt.quiz_id,
            "score": attempt.score,
            "earned_xp": attempt.earned_xp,
        },
        "mistakes": mistakes,
    }

    messages = [
        {"role": "system", "content": QUIZ_REVIEW_SYSTEM_PROMPT},
        {"role": "system", "content": json.dumps(attempt_summary, ensure_ascii=False)},
        {
            "role": "system",
            "content": "Relevant lesson excerpts:\n- "
            + "\n- ".join(
                select_relevant_chunks(
                    lesson.content or "",
                    " ".join(item["question"] for item in mistakes) or lesson.title,
                    limit=3,
                )
                or ["No matching lesson excerpt available."]
            ),
        },
    ]
    for item in recent_messages:
        role = "assistant" if item.role == "assistant" else "user"
        messages.append({"role": role, "content": item.content})
    messages.append({"role": "user", "content": student_message})
    return messages


def chat_completion(messages: list[dict[str, str]]) -> str:
    config = load_student_ai_config()
    payload = json.dumps(
        {
            "model": config.model,
            "temperature": 0.3,
            "messages": messages,
        }
    ).encode("utf-8")

    req = request.Request(
        _chat_completions_url(config.base_url),
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.api_key}",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=config.timeout_seconds) as response:
            response_body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise StudentAIProviderError(
            f"Student AI provider returned HTTP {exc.code}: {detail[:300]}"
        ) from exc
    except error.URLError as exc:
        raise StudentAIProviderError(f"Student AI provider connection failed: {exc}") from exc

    try:
        parsed = json.loads(response_body)
        content = parsed["choices"][0]["message"]["content"]
        if not content or not content.strip():
            raise KeyError("empty content")
        return content.strip()
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise StudentAIProviderError("Student AI returned an invalid response shape.") from exc


def _answer_text(question: dict, answer_index: int) -> str:
    options = question.get("options") or []
    if isinstance(options, list) and 0 <= answer_index < len(options):
        return str(options[answer_index])
    return "No answer selected"


def _question_schema_label(question: dict) -> str:
    options = question.get("options")
    answer = question.get("answer")
    question_type = str(question.get("type", "mcq"))
    if isinstance(options, list) and isinstance(answer, int):
        return question_type
    return "unsupported-or-unknown question schema"


def _explanation_from_question(
    question: dict,
    student_answer_text: str,
    correct_answer_text: str,
    lesson_excerpt: str,
) -> str:
    prompt = question.get("q", "This question")
    if lesson_excerpt and lesson_excerpt != "No direct lesson excerpt was found for this question.":
        return (
            f"The question is testing the idea behind '{prompt}'. "
            f"The lesson material points to this concept: {lesson_excerpt}"
        )
    return (
        f"The question is testing the concept described in '{prompt}'. "
        f"The correct option '{correct_answer_text}' matches that concept better than '{student_answer_text}'."
    )


def _why_answer_is_correct(question: dict, correct_answer_text: str, lesson_excerpt: str) -> str:
    prompt = question.get("q", "This question")
    if lesson_excerpt and lesson_excerpt != "No direct lesson excerpt was found for this question.":
        return (
            f"'{correct_answer_text}' is correct because it matches the concept highlighted by the lesson material for '{prompt}'. "
            f"The most relevant lesson idea is: {lesson_excerpt}"
        )
    return f"'{correct_answer_text}' is the best answer because it matches what '{prompt}' is really testing."


def build_attempt_explanations(
    attempt: models.Attempt,
    lesson: models.Lesson,
    question_index: int | None = None,
) -> list[dict]:
    try:
        questions = json.loads(attempt.quiz_questions_snapshot_json or "[]")
        student_answers = json.loads(attempt.student_answers_json or "[]")
        wrong_indexes = json.loads(attempt.wrong_answer_indexes_json or "[]")
    except json.JSONDecodeError:
        return []

    if question_index is not None:
        wrong_indexes = [idx for idx in wrong_indexes if idx == question_index]

    explanation_items: list[dict] = []
    for wrong_index in wrong_indexes:
        if not isinstance(wrong_index, int) or wrong_index < 0 or wrong_index >= len(questions):
            continue
        question = questions[wrong_index]
        if not isinstance(question, dict):
            continue

        correct_index = int(question.get("answer", -1))
        student_index = (
            int(student_answers[wrong_index])
            if wrong_index < len(student_answers) and isinstance(student_answers[wrong_index], int)
            else -1
        )
        query = f"{question.get('q', '')} {lesson.title}"
        relevant_chunks = select_relevant_chunks(lesson.content or "", query, limit=2)

        explanation_items.append(
            {
                "question_index": wrong_index,
                "question_id": wrong_index,
                "question": question.get("q", "Question"),
                "question_schema": _question_schema_label(question),
                "options": question.get("options") or [],
                "student_answer_index": student_index,
                "correct_answer_index": correct_index,
                "is_correct": False,
                "your_answer": _answer_text(question, student_index),
                "correct_answer": _answer_text(question, correct_index),
                "why_your_answer_was_wrong": (
                    f"Your selected option '{_answer_text(question, student_index)}' does not match the concept the question is testing."
                    if student_index >= 0
                    else "You did not submit a valid answer for this question."
                ),
                "why_correct_answer_is_correct": _why_answer_is_correct(
                    question,
                    _answer_text(question, correct_index),
                    relevant_chunks[0] if relevant_chunks else "",
                ),
                "explanation": _explanation_from_question(
                    question,
                    _answer_text(question, student_index),
                    _answer_text(question, correct_index),
                    relevant_chunks[0] if relevant_chunks else "",
                ),
                "lesson_connection": relevant_chunks[0]
                if relevant_chunks
                else "No direct lesson excerpt was found for this question.",
                "practice_tip": "Review the linked lesson idea, identify the exact concept in the question stem, and compare each option against that concept before you choose.",
            }
        )

    return explanation_items


def build_review_summary(lesson: models.Lesson, explanation_items: list[dict]) -> str:
    if not explanation_items:
        return (
            f"No incorrect answers were found for {lesson.title}. "
            "There is nothing for the AI tutor to explain in this attempt."
        )
    return (
        f"I found {len(explanation_items)} incorrect answer(s) in {lesson.title}. "
        "Start with the explanation cards, then ask follow-up questions if any concept is still unclear."
    )
