from __future__ import annotations

from dataclasses import dataclass
from typing import Any


SUPPORTED_E_MODE_TYPES = [
    "mcq",
    "true_false",
    "code_output",
    "fill_gap",
    "ordering",
]

SUPPORTED_DIFFICULTIES = {"easy", "medium", "hard"}


class EModeValidationError(ValueError):
    pass


@dataclass
class NormalizedDraft:
    title: str
    xp_reward: int
    questions: list[dict[str, Any]]
    assistant_message: str


def get_supported_question_types() -> list[str]:
    return list(SUPPORTED_E_MODE_TYPES)


def _normalize_text(value: Any, *, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise EModeValidationError(f"{field_name} is required")
    return text


def _normalize_optional_text(value: Any, default: str) -> str:
    text = str(value or "").strip()
    return text if text else default


def _normalize_options(question: dict[str, Any], *, question_type: str) -> list[str]:
    if question_type == "true_false":
        return ["True", "False"]

    options = question.get("options")
    if not isinstance(options, list):
        raise EModeValidationError("Question options must be a list")

    normalized = [str(option).strip() for option in options if str(option).strip()]
    if len(normalized) < 2:
        raise EModeValidationError("Each question must contain at least two answer options")
    return normalized


def _normalize_answer_index(question: dict[str, Any], options: list[str]) -> int:
    answer = question.get("answer", question.get("correctIndex"))
    if not isinstance(answer, int):
        raise EModeValidationError("Each question must include an integer answer index")
    if answer < 0 or answer >= len(options):
        raise EModeValidationError("Question answer index is outside the options list")
    return answer


def normalize_question(raw_question: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw_question, dict):
        raise EModeValidationError("Question items must be objects")

    question_type = str(raw_question.get("type") or "").strip()
    if question_type not in SUPPORTED_E_MODE_TYPES:
        raise EModeValidationError(
            f"Unsupported question type '{question_type}'. Supported types: {', '.join(SUPPORTED_E_MODE_TYPES)}"
        )

    prompt = _normalize_text(
        raw_question.get("q") or raw_question.get("question"),
        field_name="Question text",
    )
    options = _normalize_options(raw_question, question_type=question_type)
    answer_index = _normalize_answer_index(raw_question, options)

    normalized = {
        "type": question_type,
        "q": prompt,
        "question": prompt,
        "options": options,
        "answer": answer_index,
        "correctIndex": answer_index,
        "explanation": _normalize_optional_text(
            raw_question.get("explanation"),
            "Review the lesson concept and compare it with the selected answer.",
        ),
        "difficulty": (
            raw_question.get("difficulty")
            if raw_question.get("difficulty") in SUPPORTED_DIFFICULTIES
            else "medium"
        ),
        "topicTag": _normalize_optional_text(raw_question.get("topicTag"), "ai-generated"),
        "hint": _normalize_optional_text(
            raw_question.get("hint"),
            "Focus on the lesson material and compare each option carefully.",
        ),
    }

    if question_type == "code_output":
        code = _normalize_text(raw_question.get("code"), field_name="Code block")
        normalized["code"] = code

    return normalized


def normalize_draft(raw_draft: dict[str, Any], *, fallback_title: str) -> NormalizedDraft:
    if not isinstance(raw_draft, dict):
        raise EModeValidationError("AI output must be a JSON object")

    raw_questions = raw_draft.get("questions")
    if not isinstance(raw_questions, list) or not raw_questions:
        raise EModeValidationError("AI output must contain at least one question")

    normalized_questions = [normalize_question(question) for question in raw_questions]

    title = str(raw_draft.get("title") or fallback_title).strip()
    if not title:
        raise EModeValidationError("Draft title is required")

    xp_reward = raw_draft.get("xp_reward", 100)
    if not isinstance(xp_reward, int):
        raise EModeValidationError("xp_reward must be an integer")
    if xp_reward < 0 or xp_reward > 500:
        raise EModeValidationError("xp_reward must be between 0 and 500")

    assistant_message = _normalize_optional_text(
        raw_draft.get("assistant_message"),
        "I updated the draft using the uploaded material and your latest request.",
    )

    return NormalizedDraft(
        title=title,
        xp_reward=xp_reward,
        questions=normalized_questions,
        assistant_message=assistant_message,
    )
