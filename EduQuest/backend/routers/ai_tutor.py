from datetime import datetime
import json
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from types import SimpleNamespace

import database
import dependencies
from student_ai_service import (
    StudentAIConfigurationError,
    StudentAIProviderError,
    build_attempt_explanations,
    build_open_question_prompt,
    build_quiz_follow_up_prompt,
    build_review_summary,
    chat_completion,
    recent_session_messages,
    select_relevant_chunks,
)
from firestore_primary_store import as_record, get_store


router = APIRouter()


def _store():
    return get_store()


class HintRequest(BaseModel):
    user_id: int
    context: str
    user_question: str


class ReviewMistake(BaseModel):
    question: str
    options: list[str]
    user_answer_index: int
    correct_answer_index: int
    explanation: str | None = None
    hint: str | None = None
    topicTag: str | None = None


class ReviewRequest(BaseModel):
    user_id: int
    lesson_title: str
    wrong_answers: list[ReviewMistake]


class ReviewFollowUpRequest(BaseModel):
    user_id: int
    lesson_title: str
    wrong_answers: list[ReviewMistake]
    user_question: str


class OpenQuestionSessionCreate(BaseModel):
    course_id: int
    lesson_id: int
    message: str | None = None


class StudentAIMessageCreate(BaseModel):
    message: str


class QuizExplanationSessionCreate(BaseModel):
    attempt_id: int
    question_index: int | None = None
    message: str | None = None


def _student_level(current_user) -> int | None:
    profile = _store().get_profile_by_user_id(current_user.id)
    if profile and isinstance(profile.get("level"), int):
        return profile["level"]
    return None


def _concept_explanation(question_text: str, correct_answer: str) -> str:
    q = question_text.lower()
    correct = correct_answer.lower()

    if "variable" in q:
        return f"The question is testing whether you know that a variable stores data that can be used later in a program. '{correct_answer}' fits that definition."
    if "data type" in q or "standard data type" in q:
        return f"The key idea is to recognize which option is a real programming data type and which one is just an everyday word. '{correct_answer}' is the option that breaks the data-type pattern."
    if "loop" in q or "for loop" in q or "while loop" in q:
        return f"This question is about choosing the right repetition structure. '{correct_answer}' is correct because it matches the situation described in the prompt."
    if "array" in q or "list" in q:
        return f"The concept here is ordered storage of multiple values. '{correct_answer}' matches the idea of grouping elements so they can be accessed by position."
    if "function" in q or "method" in q:
        return f"This checks whether you understand reusable blocks of logic. '{correct_answer}' is correct because it describes the role of a function or method."
    if "boolean" in correct or "integer" in correct or "string" in correct:
        return f"The question focuses on basic programming concepts and classifications. '{correct_answer}' is the answer that matches the formal concept used in programming."
    return f"The correct answer is '{correct_answer}' because it best matches the concept described in the question."


def _wrong_choice_feedback(user_answer: str, correct_answer: str) -> str:
    if not user_answer or user_answer == "No answer selected":
        return "You left this question unanswered, so the main goal is to compare the prompt carefully with the available choices."
    return f"Your choice '{user_answer}' does not fully match what the question is asking, while '{correct_answer}' directly matches the concept being tested."


def _build_review_item(mistake: ReviewMistake) -> dict:
    correct_answer = (
        mistake.options[mistake.correct_answer_index]
        if 0 <= mistake.correct_answer_index < len(mistake.options)
        else "Unknown"
    )
    user_answer = (
        mistake.options[mistake.user_answer_index]
        if 0 <= mistake.user_answer_index < len(mistake.options)
        else "No answer selected"
    )

    explanation = mistake.explanation or _concept_explanation(mistake.question, correct_answer)
    if mistake.topicTag:
        explanation = f"Topic: {mistake.topicTag}. {explanation}"

    next_step = _wrong_choice_feedback(user_answer, correct_answer)
    if mistake.hint:
        next_step = f"{next_step} Hint to remember: {mistake.hint}"

    return {
        "question": mistake.question,
        "your_answer": user_answer,
        "correct_answer": correct_answer,
        "explanation": explanation,
        "why_your_answer_was_wrong": next_step,
    }


