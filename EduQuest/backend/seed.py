import argparse
from datetime import datetime, timedelta
import json

from database import SessionLocal, engine
import models


def _lesson_content(
    intro: str,
    objectives: list[str],
    key_concepts: list[str],
    explanation: str,
    example: str,
    common_mistakes: list[str],
    practice: str,
    recap: str,
) -> str:
    plain_text = "\n\n".join(
        [
            f"Introduction\n{intro}",
            "Learning objectives\n" + "\n".join(f"- {item}" for item in objectives),
            "Key concepts\n" + "\n".join(f"- {item}" for item in key_concepts),
            f"Explanation\n{explanation}",
            f"Concrete example\n{example}",
            "Common mistakes\n" + "\n".join(f"- {item}" for item in common_mistakes),
            f"Mini practice task\n{practice}",
            f"Recap\n{recap}",
        ]
    )
    return json.dumps(
        {
            "version": 1,
            "hook": intro,
            "objectives": objectives,
            "concepts": _concept_cards(key_concepts),
            "explanation": explanation,
            "example": {
                "title": "Worked example",
                "kind": _example_kind(example),
                "body": example,
            },
            "visual": _visual_payload(intro, explanation, example),
            "visualBlocks": _visual_blocks(intro, explanation, example),
            "didYouKnow": _did_you_know_payload(intro, explanation, example),
            "flashcards": _flashcards_payload(key_concepts),
            "mistakes": common_mistakes,
            "practice": _practice_payload(key_concepts, practice),
            "recap": recap,
            "finalChallenge": _final_challenge_payload(practice, recap),
            "legacyText": plain_text,
        }
    )


def _concept_cards(key_concepts: list[str]) -> list[dict]:
    cards = []
    for index, concept in enumerate(key_concepts, start=1):
        title, _, body = concept.partition(" is ")
        if body:
            body = f"is {body}"
        else:
            title = f"Concept {index}"
            body = concept
        cards.append({"title": title.strip("."), "body": body.strip()})
    return cards


def _example_kind(example: str) -> str:
    code_signals = ["\n", "=", "<", ">", "def ", "for ", "if ", "{", "}"]
    return "code" if any(signal in example for signal in code_signals) else "scenario"


def _visual_payload(intro: str, explanation: str, example: str) -> dict:
    source = f"{intro} {explanation} {example}".lower()
    if "html" in source or "<h1>" in source or "<p>" in source:
        return {
            "kind": "html-tree",
            "title": "Visual model: HTML tree",
            "body": "Imagine the page as a tree: headings, paragraphs, links, and lists each become visible branches of meaning.",
        }
    if "css" in source or "padding" in source or "layout" in source:
        return {
            "kind": "box-model",
            "title": "Visual model: CSS box model",
            "body": "Picture every element as content wrapped by padding, border, and margin. Layout becomes easier when those layers are visible.",
        }
    if "request" in source or "server" in source or "api" in source or "json" in source:
        return {
            "kind": "client-server",
            "title": "Visual model: client-server loop",
            "body": "The mobile app sends a request, the backend checks data, and the response returns structured information for the UI.",
        }
    if "algorithm" in source or "step" in source:
        return {
            "kind": "algorithm-steps",
            "title": "Visual model: step-by-step path",
            "body": "Each instruction is a checkpoint. The result is reliable only when the checkpoints are ordered and complete.",
        }
    if "traceback" in source or "error" in source or "debug" in source:
        return {
            "kind": "debug-trace",
            "title": "Visual model: trace the error",
            "body": "Start from the visible symptom, read the message, inspect the named line, then test one focused fix.",
        }
    if "loop" in source or "list" in source:
        return {
            "kind": "loop-flow",
            "title": "Visual model: repeat over items",
            "body": "A loop moves across a collection one item at a time, applying the same action until the collection is finished.",
        }
    return {
        "kind": "concept-map",
        "title": "Visual model: concept map",
        "body": "Connect the concept, example, mistake, and practice task so the topic becomes easier to remember.",
    }


def _visual_blocks(intro: str, explanation: str, example: str) -> list[dict]:
    source = f"{intro} {explanation} {example}".lower()
    blocks = []

    if "html" in source or "<h1>" in source or "<p>" in source:
        blocks.append(
            {
                "kind": "html-tree",
                "title": "HTML tree",
                "body": "Document nodes nest like a tree: html contains body, body contains headings, paragraphs, links, and form fields.",
                "steps": ["html", "body", "section", "h1 / p / form"],
            }
        )
    if "css" in source or "padding" in source or "layout" in source:
        blocks.append(
            {
                "kind": "box-model",
                "title": "CSS box model",
                "body": "Every visual element can be inspected as content, padding, border, and margin. This keeps spacing decisions predictable.",
                "steps": ["content", "padding", "border", "margin"],
            }
        )
    if "request" in source or "server" in source or "api" in source or "json" in source:
        blocks.append(
            {
                "kind": "client-server",
                "title": "Client-server flow",
                "body": "A screen requests data, the API validates the request, the database answers, and JSON returns to the frontend.",
                "steps": ["client", "request", "backend", "database", "response"],
            }
        )
    if "algorithm" in source or "step" in source:
        blocks.append(
            {
                "kind": "algorithm-steps",
                "title": "Algorithm checkpoints",
                "body": "Reliable algorithms move through clear checkpoints, so missing or swapped steps are easier to spot.",
                "steps": ["input", "ordered steps", "edge case", "output"],
            }
        )
    if "traceback" in source or "error" in source or "debug" in source:
        blocks.append(
            {
                "kind": "debug-trace",
                "title": "Debug trace",
                "body": "Read the symptom, locate the line, check one assumption, apply one fix, and retest.",
                "steps": ["symptom", "message", "line", "fix", "retest"],
            }
        )
    if "python" in source or "print(" in source or "def " in source or "score =" in source:
        blocks.append(
            {
                "kind": "python-output",
                "title": "Code and output",
                "body": "Predict the value of each variable before running the next line. This habit makes quiz code-reading questions easier.",
                "steps": ["read line", "update value", "predict output"],
            }
        )
    if "form" in source or "validation" in source:
        blocks.append(
            {
                "kind": "forms-validation",
                "title": "Form validation path",
                "body": "A good form checks required fields, validates format, explains errors, and only then submits data.",
                "steps": ["input", "validate", "feedback", "submit"],
            }
        )
    if not blocks:
        blocks.append(
            {
                "kind": "concept-map",
                "title": "Concept map",
                "body": "Connect definition, example, mistake, practice, and quiz. The same concept appears in each step.",
                "steps": ["concept", "example", "practice", "quiz"],
            }
        )

    blocks.append(
        {
            "kind": "learning-loop",
            "title": "Study loop",
            "body": "Read the idea, test it locally, use feedback, then submit a saved quiz attempt for progress.",
            "steps": ["learn", "practice", "feedback", "quiz"],
        }
    )
    return blocks[:3]


def _did_you_know_payload(intro: str, explanation: str, example: str) -> dict:
    source = f"{intro} {explanation} {example}".lower()
    if "debug" in source or "error" in source or "traceback" in source:
        body = "Professional developers spend a large part of their time reading symptoms and testing small fixes, not writing perfect code first."
    elif "html" in source or "css" in source or "form" in source:
        body = "Clear structure and validation improve learning because students can scan, predict, and recover from mistakes faster."
    elif "python" in source or "print(" in source or "def " in source:
        body = "Code-reading practice is one of the fastest ways to build confidence before writing larger programs."
    elif "algorithm" in source or "loop" in source or "step" in source:
        body = "Algorithms are easier to debug when every step has a visible input and output."
    else:
        body = "Memory improves when a learner sees the same idea as a definition, example, practice task, and feedback."
    return {
        "title": "Did you know?",
        "body": body,
    }


def _flashcards_payload(key_concepts: list[str]) -> list[dict]:
    cards = []
    for concept in key_concepts[:5]:
        title, separator, body = concept.partition(" is ")
        if not separator:
            title, separator, body = concept.partition(" are ")
            if separator:
                body = f"are {body}"
        else:
            body = f"is {body}"
        if not separator:
            title = concept.split(".")[0]
            body = concept
        cards.append(
            {
                "term": title.strip(" ."),
                "definition": body.strip(" ."),
            }
        )
    return cards


