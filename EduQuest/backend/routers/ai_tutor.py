from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
import time
import models, database, dependencies

router = APIRouter()

class HintRequest(BaseModel):
    user_id: int
    context: str # e.g. "Question 2 on arrays"
    user_question: str


class ReviewMistake(BaseModel):
    question: str
    options: list[str]
    user_answer_index: int
    correct_answer_index: int


class ReviewRequest(BaseModel):
    user_id: int
    lesson_title: str
    wrong_answers: list[ReviewMistake]


class ReviewFollowUpRequest(BaseModel):
    user_id: int
    lesson_title: str
    wrong_answers: list[ReviewMistake]
    user_question: str


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

    return {
        "question": mistake.question,
        "your_answer": user_answer,
        "correct_answer": correct_answer,
        "explanation": _concept_explanation(mistake.question, correct_answer),
        "why_your_answer_was_wrong": _wrong_choice_feedback(user_answer, correct_answer),
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

@router.post("/hint")
def request_hint(request: HintRequest, db: Session = Depends(database.get_db), current_user: models.User = Depends(dependencies.get_active_user)):
    if request.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot request hints for another user")
    # Simulator delay to represent LLM latency
    time.sleep(1.5)

    config = db.query(models.SystemConfig).first()
    safety_enabled = config.ai_safety if config else True
    
    query = request.user_question.lower()
    hint_response = ""
    
    if safety_enabled and ("hack" in query or "bypass" in query or "answer" in query):
        hint_response = "[Blocked by AI Safety] I cannot provide direct answers or inappropriate content. Please try to solve the problem yourself!"
    elif "array" in query or "list" in query:
        hint_response = "An array is a data structure consisting of a collection of elements. Think of it like a row of mailboxes."
    elif "loop" in query or "for" in query or "while" in query:
        hint_response = "Loops let you run the same block of code multiple times. Use a 'for' loop when you know how many times to repeat."
    elif "function" in query or "method" in query:
        hint_response = "A function is a reusable block of code that performs a specific task."
    else:
        hint_response = "A good strategy here is to break down the problem. What are the inputs, and what is the expected output?"

    # Log to DB
    new_log = models.AILog(
        user_id=request.user_id,
        context=request.context,
        question=request.user_question,
        hint=hint_response,
        timestamp=datetime.utcnow()
    )
    db.add(new_log)
    db.commit()
    
    return {
        "hint": hint_response,
        "source": "mocked_safe_gateway" if safety_enabled else "mocked_llm_gateway"
    }


@router.post("/review-mistakes")
def review_mistakes(
    request: ReviewRequest,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(dependencies.get_active_user),
):
    if request.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot review mistakes for another user")
    time.sleep(1.0)

    explanations = [_build_review_item(mistake) for mistake in request.wrong_answers]
    summary = (
        f"I reviewed {len(explanations)} incorrect answer(s) from {request.lesson_title}. "
        "Read each explanation, then ask follow-up questions if any step is still unclear."
    )

    db.add(
        models.AILog(
            user_id=request.user_id,
            context=f"review:{request.lesson_title}",
            question="Generate explanations for incorrect quiz answers",
            hint=summary,
            timestamp=datetime.utcnow(),
        )
    )
    db.commit()

    return {
        "summary": summary,
        "explanations": explanations,
    }


@router.post("/review-chat")
def review_chat(
    request: ReviewFollowUpRequest,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(dependencies.get_active_user),
):
    if request.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot continue AI review for another user")
    time.sleep(0.8)

    response = _build_follow_up_answer(
        request.user_question,
        request.lesson_title,
        request.wrong_answers,
    )

    db.add(
        models.AILog(
            user_id=request.user_id,
            context=f"review-chat:{request.lesson_title}",
            question=request.user_question,
            hint=response,
            timestamp=datetime.utcnow(),
        )
    )
    db.commit()

    return {"answer": response}