def _build_follow_up_answer(user_question: str, lesson_title: str, wrong_answers: list[ReviewMistake]) -> str:
    lowered = user_question.lower()

    if "summary" in lowered or "overall" in lowered:
        return f"In {lesson_title}, the main pattern is to connect each question to the programming concept it tests. Focus on definitions, not on guessing from familiar words."
    if "study" in lowered or "improve" in lowered or "next time" in lowered:
        return "A strong strategy is: read the concept name in the question, eliminate answers that are just everyday words, and explain to yourself why the correct option fits before selecting it."
    if "why" in lowered or "explain" in lowered:
        return "The best way to understand these mistakes is to compare the exact wording of the question with the correct concept. Look at what the question defines, then choose the option that matches that definition precisely."

    if wrong_answers:
        first = _build_review_item(wrong_answers[0])
        return (
            f"Let's connect your question back to the quiz. For example, in '{first['question']}', "
            f"the correct answer was '{first['correct_answer']}' because {first['explanation'].lower()}"
        )

    return "Ask me about a specific wrong answer, and I will explain the concept step by step."


def _message_records(session_id: int) -> list[SimpleNamespace]:
    return [as_record(item) for item in _store().list_student_ai_messages(session_id)]


def _session_payload(session: dict) -> dict:
    messages = sorted(
        _store().list_student_ai_messages(session["id"]),
        key=lambda item: item.get("created_at") or datetime.utcnow(),
    )
    return {
        "session_id": session["id"],
        "mode": session["mode"],
        "course_id": session.get("course_id"),
        "lesson_id": session.get("lesson_id"),
        "attempt_id": session.get("attempt_id"),
        "messages": [
            {
                "id": item["id"],
                "role": item["role"],
                "content": item["content"],
                "created_at": item["created_at"].isoformat() if item.get("created_at") else None,
            }
            for item in messages
        ],
    }


def _load_owned_session(
    db: Session,
    session_id: int,
    current_user,
    expected_mode: str | None = None,
) -> dict:
    session = _store().get_student_ai_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Student AI session not found")
    if session["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot access another student's AI session")
    if expected_mode and session["mode"] != expected_mode:
        raise HTTPException(status_code=400, detail="Student AI session mode mismatch")
    return session