def _final_challenge_payload(practice: str, recap: str) -> dict:
    return {
        "title": "Final challenge",
        "body": practice,
        "successCriteria": [
            "Use the lesson vocabulary correctly.",
            "Explain one reason for your choice.",
            "Connect your answer to the quiz review feedback.",
        ],
        "recapPrompt": recap,
    }


def _practice_payload(key_concepts: list[str], practice: str) -> dict:
    correct = key_concepts[0] if key_concepts else "Use the lesson concept in a concrete situation."
    distractor_one = key_concepts[1] if len(key_concepts) > 1 else "Ignore the lesson goal and guess quickly."
    distractor_two = key_concepts[2] if len(key_concepts) > 2 else "Focus only on visual style without checking behavior."
    return {
        "type": "mcq",
        "prompt": practice,
        "options": [
            correct,
            distractor_one,
            distractor_two,
            "Skip the reasoning and choose a random answer.",
        ],
        "answer": 0,
        "explanation": f"The strongest answer is: {correct} It connects the practice task to the main idea of the lesson.",
    }


def _question(
    q: str,
    options: list[str],
    answer: int,
    explanation: str,
    difficulty: str,
    topic_tag: str,
    hint: str,
) -> dict:
    return {
        "type": "mcq",
        "q": q,
        "question": q,
        "options": options,
        "answer": answer,
        "correctIndex": answer,
        "explanation": explanation,
        "difficulty": difficulty,
        "topicTag": topic_tag,
        "hint": hint,
    }


def _questions(items: list[tuple]) -> list[dict]:
    return [_question(*item) for item in items]


