from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Literal

import openai
from openai import OpenAI
from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)
BACKEND_DIR = Path(__file__).resolve().parent
ENV_PATH = BACKEND_DIR / ".env"

SUPPORTED_DIFFICULTIES = ("easy", "medium", "hard")
SUPPORTED_TYPES = ("mcq", "true_false", "code_output", "fill_gap", "ordering")


class EModeLLMError(RuntimeError):
    status_code = 502


class EModeLLMConfigError(EModeLLMError):
    status_code = 503


class EModeLLMProviderError(EModeLLMError):
    status_code = 502


class EModeLLMOutputError(EModeLLMError):
    status_code = 422


class EModeQuestionSchema(BaseModel):
    type: Literal["mcq", "true_false", "code_output", "fill_gap", "ordering"]
    q: str = Field(min_length=1)
    options: list[str] = Field(min_length=2)
    answer: int
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    topicTag: str = Field(min_length=1)
    hint: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    code: str | None = None


class EModeDraftSchema(BaseModel):
    title: str = Field(min_length=1)
    xp_reward: int = Field(ge=0, le=500)
    assistant_message: str = Field(min_length=1)
    questions: list[EModeQuestionSchema] = Field(min_length=1)


def _load_env_files() -> None:
    if not ENV_PATH.exists():
        return
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ[key] = value


def _first_env(*keys: str, default: str = "") -> str:
    for key in keys:
        value = os.getenv(key, "").strip()
        if value:
            return value
    return default


def build_e_mode_prompt(
    *,
    topic: str,
    instructions: str,
    student_level: str | None,
    difficulty: str | None,
    language: str | None,
    task_count: int | None,
    preferred_types: list[str],
    supported_types: list[str],
    draft: dict[str, Any] | None,
    recent_messages: list[dict[str, str]],
    material_context: str,
    teacher_message: str,
) -> list[dict[str, str]]:
    system_prompt = f"""
You are EduQuest E-Mode, an educational task creation assistant.

You must return only a structured EduQuest quiz draft.

Hard rules:
- Base the draft mainly on the uploaded material context.
- Follow the teacher topic and instructions closely.
- Update the current draft instead of starting over when a draft already exists.
- Use only these exact EduQuest question types: {", ".join(supported_types)}.
- Never return: single_choice, multiple_choice, text_answer, short_answer, open_text, essay, written_response.
- If the teacher asks for an unsupported format, adapt it to the closest supported EduQuest type and explain that in assistant_message.
- Keep the output grounded in the uploaded material. Do not invent unsupported facts.
- Every question must contain q, options, answer, difficulty, topicTag, hint, explanation.
- code_output questions must also include code.
- difficulty must be one of: easy, medium, hard.
- xp_reward must be an integer from 0 to 500.
""".strip()

    user_payload = {
        "topic": topic,
        "instructions": instructions,
        "student_level": student_level,
        "difficulty": difficulty,
        "language": language,
        "task_count": task_count,
        "preferred_types": preferred_types,
        "supported_types": supported_types,
        "current_draft": draft,
        "recent_messages": recent_messages[-4:],
        "teacher_message": teacher_message,
        "material_context": material_context,
    }

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
    ]


def generate_draft_from_llm(messages: list[dict[str, str]]) -> dict[str, Any]:
    _load_env_files()

    model = _first_env("AI_MODEL", "E_MODE_MODEL", "STUDENT_AI_MODEL", "E_MODE_LLM_MODEL")
    api_key = _first_env("OPENAI_API_KEY", "E_MODE_LLM_API_KEY")
    base_url = _first_env("OPENAI_BASE_URL", "E_MODE_LLM_API_URL") or None
    timeout_raw = _first_env(
        "AI_TIMEOUT_SECONDS",
        "E_MODE_TIMEOUT_SECONDS",
        "STUDENT_AI_TIMEOUT_SECONDS",
        "E_MODE_LLM_TIMEOUT",
        default="45",
    )

    if not api_key:
        logger.error("E-Mode AI configuration missing OPENAI_API_KEY")
        raise EModeLLMConfigError(f"E-Mode AI is not configured. Set OPENAI_API_KEY in {ENV_PATH}.")
    if not model:
        logger.error("E-Mode AI configuration missing AI_MODEL")
        raise EModeLLMConfigError(f"E-Mode AI is not configured. Set AI_MODEL in {ENV_PATH}.")

    try:
        timeout_seconds = int(timeout_raw)
    except ValueError as exc:
        logger.error("E-Mode AI configuration has invalid AI_TIMEOUT_SECONDS value")
        raise EModeLLMConfigError(f"AI_TIMEOUT_SECONDS in {ENV_PATH} must be an integer.") from exc

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout_seconds)

    try:
        completion = client.beta.chat.completions.parse(
            model=model,
            messages=messages,
            response_format=EModeDraftSchema,
            temperature=0,
            top_p=1,
            max_completion_tokens=1200,
            store=True,
        )
    except openai.AuthenticationError as exc:
        logger.exception("E-Mode AI authentication failure")
        raise EModeLLMProviderError("E-Mode AI authentication failed. Check OPENAI_API_KEY.") from exc
    except openai.RateLimitError as exc:
        logger.exception("E-Mode AI rate limit failure")
        raise EModeLLMProviderError("E-Mode AI rate limit reached. Try again later.") from exc
    except (openai.APIConnectionError, openai.APITimeoutError) as exc:
        logger.exception("E-Mode AI connectivity failure")
        raise EModeLLMProviderError("E-Mode AI request failed due to a network or timeout problem.") from exc
    except openai.BadRequestError as exc:
        logger.exception("E-Mode AI bad request failure")
        raise EModeLLMProviderError(f"E-Mode AI request was rejected by the provider: {exc}") from exc
    except openai.APIStatusError as exc:
        logger.exception("E-Mode AI provider status failure")
        raise EModeLLMProviderError(f"E-Mode AI provider returned HTTP {exc.status_code}.") from exc
    except Exception as exc:  # pragma: no cover - defensive provider catch
        logger.exception("Unexpected E-Mode AI provider failure")
        raise EModeLLMProviderError("E-Mode AI request failed unexpectedly.") from exc

    message = completion.choices[0].message
    parsed = message.parsed
    raw_content = message.content
    if parsed is None:
        logger.error("E-Mode AI returned no parsed draft. Raw content excerpt: %s", _excerpt(raw_content))
        raise EModeLLMOutputError("E-Mode AI returned an empty or unparseable draft.")

    draft = parsed.model_dump()
    logger.info(
        "E-Mode AI draft generated with %s questions and title '%s'",
        len(draft.get("questions", [])),
        draft.get("title", ""),
    )
    return draft


def _excerpt(raw_content: str | list[Any] | None, limit: int = 400) -> str:
    if raw_content is None:
        return "<empty>"
    if isinstance(raw_content, list):
        pieces = []
        for item in raw_content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    pieces.append(text)
        raw_text = "".join(pieces)
    else:
        raw_text = str(raw_content)
    raw_text = raw_text.replace("\n", " ").strip()
    return raw_text[:limit]