def _load_course_and_lesson(db: Session, course_id: int, lesson_id: int) -> tuple[dict, dict]:
    course = _store().get_course(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    lesson = _store().get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    if lesson["course_id"] != course["id"]:
        raise HTTPException(status_code=422, detail="Lesson does not belong to the selected course")

    return course, lesson


def _lesson_excerpt_payload(lesson: dict, message: str) -> list[str]:
    return select_relevant_chunks(
        lesson.get("content") or "",
        f"{lesson['title']} {message}",
        limit=3,
    )


def _attempt_has_snapshot(attempt: dict) -> bool:
    try:
        student_answers = json.loads(attempt.get("student_answers_json") or "[]")
        question_snapshot = json.loads(attempt.get("quiz_questions_snapshot_json") or "[]")
    except json.JSONDecodeError:
        return False
    return bool(student_answers) and bool(question_snapshot)


def _store_session_message(
    db: Session,
    session: dict,
    role: str,
    content: str,
) -> None:
    _store().add_student_ai_message(
        {
            "session_id": session["id"],
            "role": role,
            "content": content.strip(),
        },
        db=db,
    )


def _selected_question_indexes(explanation_items: list[dict]) -> list[int]:
    return [
        int(item["question_index"])
        for item in explanation_items
        if isinstance(item, dict) and isinstance(item.get("question_index"), int)
    ]


@router.post("/hint")
def request_hint(request: HintRequest, db: Session = Depends(database.get_db), current_user=Depends(dependencies.get_active_user)):
    if request.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot request hints for another user")
    time.sleep(1.5)

    config = _store().get_system_config()
    safety_enabled = config["ai_safety"] if config else True

    query = request.user_question.lower()
    context = request.context.lower()
    hint_response = ""

    if safety_enabled and ("hack" in query or "bypass" in query):
        hint_response = "[Blocked by AI Safety] I cannot provide direct answers or inappropriate content. Please try to solve the problem yourself!"
    elif "hint:" in context:
        hint_response = request.context.split("hint:", 1)[1].strip()
    elif "indentation" in context or "indentation" in query:
        hint_response = "For Python indentation, follow the left edge of each line. Indented lines belong to the block above them."
    elif "html" in context or "html" in query:
        hint_response = "For HTML, ask what the tag means structurally before thinking about how it looks."
    elif "css" in context or "css" in query or "layout" in context:
        hint_response = "For CSS, separate content, padding, border, margin, and layout. Visual layers make the rule easier to reason about."
    elif "server" in context or "api" in context or "request" in query:
        hint_response = "Trace the request-response loop: client sends data, server validates or computes, then the UI renders the response."
    elif "validation" in context or "validation" in query:
        hint_response = "Validation is a safety check before data is trusted. Client checks help users, server checks protect the system."
    elif "dictionary" in context or "key" in query:
        hint_response = "For dictionaries, identify the key first, then read or update the value stored under that key."
    elif "variable" in context or "variable" in query:
        hint_response = "A variable is a named place for a value. Check the value type before deciding what operation is valid."
    elif "array" in query or "list" in query:
        hint_response = "An array is a data structure consisting of a collection of elements. Think of it like a row of mailboxes."
    elif "loop" in query or "for" in query or "while" in query:
        hint_response = "Loops let you run the same block of code multiple times. Use a 'for' loop when you know how many times to repeat."
    elif "function" in query or "method" in query:
        hint_response = "A function is a reusable block of code that performs a specific task."
    else:
        hint_response = "A good strategy here is to break down the problem. What are the inputs, and what is the expected output?"

    _store().create_ai_log(
        {
            "user_id": request.user_id,
            "context": request.context,
            "question": request.user_question,
            "hint": hint_response,
            "timestamp": datetime.utcnow(),
        },
        db=db,
    )

    return {
        "hint": hint_response,
        "source": "mocked_safe_gateway" if safety_enabled else "mocked_llm_gateway",
    }


@router.post("/review-mistakes")
def review_mistakes(
    request: ReviewRequest,
    db: Session = Depends(database.get_db),
    current_user=Depends(dependencies.get_active_user),
):
    if request.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot review mistakes for another user")
    time.sleep(1.0)

    explanations = [_build_review_item(mistake) for mistake in request.wrong_answers]
    summary = (
        f"I reviewed {len(explanations)} incorrect answer(s) from {request.lesson_title}. "
        "Read each explanation, then ask follow-up questions if any step is still unclear."
    )

    _store().create_ai_log(
        {
            "user_id": request.user_id,
            "context": f"review:{request.lesson_title}",
            "question": "Generate explanations for incorrect quiz answers",
            "hint": summary,
            "timestamp": datetime.utcnow(),
        },
        db=db,
    )

    return {
        "summary": summary,
        "explanations": explanations,
    }


@router.post("/review-chat")
def review_chat(
    request: ReviewFollowUpRequest,
    db: Session = Depends(database.get_db),
    current_user=Depends(dependencies.get_active_user),
):
    if request.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot continue AI review for another user")
    time.sleep(0.8)

    response = _build_follow_up_answer(
        request.user_question,
        request.lesson_title,
        request.wrong_answers,
    )

    _store().create_ai_log(
        {
            "user_id": request.user_id,
            "context": f"review-chat:{request.lesson_title}",
            "question": request.user_question,
            "hint": response,
            "timestamp": datetime.utcnow(),
        },
        db=db,
    )

    return {"answer": response}


@router.post("/open-question/sessions")
def create_open_question_session(
    payload: OpenQuestionSessionCreate,
    db: Session = Depends(database.get_db),
    current_user = Depends(dependencies.get_active_student),
):
    course, lesson = _load_course_and_lesson(db, payload.course_id, payload.lesson_id)

    session = _store().create_student_ai_session(
        {
            "user_id": current_user.id,
            "mode": "open_question",
            "course_id": course["id"],
            "lesson_id": lesson["id"],
        },
        db=db,
    )

    response = {
        **_session_payload(session),
        "course_title": course["title"],
        "lesson_title": lesson["title"],
        "lesson_excerpts": _lesson_excerpt_payload(lesson, payload.message or lesson["title"]),
    }

    if payload.message and payload.message.strip():
        messages = build_open_question_prompt(
            as_record(course),
            as_record(lesson),
            response["lesson_excerpts"],
            recent_session_messages(SimpleNamespace(messages=[])),
            payload.message.strip(),
            student_level=_student_level(current_user),
        )
        try:
            ai_answer = chat_completion(messages)
        except StudentAIConfigurationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except StudentAIProviderError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        _store_session_message(db, session, "user", payload.message)
        _store_session_message(db, session, "assistant", ai_answer)
        response = {
            **_session_payload(session),
            "course_title": course["title"],
            "lesson_title": lesson["title"],
            "lesson_excerpts": response["lesson_excerpts"],
            "answer": ai_answer,
        }

    return response


@router.post("/open-question/sessions/{session_id}/message")
def send_open_question_message(
    session_id: int,
    payload: StudentAIMessageCreate,
    db: Session = Depends(database.get_db),
    current_user = Depends(dependencies.get_active_student),
):
    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    session = _load_owned_session(db, session_id, current_user, expected_mode="open_question")
    course, lesson = _load_course_and_lesson(db, session["course_id"], session["lesson_id"])
    lesson_chunks = _lesson_excerpt_payload(lesson, payload.message)
    messages = build_open_question_prompt(
        as_record(course),
        as_record(lesson),
        lesson_chunks,
        recent_session_messages(SimpleNamespace(messages=_message_records(session["id"]))),
        payload.message.strip(),
        student_level=_student_level(current_user),
    )
    try:
        ai_answer = chat_completion(messages)
    except StudentAIConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except StudentAIProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    _store_session_message(db, session, "user", payload.message)
    _store_session_message(db, session, "assistant", ai_answer)

    return {
        **_session_payload(session),
        "course_title": course["title"],
        "lesson_title": lesson["title"],
        "lesson_excerpts": lesson_chunks,
        "answer": ai_answer,
    }


@router.get("/sessions/{session_id}")
def get_student_ai_session(
    session_id: int,
    db: Session = Depends(database.get_db),
    current_user = Depends(dependencies.get_active_student),
):
    session = _load_owned_session(db, session_id, current_user)
    payload = _session_payload(session)

    if session["mode"] == "quiz_explanation" and session.get("attempt_id"):
        attempt = _store().get_attempt(session["attempt_id"])
        if attempt:
            quiz = _store().get_quiz(attempt["quiz_id"])
            lesson = _store().get_lesson(quiz["lesson_id"]) if quiz else None
            if lesson:
                explanation_items = build_attempt_explanations(as_record(attempt), as_record(lesson))
                payload["summary"] = build_review_summary(as_record(lesson), explanation_items)
                payload["explanations"] = explanation_items

    return payload


@router.post("/quiz-explanation/sessions")
def create_quiz_explanation_session(
    payload: QuizExplanationSessionCreate,
    db: Session = Depends(database.get_db),
    current_user = Depends(dependencies.get_active_student),
):
    attempt = _store().get_attempt(payload.attempt_id)
    if not attempt:
        raise HTTPException(status_code=404, detail="Quiz attempt not found")
    if attempt["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot access another student's quiz attempt")
    if not _attempt_has_snapshot(attempt):
        raise HTTPException(status_code=422, detail="Quiz attempt does not contain answer details for AI explanation")

    quiz = _store().get_quiz(attempt["quiz_id"])
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    lesson = _store().get_lesson(quiz["lesson_id"])
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    course = _store().get_course(lesson["course_id"])
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    explanation_items = build_attempt_explanations(as_record(attempt), as_record(lesson), question_index=payload.question_index)
    if not explanation_items:
        raise HTTPException(status_code=422, detail="No incorrect answers were found for the selected quiz review scope")
    summary = build_review_summary(as_record(lesson), explanation_items)

    session = _store().create_student_ai_session(
        {
            "user_id": current_user.id,
            "mode": "quiz_explanation",
            "course_id": course["id"],
            "lesson_id": lesson["id"],
            "attempt_id": attempt["id"],
        },
        db=db,
    )

    response = {
        **_session_payload(session),
        "course_title": course["title"],
        "lesson_title": lesson["title"],
        "selected_question_indexes": _selected_question_indexes(explanation_items),
        "summary": summary,
        "explanations": explanation_items,
    }

    if payload.message and payload.message.strip():
        messages = build_quiz_follow_up_prompt(
            as_record(course),
            as_record(lesson),
            as_record(attempt),
            explanation_items,
            recent_session_messages(SimpleNamespace(messages=[])),
            payload.message.strip(),
            student_level=_student_level(current_user),
        )
        try:
            ai_answer = chat_completion(messages)
        except StudentAIConfigurationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except StudentAIProviderError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        _store_session_message(db, session, "user", payload.message)
        _store_session_message(db, session, "assistant", ai_answer)
        response["answer"] = ai_answer
        response["messages"] = _session_payload(session)["messages"]

    return response


@router.post("/quiz-explanation/sessions/{session_id}/message")
def send_quiz_explanation_message(
    session_id: int,
    payload: StudentAIMessageCreate,
    db: Session = Depends(database.get_db),
    current_user = Depends(dependencies.get_active_student),
):
    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    session = _load_owned_session(db, session_id, current_user, expected_mode="quiz_explanation")
    attempt = _store().get_attempt(session["attempt_id"])
    if not attempt:
        raise HTTPException(status_code=404, detail="Quiz attempt not found")

    quiz = _store().get_quiz(attempt["quiz_id"])
    lesson = _store().get_lesson(session["lesson_id"])
    course = _store().get_course(session["course_id"])
    if not quiz or not lesson or not course:
        raise HTTPException(status_code=404, detail="Related lesson context was not found")

    explanation_items = build_attempt_explanations(as_record(attempt), as_record(lesson))
    if not explanation_items:
        raise HTTPException(status_code=422, detail="No incorrect answers were found for this completed quiz attempt")
    messages = build_quiz_follow_up_prompt(
        as_record(course),
        as_record(lesson),
        as_record(attempt),
        explanation_items,
        recent_session_messages(SimpleNamespace(messages=_message_records(session["id"]))),
        payload.message.strip(),
        student_level=_student_level(current_user),
    )
    try:
        ai_answer = chat_completion(messages)
    except StudentAIConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except StudentAIProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    _store_session_message(db, session, "user", payload.message)
    _store_session_message(db, session, "assistant", ai_answer)

    return {
        **_session_payload(session),
        "course_title": course["title"],
        "lesson_title": lesson["title"],
        "selected_question_indexes": _selected_question_indexes(explanation_items),
        "summary": build_review_summary(as_record(lesson), explanation_items),
        "explanations": explanation_items,
        "answer": ai_answer,
    }