COURSE_BLUEPRINTS = [
    {
        "title": "Introduction to Computer Science",
        "description": (
            "Category: Computer Science Foundations. Level: Beginner. "
            "Learn how programs store data, make decisions, use functions, follow algorithms, and handle errors."
        ),
        "lessons": [
            (
                "Variables and Data Types",
                _lesson_content(
                    "Programs become useful when they can remember information. A variable is a name connected to a value, and a data type explains what kind of value it is.",
                    [
                        "Define variables in everyday language.",
                        "Distinguish numbers, strings, booleans, and lists.",
                        "Choose a sensible data type for a learning-app feature.",
                    ],
                    [
                        "Variable names should describe the stored value.",
                        "Types control which operations are valid.",
                        "Booleans are ideal for yes-or-no states.",
                    ],
                    "A quiz app may store score as a number, studentName as text, isPassed as true or false, and selectedAnswers as a list. The type matters because adding two numbers is different from joining two strings. Clear variable names also make code easier to review during a defense.",
                    "score = 85 stores a number. name = \"Demo Student\" stores text. isPassed = score >= 70 stores a boolean result that can control the next screen.",
                    [
                        "Using vague names such as x when the meaning is known.",
                        "Treating text that looks like a number as if it were already numeric.",
                        "Using strings such as \"true\" when a boolean true is needed.",
                    ],
                    "Write variable names and types for XP, lesson title, completed status, and selected quiz answers.",
                    "Variables name data. Data types make behavior predictable and help prevent invalid operations.",
                ),
            ),
            (
                "Control Flow and Decisions",
                _lesson_content(
                    "Control flow is the order in which code runs. Decisions and loops let a program react to different learner actions instead of always doing the same thing.",
                    [
                        "Explain how if and else choose paths.",
                        "Identify when a loop is useful.",
                        "Trace a short decision-based program.",
                    ],
                    [
                        "A condition is an expression that becomes true or false.",
                        "A branch is a path selected by a condition.",
                        "A loop repeats a block for several values or while a condition remains true.",
                    ],
                    "An if statement checks a condition and runs a block only when the condition is true. An else block handles the alternative. Loops are useful when the same action must happen for every quiz answer, every lesson, or every attempt in a history list.",
                    "If score >= 70, show 'Passed'. Otherwise show 'Try again'. A loop can repeat this check for every attempt in a student's progress history.",
                    [
                        "Writing a loop condition that never becomes false.",
                        "Forgetting the else case when the learner does not meet the condition.",
                        "Using many separate if statements when one loop would be clearer.",
                    ],
                    "Design a rule that awards a badge when a learner completes five lessons, otherwise shows how many lessons remain.",
                    "Decisions choose a path. Loops repeat work. Together they make programs adaptive.",
                ),
            ),
            (
                "Functions and Problem Decomposition",
                _lesson_content(
                    "Large problems become manageable when they are split into smaller named actions. A function is a reusable action with a clear purpose.",
                    [
                        "Describe what a function does.",
                        "Identify inputs, processing, and output.",
                        "Break a quiz feature into smaller functions.",
                    ],
                    [
                        "A function name should describe the action.",
                        "Parameters carry inputs into a function.",
                        "A return value sends the result back to the caller.",
                    ],
                    "Instead of writing scoring logic in several screens, an app can use a function such as calculateScore(answers). This keeps behavior consistent and easier to test. Good decomposition also helps explain system design clearly: score calculation, feedback creation, and XP awarding can be separate responsibilities.",
                    "calculatePercent(correct, total) can return correct / total * 100. The dashboard, quiz result screen, and analytics screen can all reuse that calculation.",
                    [
                        "Creating a function that tries to do too many unrelated jobs.",
                        "Using unclear parameter names.",
                        "Printing a result when another part of the program needs to reuse it.",
                    ],
                    "Break 'submit a quiz' into three functions: one for checking answers, one for calculating XP, and one for building feedback.",
                    "Functions reduce repetition. Decomposition turns a complex feature into understandable steps.",
                ),
            ),
            (
                "Algorithms and Step-by-Step Thinking",
                _lesson_content(
                    "An algorithm is a clear sequence of steps for solving a problem. Even a simple quiz checker is an algorithm.",
                    [
                        "Define an algorithm as a repeatable process.",
                        "Order steps correctly for a simple task.",
                        "Recognize why precise instructions matter.",
                    ],
                    [
                        "Input is information the algorithm receives.",
                        "Processing is the ordered work done on the input.",
                        "Output is the result produced at the end.",
                    ],
                    "Computers follow instructions exactly, so algorithm steps must be complete and ordered. For a quiz, the algorithm receives answers, compares each one with the correct index, counts correct answers, calculates a score, and returns feedback. Edge cases such as zero questions should be handled before calculation.",
                    "To find the highest score, start with the first score as best, compare every other score, replace best when a higher score appears, then return best.",
                    [
                        "Skipping edge cases such as an empty list.",
                        "Using data before it has been loaded.",
                        "Describing a goal but not the exact steps.",
                    ],
                    "Write a five-step algorithm for recommending the next lesson after a student completes a quiz.",
                    "Algorithms convert goals into repeatable steps that can be implemented, tested, and explained.",
                ),
            ),
            (
                "Debugging and Error Handling",
                _lesson_content(
                    "Debugging is the process of finding and fixing mistakes. Error handling is how a program responds when something goes wrong.",
                    [
                        "Separate syntax, runtime, and logic errors.",
                        "Use small checks to locate a problem.",
                        "Explain why friendly error messages matter.",
                    ],
                    [
                        "A syntax error means code cannot be parsed.",
                        "A runtime error happens while code is running.",
                        "A logic error means code runs but produces the wrong result.",
                    ],
                    "A good debugging process starts by reproducing the problem, reading the error message, and checking one assumption at a time. In a learning app, error handling should prevent crashes and explain what the learner can do next. This keeps the educational flow stable.",
                    "If a quiz has zero questions, the backend should return a clear message instead of dividing by zero. The UI should explain that quiz content is unavailable.",
                    [
                        "Changing many things at once and losing track of the real fix.",
                        "Ignoring error messages.",
                        "Showing technical stack traces to students.",
                    ],
                    "Imagine a lesson opens but the quiz is missing. Write what the app should log and what the student should see.",
                    "Debugging is systematic investigation. Error handling protects the learning experience.",
                ),
            ),
        ],
    },
    {
        "title": "Python Programming Basics",
        "description": (
            "Category: Programming. Level: Beginner to early intermediate. "
            "Practice Python syntax, loops, functions, dictionaries, and debugging through small code examples."
        ),
        "lessons": [
            (
                "Python Syntax and Indentation",
                _lesson_content(
                    "Python is designed to be readable. Its most visible rule is indentation: spaces at the start of a line show which statements belong together.",
                    [
                        "Recognize Python statements and expressions.",
                        "Explain why indentation is required.",
                        "Read a short Python block accurately.",
                    ],
                    [
                        "A statement is an instruction Python executes.",
                        "An expression produces a value.",
                        "A block is an indented group of statements.",
                    ],
                    "In many languages braces show structure. In Python, indentation does that job. Lines inside an if statement, loop, or function must be indented consistently. This makes beginner code easier to scan but also means spacing mistakes can change behavior or stop the program.",
                    "if score >= 70:\n    print('Passed')\nprint('Done')\nThe first print belongs to the if block. The second print runs after the decision.",
                    [
                        "Mixing tabs and spaces.",
                        "Indenting a line that should run outside the block.",
                        "Forgetting the colon after if, for, while, or def.",
                    ],
                    "Write a tiny if statement that prints 'Review needed' when score is below 70.",
                    "Python syntax is compact, but indentation carries meaning. Read blocks by watching their left edge.",
                ),
            ),
            (
                "Lists and Loops",
                _lesson_content(
                    "A list stores multiple values in order. A loop lets you process those values one by one without copying the same code.",
                    [
                        "Create and read a Python list.",
                        "Use a loop to visit every item.",
                        "Choose between direct item loops and index-based loops.",
                    ],
                    [
                        "A list is an ordered collection such as scores = [80, 95, 70].",
                        "An index is a numeric position starting at 0.",
                        "A for loop repeats once for each item.",
                    ],
                    "Lists are useful when a program handles a group: quiz scores, lesson titles, or selected answers. A for loop keeps code short because the same action can be repeated for every item. If position does not matter, looping directly over items is usually clearer.",
                    "scores = [80, 95, 70]\nfor score in scores:\n    print(score)\nThis prints each score in the same order as the list.",
                    [
                        "Trying to access index 3 in a three-item list.",
                        "Changing a list while looping without planning.",
                        "Using an index loop when the item value is enough.",
                    ],
                    "Create a list of three quiz scores and write a loop that prints only scores greater than 70.",
                    "Lists group related values. Loops make repeated processing clear and concise.",
                ),
            ),
            (
                "Functions and Parameters",
                _lesson_content(
                    "Functions in Python let you name reusable behavior. Parameters let the same function work with different inputs.",
                    [
                        "Write a simple function definition.",
                        "Pass values through parameters.",
                        "Return a result instead of only printing.",
                    ],
                    [
                        "def defines a function.",
                        "A parameter is a variable listed in the function header.",
                        "An argument is the actual value passed during a call.",
                    ],
                    "A function should have one clear purpose. If a quiz app needs to calculate accuracy many times, a function prevents copy-paste logic. Returning a result is often more flexible than printing because another part of the program can use the value.",
                    "def accuracy(correct, total):\n    return correct / total\nresult = accuracy(6, 7)",
                    [
                        "Forgetting parentheses when calling a function.",
                        "Using a variable inside the function before it is passed in.",
                        "Printing a result when the caller needs to reuse it.",
                    ],
                    "Write a function named passed(score) that returns True when score is at least 70.",
                    "Functions make Python programs easier to reuse, test, and explain. Parameters carry input into the function.",
                ),
            ),
            (
                "Dictionaries and Data Structures",
                _lesson_content(
                    "A dictionary stores values by key. It is useful when each piece of data has a name, such as a user profile.",
                    [
                        "Explain key-value storage.",
                        "Read and update dictionary values.",
                        "Choose dictionaries when named fields matter.",
                    ],
                    [
                        "A key is the label used to find a value.",
                        "A value is the data stored under the key.",
                        "A data structure organizes data for access and updates.",
                    ],
                    "Lists are best for ordered collections. Dictionaries are best when values have named fields. For example, a learner can have name, xp, level, and role. Accessing learner['xp'] is clearer than remembering which list position stores XP.",
                    "learner = {'name': 'Demo Student', 'xp': 1450}\nlearner['xp'] = learner['xp'] + 100",
                    [
                        "Using a key that does not exist.",
                        "Confusing dictionary braces with list brackets.",
                        "Storing unrelated data without clear field names.",
                    ],
                    "Create a dictionary for a lesson with title, completed, and quizScore fields.",
                    "Dictionaries make structured data readable. They are ideal for profiles, quiz records, and API-style objects.",
                ),
            ),
            (
                "Reading Errors and Debugging",
                _lesson_content(
                    "Python error messages are learning tools. They usually tell you the error type, the line, and a clue about what went wrong.",
                    [
                        "Read the main parts of a traceback.",
                        "Recognize common Python errors.",
                        "Use small tests to confirm a fix.",
                    ],
                    [
                        "A traceback shows where Python failed.",
                        "NameError means a name was not defined.",
                        "TypeError means an operation used an incompatible type.",
                    ],
                    "Start from the last line of the traceback, then inspect the line number mentioned above it. After making a fix, run a small example that proves the specific problem is solved. This habit prevents guessing and supports reliable development.",
                    "If total is 0, correct / total raises ZeroDivisionError. A safe function should check total before dividing.",
                    [
                        "Reading only the first line of a traceback.",
                        "Assuming the error is in a library instead of your input.",
                        "Fixing symptoms without checking the original assumption.",
                    ],
                    "Write a guard for accuracy(correct, total) that returns 0 when total equals 0.",
                    "Tracebacks are maps, not failure labels. Use them to find the smallest reliable fix.",
                ),
            ),
        ],
    },
    {
        "title": "Web Development Fundamentals",
        "description": (
            "Category: Web Development. Level: Beginner. "
            "Build a foundation in HTML structure, CSS layout, JavaScript behavior, APIs, and validation."
        ),
        "lessons": [
            (
                "HTML Structure",
                _lesson_content(
                    "HTML gives a web page its structure. It tells the browser what each part of the content means.",
                    [
                        "Identify common HTML elements.",
                        "Explain headings, paragraphs, links, and attributes.",
                        "Build a simple semantic page outline.",
                    ],
                    [
                        "An element is a tag with content and a closing tag when needed.",
                        "Semantic HTML uses tags that describe meaning.",
                        "An attribute adds extra information such as href or alt.",
                    ],
                    "A browser can display plain text, but HTML makes the text meaningful. A heading marks the main topic, a paragraph holds readable content, and a link connects the page to another resource. Semantic tags improve accessibility and maintenance.",
                    "<h1>Python Basics</h1>\n<p>Learn syntax, loops, and functions.</p>\n<a href='/quiz'>Take quiz</a>",
                    [
                        "Using headings only for visual size.",
                        "Forgetting closing tags.",
                        "Using non-descriptive link text such as 'click here'.",
                    ],
                    "Sketch the HTML structure for a course page with a title, lesson list, and quiz button.",
                    "HTML is the content layer. Good structure helps users, browsers, and assistive tools understand the page.",
                ),
            ),
            (
                "CSS Styling and Layout",
                _lesson_content(
                    "CSS controls how HTML looks. It defines color, spacing, typography, and layout.",
                    [
                        "Connect CSS rules to HTML elements.",
                        "Explain the box model.",
                        "Choose layout tools for simple screens.",
                    ],
                    [
                        "A selector chooses which elements to style.",
                        "The box model includes content, padding, border, and margin.",
                        "Flexbox and grid arrange elements on the page.",
                    ],
                    "CSS separates presentation from structure. Instead of changing every heading manually, a single rule can style all course titles. Layout rules help cards, buttons, and progress indicators adapt to different screen sizes.",
                    ".course-card { padding: 16px; border-radius: 8px; display: flex; gap: 12px; }",
                    [
                        "Using margin when padding is needed inside a component.",
                        "Writing styles that only work on one screen width.",
                        "Relying only on color to communicate status.",
                    ],
                    "Describe which CSS properties would make quiz options readable on a phone.",
                    "CSS is the visual layer. Good layout supports scanning, tapping, and reading.",
                ),
            ),
            (
                "JavaScript Basics",
                _lesson_content(
                    "JavaScript adds behavior to web pages. It can respond to clicks, update text, and prepare data for an API request.",
                    [
                        "Describe variables, functions, and events in JavaScript.",
                        "Read a simple event handler.",
                        "Explain how state changes affect the UI.",
                    ],
                    [
                        "An event is a user or browser action such as a click.",
                        "The DOM is the page structure JavaScript can read or update.",
                        "State is the current data that drives what the user sees.",
                    ],
                    "A quiz screen uses behavior: when the learner taps an option, the app records the answer, moves to the next question, and updates progress. JavaScript is one common language for this kind of browser interaction.",
                    "button.addEventListener('click', () => {\n  score = score + 1;\n});",
                    [
                        "Changing the display but forgetting to update stored state.",
                        "Running code before the page element exists.",
                        "Putting too much logic directly inside a click handler.",
                    ],
                    "Write pseudocode for what should happen when a student selects a quiz answer.",
                    "JavaScript is the behavior layer. It connects user actions to visible interface changes.",
                ),
            ),
            (
                "Client-Server Communication",
                _lesson_content(
                    "Most learning apps use a client and a server. The client shows the interface; the server stores data and applies shared rules.",
                    [
                        "Explain request and response flow.",
                        "Recognize JSON as a common data format.",
                        "Describe why stable API contracts matter.",
                    ],
                    [
                        "A client is the app or browser making a request.",
                        "A server receives the request and returns data.",
                        "JSON is structured text for API data.",
                    ],
                    "When a learner opens a course, the client asks the server for course data. The server reads from the database and returns JSON. If field names change unexpectedly, the client may fail to display content.",
                    "GET /api/courses can return [{\"title\":\"Python Programming Basics\",\"lesson_count\":5}].",
                    [
                        "Assuming the client can trust all user input.",
                        "Changing API response fields without updating the frontend.",
                        "Ignoring failed requests.",
                    ],
                    "List the data a quiz submit request should send and the data the response should return.",
                    "Client-server communication lets the app persist learning data and keep business rules in one reliable place.",
                ),
            ),
            (
                "Forms and Validation",
                _lesson_content(
                    "Forms collect user input. Validation checks whether that input is complete, safe, and useful.",
                    [
                        "Identify common form fields.",
                        "Explain client-side and server-side validation.",
                        "Write clear validation feedback.",
                    ],
                    [
                        "A required field must be provided.",
                        "Client validation gives quick feedback before sending.",
                        "Server validation is the authoritative check before saving.",
                    ],
                    "A login form can check that email and password are not empty before sending. The server must still verify the credentials. Good validation explains the problem in user-friendly language and prevents invalid data from reaching the database.",
                    "If a quiz creation form receives an empty question list, it should show 'Add at least one question' instead of saving a broken quiz.",
                    [
                        "Only validating in the browser.",
                        "Showing vague messages such as 'invalid'.",
                        "Accepting input that the next screen cannot display.",
                    ],
                    "Design validation rules for a teacher creating a quiz question with four options.",
                    "Validation protects both the user experience and the database. It should be specific and repeated on the server.",
                ),
            ),
        ],
    },
]


QUIZ_BANKS = {
    "Variables and Data Types": _questions([
        ("Which option describes a variable best?", ["A named container for data", "A repeated loop block", "A syntax error", "A network request"], 0, "A variable gives a reusable name to a value stored by the program.", "easy", "variables", "Look for the option that connects a name with stored data."),
        ("Which value is a boolean?", ["42", "\"hello\"", "true", "3.14"], 2, "A boolean represents a true-or-false condition.", "easy", "data-types", "Booleans are often used inside if statements."),
        ("A learner profile stores XP as 1450. Which type is most appropriate?", ["String", "Integer", "Boolean", "Image"], 1, "XP is a whole-number quantity, so an integer is the most appropriate type.", "easy", "data-types", "Choose the type designed for whole numbers."),
        ("Why should a variable named isCompleted usually store true or false?", ["The name suggests a yes-or-no state", "It stores a long paragraph", "It must hold a file", "It is always a decimal"], 0, "Names that start with is often represent boolean states such as completed or not completed.", "medium", "naming", "Think about what question the variable name answers."),
        ("What is the main problem with storing a score as the text \"90\"?", ["It may need conversion before numeric calculations", "It cannot be displayed", "It is always false", "It deletes the quiz"], 0, "Text that looks numeric may still need conversion before arithmetic or comparison.", "medium", "type-conversion", "The quotes are the clue."),
        ("Which variable name is clearest for a student's current level?", ["x", "value", "currentLevel", "thing"], 2, "currentLevel describes the meaning of the stored value.", "easy", "naming", "Prefer names that explain purpose."),
        ("A list of quiz scores is useful because it can store...", ["Only one number", "Multiple related values in order", "A single true or false", "Only lesson titles"], 1, "A list stores multiple values and keeps their order.", "medium", "collections", "Think about grouped values."),
    ]),
    "Control Flow and Decisions": _questions([
        ("Which statement helps a program choose between paths?", ["if", "list", "import", "return type"], 0, "An if statement checks a condition and chooses whether a block runs.", "easy", "conditionals", "The keyword is used for decisions."),
        ("Which construct repeats code while a condition remains true?", ["variable", "while loop", "string", "database"], 1, "A while loop repeats as long as its condition evaluates to true.", "easy", "loops", "Look for repetition."),
        ("If score >= 70, the app shows 'Passed'. What is score >= 70?", ["A condition", "A list", "A file path", "A function name"], 0, "score >= 70 is a true-or-false expression used to choose a branch.", "easy", "conditions", "It can be true or false."),
        ("Why is an else branch useful in a quiz result screen?", ["It handles the case where the condition is false", "It creates a new database", "It removes all errors", "It changes the programming language"], 0, "Else defines what should happen when the if condition is not met.", "medium", "branching", "Think about the alternative path."),
        ("Which bug is most likely in a loop whose condition never becomes false?", ["Infinite loop", "Better typography", "Missing image", "Correct validation"], 0, "A loop that never reaches a false condition can run forever.", "medium", "loops", "The loop needs a stopping point."),
        ("You need to check every answer in a submitted quiz. What is the best tool?", ["A loop", "A color picker", "A title string", "A password field"], 0, "A loop is appropriate because the same check repeats for each answer.", "easy", "iteration", "The phrase every answer signals repetition."),
        ("A learner earns a badge only after five completed lessons. Which condition matches that rule?", ["completedLessons >= 5", "completedLessons == 0", "name == 'badge'", "quizTitle < score"], 0, "The badge should be awarded when the completion count reaches at least five.", "medium", "conditions", "At least five means greater than or equal to five."),
    ]),
    "Functions and Problem Decomposition": _questions([
        ("Why use functions?", ["To reuse and name logic", "To rename every variable randomly", "To avoid all inputs", "To remove the need for testing"], 0, "Functions package logic under a clear name so it can be reused and tested.", "easy", "functions", "Think reuse and clarity."),
        ("In calculateScore(correct, total), what are correct and total?", ["Parameters", "HTML tags", "Network ports", "Database tables"], 0, "Parameters are input names listed in a function definition.", "easy", "parameters", "They receive values when the function is called."),
        ("What should a function named calculateAccuracy most likely return?", ["A numeric accuracy value", "A random password", "A CSS layout", "An unrelated lesson title"], 0, "The function name describes a calculation, so returning the calculated value is expected.", "easy", "return-values", "Match the name to the output."),
        ("Which function has the clearest single responsibility?", ["awardXp(score)", "doEverythingForTheWholeApp()", "fixStuff()", "data()"], 0, "awardXp(score) describes one focused job.", "medium", "decomposition", "Specific names usually signal focused behavior."),
        ("Why is decomposition useful for a quiz submission feature?", ["It splits scoring, feedback, and saving into understandable steps", "It forces all code into one line", "It removes user input", "It prevents lessons from loading"], 0, "Separating responsibilities makes the feature easier to test and explain.", "medium", "decomposition", "Think about smaller steps."),
        ("What is a return value?", ["The result a function sends back", "A spelling mistake", "A button color", "A database password"], 0, "A return value is the output passed back to the caller.", "easy", "return-values", "It leaves the function."),
        ("A function prints the score but the dashboard needs to use the number. What is the better design?", ["Return the score value", "Delete the dashboard", "Store the score as an icon", "Ignore the calculation"], 0, "Returning the score lets other parts of the program use it.", "hard", "function-design", "Printing is not the same as providing data to another step."),
    ]),
    "Algorithms and Step-by-Step Thinking": _questions([
        ("What is an algorithm?", ["A clear sequence of steps for solving a problem", "Only a computer screen", "A random variable name", "A type of font"], 0, "An algorithm is a repeatable process made of ordered steps.", "easy", "algorithms", "Look for step-by-step process."),
        ("Which step should come first when checking quiz answers?", ["Load or receive the submitted answers", "Show final XP before scoring", "Delete all questions", "Ignore correct answers"], 0, "The algorithm needs the user's answers before it can compare or score them.", "easy", "algorithm-order", "Data must exist before it can be processed."),
        ("What are inputs in a quiz-scoring algorithm?", ["Student answers and correct answers", "Only button colors", "The app logo", "A paragraph about CSS"], 0, "The scoring process needs both the submitted answers and the correct answers.", "easy", "inputs", "Inputs are the data the algorithm receives."),
        ("Why should an algorithm handle an empty list of questions?", ["To avoid invalid scoring such as division by zero", "To make the screen darker", "To rename the user", "To skip validation forever"], 0, "A robust algorithm handles edge cases before calculations fail.", "medium", "edge-cases", "Think about total questions equal to zero."),
        ("To find the highest score, what value should be updated during the loop?", ["The current best score", "The course title", "The font size", "The user's email"], 0, "The algorithm tracks the best score seen so far.", "medium", "search", "Keep the strongest candidate while checking the rest."),
        ("Which description is most precise?", ["Compare each submitted answer with the matching correct answer", "Do the quiz thing", "Make it work", "Use some data"], 0, "Precise steps are easier to implement, test, and explain.", "medium", "precision", "Avoid vague instructions."),
        ("What is the output of a quiz-scoring algorithm?", ["Score and feedback", "Raw keyboard input only", "A CSS selector", "An unused loop"], 0, "After processing answers, the useful output is a score and feedback.", "easy", "outputs", "Output is the result."),
    ]),
    "Debugging and Error Handling": _questions([
        ("What is a logic error?", ["Code runs but produces the wrong result", "Code is perfectly correct", "The monitor is off", "A heading is too large"], 0, "A logic error means the program executes but the behavior is incorrect.", "easy", "debugging", "The code runs, but the answer is wrong."),
        ("Which debugging step is usually best first?", ["Reproduce the problem", "Change random files", "Ignore the error", "Delete all tests"], 0, "You need to see the problem reliably before you can isolate it.", "easy", "debugging-process", "Confirm what is happening."),
        ("A quiz has no questions and scoring divides by total questions. What error risk appears?", ["Division by zero", "Better accessibility", "A successful login", "A valid badge"], 0, "Dividing by zero is invalid and should be handled before scoring.", "medium", "error-handling", "The total is zero."),
        ("What should a student-facing error message do?", ["Explain the problem and recovery path", "Show a raw stack trace", "Hide the problem", "Insult the user"], 0, "Useful error messages are clear, respectful, and actionable.", "easy", "ux-errors", "Think about what helps the learner continue."),
        ("Why is changing one thing at a time useful during debugging?", ["It helps identify which change fixed the issue", "It slows the computer permanently", "It prevents reading logs", "It removes all variables"], 0, "Small changes keep cause and effect visible.", "medium", "debugging-process", "Avoid losing track of the real cause."),
        ("A syntax error means...", ["The code cannot be parsed correctly", "The code always gives the wrong score", "The network is always offline", "The database is full"], 0, "Syntax errors happen when code violates language rules.", "easy", "error-types", "Syntax is code grammar."),
        ("Which check protects a quiz review screen?", ["Confirm the selected answer index is inside the options list", "Assume every index is valid", "Remove all explanations", "Skip loading questions"], 0, "Index validation prevents crashes and incorrect review output.", "hard", "validation", "The answer index must match an existing option."),
    ]),
    "Python Syntax and Indentation": _questions([
        ("What does indentation communicate in Python?", ["Program structure", "Network latency", "Database size", "Compiler brand"], 0, "Indentation defines which statements belong to the same block.", "easy", "python-syntax", "Watch the left edge of the code."),
        ("Which line starts a valid Python if block?", ["if score >= 70:", "if score >= 70", "if score >= 70 then", "<if score>"], 0, "Python if headers end with a colon.", "easy", "conditionals", "The colon opens the block."),
        ("In Python, an expression is code that...", ["Produces a value", "Only stores images", "Deletes indentation", "Cannot be used in conditions"], 0, "Expressions evaluate to values, such as score >= 70 producing true or false.", "medium", "expressions", "Think evaluates to something."),
        ("What will this code print if score is 80?\nif score >= 70:\n    print('Passed')", ["Passed", "Failed", "score", "Nothing because 80 is text"], 0, "The condition is true, so the indented print statement runs.", "easy", "code-reading", "80 is greater than 70."),
        ("What is a common indentation mistake?", ["Mixing tabs and spaces", "Using meaningful variable names", "Writing comments", "Returning a value"], 0, "Mixed tabs and spaces can create confusing or invalid Python blocks.", "medium", "indentation", "The problem is inconsistent spacing."),
        ("Which statement is outside the if block?\nif passed:\n    print('Great')\nprint('Done')", ["print('Done')", "print('Great')", "if passed:", "Both print lines"], 0, "print('Done') is not indented, so it runs after the if block.", "medium", "code-reading", "Compare indentation levels."),
        ("Why is Python readable for beginners?", ["Its structure is visible through indentation and simple syntax", "It ignores all errors", "It has no variables", "It only runs in browsers"], 0, "Python emphasizes readable syntax and clear blocks.", "easy", "python-syntax", "Think readability."),
    ]),
    "Lists and Loops": _questions([
        ("What does a Python list store?", ["Multiple values in order", "Only one true or false", "Only a CSS rule", "A server route"], 0, "A list is an ordered collection of values.", "easy", "lists", "Think grouped values."),
        ("What is the first index in a Python list?", ["0", "1", "-1 only", "10"], 0, "Python list indexes start at 0.", "easy", "indexes", "Most programming lists start counting at zero."),
        ("What will this loop print?\nscores = [70, 80]\nfor score in scores:\n    print(score)", ["70 then 80", "80 then 70", "score only", "Nothing"], 0, "The loop visits list items in order and prints each one.", "easy", "loops", "Read the list left to right."),
        ("Which task is best suited for a loop?", ["Checking every quiz answer", "Choosing one app title", "Writing a single heading", "Picking one icon manually"], 0, "A loop is useful when the same action repeats for multiple items.", "easy", "iteration", "The word every signals repetition."),
        ("What happens if a three-item list is accessed at index 3?", ["It is out of range", "It returns the first item", "It always returns true", "It sorts the list"], 0, "Indexes for three items are 0, 1, and 2.", "medium", "indexes", "Count from zero."),
        ("Why might for score in scores be clearer than for i in range(len(scores))?", ["It directly gives each score when the index is not needed", "It deletes the list", "It creates a database", "It prevents all bugs"], 0, "Direct item loops are simpler when position is irrelevant.", "medium", "loop-design", "Use the simplest loop that fits the need."),
        ("Which code adds a new score to a list named scores?", ["scores.append(90)", "scores.deleteAll()", "append.scores(90)", "scores = true"], 0, "append adds a new item to the end of a Python list.", "medium", "lists", "Look for the list method."),
    ]),
    "Functions and Parameters": _questions([
        ("Which keyword defines a Python function?", ["def", "func", "method", "create"], 0, "Python uses def to define a function.", "easy", "functions", "It starts the function header."),
        ("In def passed(score):, what is score?", ["A parameter", "A CSS selector", "A database table", "A file name"], 0, "score is a parameter that receives an argument when the function is called.", "easy", "parameters", "It appears inside the parentheses."),
        ("What does return do in a function?", ["Sends a result back to the caller", "Prints every variable automatically", "Starts a web server", "Deletes parameters"], 0, "return provides the function's output to the code that called it.", "easy", "return-values", "Return sends back."),
        ("What will accuracy(3, 6) return?\ndef accuracy(correct, total):\n    return correct / total", ["0.5", "3", "6", "18"], 0, "3 divided by 6 equals 0.5.", "medium", "code-reading", "Substitute the arguments into the parameters."),
        ("Why should a function avoid doing unrelated tasks?", ["Focused functions are easier to test and reuse", "It makes code impossible to read", "It prevents parameters", "It removes return values"], 0, "Single-purpose functions have clearer behavior and simpler tests.", "medium", "function-design", "One clear purpose is easier to reason about."),
        ("What is the argument in passed(85)?", ["85", "passed", "score", "def"], 0, "An argument is the actual value passed into the function call.", "easy", "arguments", "It is inside the call parentheses."),
        ("Which function name is clearest?", ["calculateXp", "do", "thing", "runAllStuff"], 0, "calculateXp describes the function's purpose.", "easy", "naming", "Good names explain the action."),
    ]),
    "Dictionaries and Data Structures": _questions([
        ("Which structure stores key-value pairs in Python?", ["Dictionary", "List only", "String", "Loop"], 0, "A dictionary maps keys to values.", "easy", "dictionaries", "Keys are the clue."),
        ("In learner = {'xp': 1450}, what is 'xp'?", ["A key", "A loop", "A function", "An error type"], 0, "'xp' is the key used to access the stored value.", "easy", "keys", "It labels the value."),
        ("Which expression reads the XP value?", ["learner['xp']", "learner(xp)", "xp.learner", "learner->xp only"], 0, "Dictionary values are read by using the key in brackets.", "easy", "dictionary-access", "Use square brackets with the key."),
        ("When is a dictionary better than a list?", ["When values have named fields", "When order is the only concern", "When data must be hidden from code", "When no values are stored"], 0, "Dictionaries are clearer when each value has a meaningful key.", "medium", "data-structures", "Think profile fields."),
        ("What risk occurs when accessing learner['level'] if the key does not exist?", ["A key error", "A successful update", "A CSS change", "A sorted list"], 0, "Reading a missing dictionary key can raise a KeyError.", "medium", "errors", "The requested key is absent."),
        ("Which data structure is best for scores = [80, 90, 75]?", ["List", "Dictionary only", "Boolean", "Function"], 0, "A list is good for an ordered group of similar values.", "easy", "lists", "The values are a sequence."),
        ("Why do API responses often look like dictionaries?", ["They use named fields that the client can read predictably", "They cannot contain text", "They replace all validation", "They are always images"], 0, "Named fields make structured data easier for clients to parse.", "hard", "api-data", "Think JSON object fields."),
    ]),
    "Reading Errors and Debugging": _questions([
        ("What is a traceback?", ["A report showing where Python failed", "A list of colors", "A database backup", "A CSS property"], 0, "A traceback shows the call path and error location.", "easy", "tracebacks", "It traces the error."),
        ("Which error means a variable name was used before being defined?", ["NameError", "ColorError", "RouteError", "StyleError"], 0, "NameError often appears when Python cannot find a name.", "easy", "error-types", "The name is unknown."),
        ("Which error is likely from '5' + 2 in Python?", ["TypeError", "IndentationSuccess", "HttpOK", "BadgeError"], 0, "Adding a string and an integer directly uses incompatible types.", "medium", "type-errors", "The operands have different types."),
        ("Where is the most useful summary of a Python error usually found?", ["Near the last line of the traceback", "Only in the app icon", "Inside the README title", "In a CSS file"], 0, "The last line usually names the error type and message.", "easy", "tracebacks", "Start at the end."),
        ("Why should you run a small example after fixing a bug?", ["To confirm the specific behavior is corrected", "To hide the bug report", "To change the programming language", "To delete the function"], 0, "A small check proves whether the fix addresses the observed problem.", "medium", "debugging-process", "Verify the fix."),
        ("What should accuracy(correct, total) do if total is 0?", ["Handle it safely before dividing", "Divide anyway", "Return a random value", "Delete correct"], 0, "The function should guard against division by zero.", "medium", "defensive-code", "Zero cannot be a divisor."),
        ("Which habit makes debugging harder?", ["Changing many unrelated lines at once", "Reading the error message", "Reproducing the issue", "Testing a small fix"], 0, "Large unrelated changes make it difficult to know what fixed or caused the issue.", "easy", "debugging-process", "Keep changes focused."),
    ]),
    "HTML Structure": _questions([
        ("Which HTML tag defines the main heading?", ["<h1>", "<p>", "<a>", "<img>"], 0, "<h1> marks the main heading of a page or section.", "easy", "html-headings", "h stands for heading."),
        ("What is semantic HTML?", ["Using tags that describe meaning", "Using only colors", "Writing Python in HTML", "Removing all structure"], 0, "Semantic tags communicate the role of content, not just appearance.", "easy", "semantic-html", "Meaning is the key word."),
        ("Which attribute gives a link its destination?", ["href", "src", "alt", "classNameOnly"], 0, "The href attribute stores the URL a link points to.", "easy", "links", "Links reference a destination."),
        ("Which tag is best for a paragraph of lesson text?", ["<p>", "<button>", "<script>", "<table>"], 0, "<p> represents a paragraph.", "easy", "html-text", "Paragraph starts with p."),
        ("Why should link text be descriptive?", ["It helps users and assistive tools understand the destination", "It makes the server faster", "It replaces validation", "It hides the URL permanently"], 0, "Descriptive link text improves usability and accessibility.", "medium", "accessibility", "Think screen readers and scanning."),
        ("What is an HTML element?", ["A tag with its content and closing tag when needed", "Only a database row", "A Python loop", "A CSS color"], 0, "An element includes the tag structure and the content it wraps.", "easy", "html-elements", "Think opening tag, content, closing tag."),
        ("Which structure is best for a list of lessons?", ["<ul> with <li> items", "<h1> for every item", "<script> only", "<img> for text"], 0, "A list of items is semantically represented with list tags.", "medium", "html-lists", "Lessons are repeated list items."),
    ]),
    "CSS Styling and Layout": _questions([
        ("What does CSS control?", ["Presentation and layout", "Database authentication", "Python imports", "Server hardware"], 0, "CSS controls visual styling such as color, spacing, and layout.", "easy", "css-basics", "Think how it looks."),
        ("Which part of the box model is inside the border around content?", ["Padding", "Margin", "Server", "Route"], 0, "Padding is the space between content and border.", "easy", "box-model", "Inside the border is padding."),
        ("What does a CSS selector do?", ["Chooses which elements a rule applies to", "Stores quiz attempts", "Runs Python code", "Sends an HTTP request"], 0, "Selectors target elements for styling.", "easy", "selectors", "Select means choose."),
        ("Which layout tool is commonly used for arranging items in a row or column?", ["Flexbox", "Traceback", "SQLite", "Boolean"], 0, "Flexbox is designed for one-dimensional layout.", "easy", "layout", "Flex suggests flexible arrangement."),
        ("Why should mobile layouts avoid fixed desktop-only widths?", ["They may overflow on small screens", "They make passwords safer", "They improve server logs", "They remove all text"], 0, "Rigid widths can break on narrow screens.", "medium", "responsive-design", "Phones have limited width."),
        ("Which property changes text color?", ["color", "padding", "display", "href"], 0, "The color property controls text color.", "easy", "css-properties", "It says color."),
        ("Why should status not rely only on color?", ["Some users may not distinguish colors easily", "Color deletes content", "It prevents HTML", "It breaks all loops"], 0, "Accessible design uses text or icons along with color.", "medium", "accessibility", "Color alone can be ambiguous."),
    ]),
    "JavaScript Basics": _questions([
        ("What does JavaScript usually add to a web page?", ["Behavior and interaction", "Only database tables", "Only static headings", "Server electricity"], 0, "JavaScript responds to events and updates page behavior.", "easy", "javascript-basics", "Think clicks and updates."),
        ("What is an event?", ["An action such as a click or key press", "A CSS color", "A database table", "A Python package"], 0, "Events represent actions the code can respond to.", "easy", "events", "Click is a common event."),
        ("What does DOM stand for in web development?", ["Document Object Model", "Data Output Machine", "Design Order Method", "Database Object Mode"], 0, "The DOM is the browser's structured representation of the page.", "medium", "dom", "It models the document."),
        ("What should happen after a learner selects a quiz option?", ["Record the answer and update the UI state", "Delete the lesson", "Change every course title", "Ignore the selection"], 0, "Interactive quiz behavior requires storing the answer and showing progress.", "medium", "state", "The app must remember the choice."),
        ("Why should code avoid putting too much logic inside one click handler?", ["It becomes harder to test and maintain", "It makes HTML semantic", "It improves indentation automatically", "It removes all events"], 0, "Complex handlers should delegate work to clear functions.", "medium", "code-organization", "Small functions help."),
        ("Which value best represents UI state?", ["currentQuestionIndex", "<h1>", "color: blue", "GET /api"], 0, "currentQuestionIndex stores where the quiz UI currently is.", "easy", "state", "State is remembered data."),
        ("What is a common mistake when updating the UI?", ["Changing what is displayed but not the stored state", "Using readable names", "Handling click events", "Testing behavior"], 0, "If state and display disagree, later behavior can be wrong.", "hard", "state-management", "The screen and stored value must match."),
    ]),
    "Client-Server Communication": _questions([
        ("What does an HTTP request usually do?", ["Asks a server for data or sends data to it", "Changes only font size", "Runs only on paper", "Deletes the browser"], 0, "HTTP requests are messages between client and server.", "easy", "http", "Request means ask or send."),
        ("What format is commonly used for API data?", ["JSON", "Only PNG", "Only CSS", "Only WAV"], 0, "JSON is a common structured text format for API requests and responses.", "easy", "json", "APIs often exchange objects and lists."),
        ("In a learning app, what is the client?", ["The mobile app or browser interface", "Only the database", "Only the CPU fan", "A password hash"], 0, "The client is the user-facing app that makes requests.", "easy", "client-server", "The learner interacts with it."),
        ("Why are stable API contracts important?", ["The frontend can parse responses predictably", "They make icons larger", "They remove all validation", "They replace lessons"], 0, "The client depends on agreed field names and response shapes.", "medium", "api-contracts", "Contract means agreement."),
        ("Which response is most useful after quiz submission?", ["Score, XP, feedback, and wrong-answer details", "Only a blank string", "Only the app logo", "Only a CSS selector"], 0, "The client needs result data to show meaningful review.", "medium", "api-design", "Think what the result screen displays."),
        ("What should the app do when a request fails?", ["Show a useful error or retry path", "Pretend success always happened", "Delete user progress", "Change the lesson topic"], 0, "Failure handling keeps the user informed and protects data quality.", "medium", "error-handling", "Network requests can fail."),
        ("Which endpoint name best suggests loading courses?", ["GET /api/courses", "POST /delete-all", "STYLE /button", "FONT /main"], 0, "GET /api/courses clearly describes reading course data.", "easy", "rest", "GET reads data."),
    ]),
    "Forms and Validation": _questions([
        ("What is validation?", ["Checking input before using or saving it", "Only changing button color", "Removing all forms", "Writing random data"], 0, "Validation confirms that input meets required rules.", "easy", "validation", "Check before use."),
        ("Why is server-side validation still needed if the client validates?", ["Client checks can be bypassed", "Server validation changes fonts", "It removes the need for data", "It only works offline"], 0, "The server must enforce the real rules because clients are not fully trusted.", "medium", "server-validation", "The server is authoritative."),
        ("Which validation message is most helpful?", ["Password must contain at least 6 characters", "Invalid", "No", "Bad"], 0, "Specific messages tell the user how to fix the input.", "easy", "ux-validation", "Actionable feedback helps."),
        ("A teacher creates a quiz with zero questions. What should validation do?", ["Reject it and ask for at least one question", "Save it as complete", "Award full XP", "Hide the course"], 0, "A quiz without questions cannot support meaningful practice.", "medium", "content-validation", "The quiz needs content."),
        ("Which field is usually required for login?", ["Email", "Favorite color", "Screen brightness", "Course category only"], 0, "Login needs an identifier such as email.", "easy", "forms", "Credentials identify the account."),
        ("Why validate selected answer indexes?", ["To ensure the answer refers to an existing option", "To make all answers correct", "To remove explanations", "To change the lesson title"], 0, "Indexes outside the options list are invalid and can break review.", "hard", "quiz-validation", "The index must point to a real option."),
        ("What is client-side validation best for?", ["Fast user feedback before sending a request", "Final security enforcement only", "Replacing the database", "Changing HTTP into CSS"], 0, "Client validation improves usability, but the server still enforces rules.", "medium", "client-validation", "It is quick feedback."),
    ]),
}


QUIZ_VARIETY_OVERRIDES = {
    "Control Flow and Decisions": {
        1: {
            "type": "true_false",
            "q": "True or false: an else block runs when the if condition is true.",
            "options": ["True", "False"],
            "answer": 1,
            "explanation": "An else block runs when the if condition is false, so the statement is false.",
            "hint": "Think about the path that runs when the condition does not pass.",
        },
        3: {
            "type": "ordering",
            "q": "Which order best describes a badge-award decision?",
            "options": [
                "Check completed lessons -> compare with badge rule -> award badge if the rule passes",
                "Award badge -> check completed lessons -> compare with badge rule",
                "Compare with badge rule -> award badge -> load completed lessons",
                "Delete progress -> award badge -> ask for completed lessons",
            ],
            "answer": 0,
            "explanation": "A decision should first inspect current progress, then compare it with the rule, then award the badge only if the condition is met.",
            "hint": "The app needs the learner's progress before it can decide anything.",
        },
    },
    "Algorithms and Step-by-Step Thinking": {
        2: {
            "type": "ordering",
            "q": "Choose the correct high-level order for checking a quiz result.",
            "options": [
                "Load answers -> compare with correct indexes -> count correct answers -> calculate score",
                "Calculate score -> load answers -> count correct answers -> compare indexes",
                "Count correct answers -> calculate score -> load answers -> compare indexes",
                "Compare indexes -> calculate score -> delete answers -> count correct answers",
            ],
            "answer": 0,
            "explanation": "The algorithm needs the submitted answers first, then it compares, counts, and calculates the final score.",
            "hint": "Start from the input before doing calculations.",
        },
    },
    "Debugging and Error Handling": {
        2: {
            "type": "ordering",
            "q": "Which debugging sequence is the safest?",
            "options": [
                "Reproduce the issue -> read the message -> inspect one assumption -> test the fix",
                "Change many files -> guess the cause -> ignore the message -> test later",
                "Delete the feature -> read the message -> change unrelated code -> publish",
                "Test the fix -> reproduce the issue -> ignore the traceback -> guess",
            ],
            "answer": 0,
            "explanation": "A reliable debugging loop narrows the problem before changing code.",
            "hint": "Debugging works best when each step reduces uncertainty.",
        },
    },
    "Python Syntax and Indentation": {
        0: {
            "type": "code_output",
            "q": "If score is 80, what will this code print?",
            "code": "score = 80\nif score >= 70:\n    print('Passed')\nprint('Done')",
            "options": ["Passed then Done", "Only Done", "Only Passed", "Nothing"],
            "answer": 0,
            "explanation": "The indented print runs because the condition is true, and the final print runs after the if block.",
            "hint": "Watch which line is indented and which line is outside the block.",
        },
        1: {
            "type": "fill_gap",
            "q": "Fill the missing Python keyword: ___ score >= 70:",
            "options": ["if", "for", "def", "return"],
            "answer": 0,
            "explanation": "The if keyword starts a conditional decision.",
            "hint": "The line checks whether a condition is true.",
        },
    },
    "Lists and Loops": {
        2: {
            "type": "code_output",
            "q": "What will this loop print?",
            "code": "scores = [80, 95]\nfor score in scores:\n    print(score)",
            "options": ["80 then 95", "95 then 80", "Only 80", "Nothing"],
            "answer": 0,
            "explanation": "The loop visits the list in order and prints each value.",
            "hint": "Lists keep order, and the loop reads one item at a time.",
        },
    },
    "Functions and Parameters": {
        1: {
            "type": "fill_gap",
            "q": "Fill the missing keyword: ___ accuracy(correct, total):",
            "options": ["def", "for", "if", "return"],
            "answer": 0,
            "explanation": "Python uses def to define a function.",
            "hint": "The line is introducing a reusable named block.",
        },
    },
    "Dictionaries and Data Structures": {
        2: {
            "type": "code_output",
            "q": "What value does this code print?",
            "code": "learner = {'name': 'Aida', 'xp': 120}\nprint(learner['xp'])",
            "options": ["120", "Aida", "xp", "name"],
            "answer": 0,
            "explanation": "The key 'xp' retrieves the value 120 from the dictionary.",
            "hint": "Look at the value stored under the selected key.",
        },
    },
    "HTML Structure": {
        0: {
            "type": "fill_gap",
            "q": "Fill the missing tag name: <___>Main title</___>",
            "options": ["h1", "p", "a", "img"],
            "answer": 0,
            "explanation": "h1 is the main heading tag.",
            "hint": "The tag name starts with h for heading.",
        },
    },
    "CSS Styling and Layout": {
        1: {
            "type": "true_false",
            "q": "True or false: padding is the space inside the border around content.",
            "options": ["True", "False"],
            "answer": 0,
            "explanation": "Padding sits between the content and border.",
            "hint": "Margin is outside the border; padding is inside it.",
        },
    },
    "JavaScript Basics": {
        2: {
            "type": "code_output",
            "q": "What value is stored after this JavaScript code runs?",
            "code": "let currentQuestionIndex = 0;\ncurrentQuestionIndex = currentQuestionIndex + 1;",
            "options": ["1", "0", "currentQuestionIndex", "undefined"],
            "answer": 0,
            "explanation": "The variable starts at 0 and then increases by 1.",
            "hint": "Track the variable value after the assignment.",
        },
    },
    "Client-Server Communication": {
        3: {
            "type": "ordering",
            "q": "Which request-response order is correct?",
            "options": [
                "Client sends request -> server handles it -> server returns response -> UI updates",
                "UI updates -> server returns response -> client sends request -> server handles it",
                "Server handles it -> UI updates -> client sends request -> response returns",
                "Client sends request -> UI deletes data -> server guesses -> response disappears",
            ],
            "answer": 0,
            "explanation": "The client starts the exchange, the server processes it, and the response lets the UI update.",
            "hint": "Start from the app asking the backend for something.",
        },
    },
    "Forms and Validation": {
        1: {
            "type": "true_false",
            "q": "True or false: server-side validation is still needed even when the client validates input.",
            "options": ["True", "False"],
            "answer": 0,
            "explanation": "Client checks improve UX, but the server must enforce the real rules.",
            "hint": "A client can be bypassed; the server protects shared data.",
        },
    },
}


def _quiz_payload(lesson_title: str, title: str) -> list[dict]:
    questions = [dict(question) for question in QUIZ_BANKS[lesson_title]]
    for index, override in QUIZ_VARIETY_OVERRIDES.get(lesson_title, {}).items():
        if 0 <= index < len(questions):
            questions[index].update(override)
            questions[index]["question"] = questions[index]["q"]
            questions[index]["correctIndex"] = questions[index]["answer"]
    return questions


def seed_db(*, reset: bool = False):
    if reset:
        print("Dropping all tables to reset state...")
        models.Base.metadata.drop_all(bind=engine)

    print("Ensuring tables exist...")
    models.Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    now = datetime.utcnow()

    has_existing_data = (
        db.query(models.User).first() is not None
        or db.query(models.Course).first() is not None
        or db.query(models.Quiz).first() is not None
    )
    if has_existing_data:
        print("Existing EduQuest data detected. Skipping demo reseed.")
        db.close()
        return

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

    for course_blueprint in COURSE_BLUEPRINTS:
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
                xp_reward=100 + min(50, (lesson_index - 1) * 10),
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
            instructions="Complete this quiz after revising decisions, loops, and badge-award examples.",
            due_at=now + timedelta(days=3),
            is_published=True,
        ),
        models.Assignment(
            quiz_id=quizzes_by_title["Functions and Parameters Quiz"].id,
            course_id=courses_by_title["Python Programming Basics"].id,
            title="Python functions practice",
            instructions="Review function inputs, return values, and code-reading examples.",
            due_at=now + timedelta(days=5),
            is_published=True,
        ),
        models.Assignment(
            quiz_id=quizzes_by_title["Client-Server Communication Quiz"].id,
            course_id=courses_by_title["Web Development Fundamentals"].id,
            title="Client-server checkpoint",
            instructions="Review request-response structure and stable JSON contracts before submitting.",
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
        (student.id, lesson_lookup["Python Syntax and Indentation"].id, now - timedelta(days=2)),
        (alice.id, lesson_lookup["Variables and Data Types"].id, now - timedelta(days=6)),
        (alice.id, lesson_lookup["Lists and Loops"].id, now - timedelta(days=3)),
        (alice.id, lesson_lookup["Dictionaries and Data Structures"].id, now - timedelta(days=2)),
        (bob.id, lesson_lookup["HTML Structure"].id, now - timedelta(days=1)),
        (bob.id, lesson_lookup["Client-Server Communication"].id, now - timedelta(hours=12)),
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
    add_attempt("student@eduquest.com", "Control Flow and Decisions Quiz", 0.57, 57, 7)
    add_attempt("student@eduquest.com", "Control Flow and Decisions Quiz", 0.86, 86, 6)
    add_attempt("student@eduquest.com", "Functions and Problem Decomposition Quiz", 0.8, 80, 5)
    add_attempt("student@eduquest.com", "Python Syntax and Indentation Quiz", 0.71, 71, 2)
    add_attempt("alice@eduquest.com", "Variables and Data Types Quiz", 0.86, 86, 6)
    add_attempt("alice@eduquest.com", "Lists and Loops Quiz", 0.71, 71, 3)
    add_attempt("alice@eduquest.com", "Reading Errors and Debugging Quiz", 0.75, 75, 1)
    add_attempt("bob@eduquest.com", "HTML Structure Quiz", 0.71, 71, 1)
    add_attempt("bob@eduquest.com", "Client-Server Communication Quiz", 0.57, 57, 0)
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
            context="Client-Server Communication",
            question="Why do frontend screens break when API field names change?",
            hint="Because the UI parser expects a stable contract and cannot infer renamed fields reliably.",
            timestamp=now - timedelta(hours=12),
        ),
        models.AILog(
            user_id=bob.id,
            context="Forms and Validation",
            question="Why should validation happen on the server too?",
            hint="Because client-side checks can be bypassed, while the server protects shared data.",
            timestamp=now - timedelta(hours=4),
        ),
    ]
    db.add_all(ai_logs)
    db.commit()

    print("Database seeded successfully with defense-ready course, lesson, and quiz content!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop and recreate all tables before seeding demo data.",
    )
    args = parser.parse_args()
    seed_db(reset=args.reset)
