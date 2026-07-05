"""
Уточняющий диалог перед правовым анализом ВНД.
До 5 вопросов, по одному за раз.
"""
from __future__ import annotations

from typing import Callable, List, Optional

from openai import OpenAI
from config import settings

MAX_CLARIFICATION_QUESTIONS = 5

START_KEYWORDS = ("начни", "начать", "приступ", "старт", "проанализ", "анализируй")
SKIP_KEYWORDS = (
    "начинай анализ",
    "пропустить уточн",
    "без уточн",
    "достаточно",
    "к анализу",
    "пропусти вопрос",
)

CLARIFIER_SYSTEM = """Ты — юридический методист. Перед анализом ВНД нужно уточнить контекст организации.

СТРОГИЕ ПРАВИЛА:
- Задай ТОЛЬКО ОДИН новый вопрос по указанной теме.
- Не повторяй уже заданные вопросы и не спрашивай то, на что клиент уже ответил.
- Вопрос должен заканчиваться знаком «?».
- Кратко поясни, зачем нужен ответ (1 короткое предложение).
- Пиши по-русски, дружелюбно и профессионально."""

DEFAULT_QUESTIONS = [
    "Уточните, пожалуйста, сферу деятельности вашей организации: отрасль, основные виды деятельности и форма (коммерческая / бюджетная / некоммерческая). Это нужно, чтобы определить применимые нормы законодательства.",
    "Сколько сотрудников в организации и есть ли филиалы или обособленные подразделения? Так мы учтём масштаб требований к локальным актам.",
    "Обрабатывает ли организация персональные данные, коммерческую тайну или сведения, составляющие гос. тайну? Укажите, если это уже следует из документа.",
    "Есть ли отраслевой регулятор или особые требования (например, ЦБ РФ, медицина, образование, гостайна, ГОСТ по ИБ)?",
    "Какова основная цель этого ВНД и какие процессы он регламентирует? Есть ли особые пожелания к фокусу анализа?",
]

QUESTION_TOPICS = [
    "сфера деятельности и тип организации",
    "масштаб организации и филиалы",
    "персональные данные и коммерческая тайна",
    "отраслевой регулятор и особые требования",
    "цель документа и фокус анализа",
]


def is_start_message(text: str) -> bool:
    lower = (text or "").lower().strip()
    return any(keyword in lower for keyword in START_KEYWORDS)


def is_skip_clarification(text: str) -> bool:
    lower = (text or "").lower().strip()
    return any(keyword in lower for keyword in SKIP_KEYWORDS)


def is_clarification_answer(history: Optional[list], user_message: str) -> bool:
    return (
        clarification_started(history)
        and not is_start_message(user_message)
        and not is_skip_clarification(user_message)
    )


def clarification_started(history: Optional[list]) -> bool:
    if not history:
        return False
    return any(
        msg.get("role") == "assistant" and msg.get("phase") == "clarification"
        for msg in history
    )


def count_clarification_answers(history: Optional[list]) -> int:
    if not history:
        return 0

    tagged = sum(
        1
        for msg in history
        if msg.get("role") == "user" and msg.get("phase") == "clarification"
    )
    if tagged:
        return tagged

    started = False
    count = 0
    for msg in history:
        if msg.get("role") == "assistant" and msg.get("phase") == "clarification":
            started = True
            continue
        if started and msg.get("role") == "user":
            content = msg.get("content", "")
            if is_start_message(content) and count == 0:
                continue
            count += 1
    return count


def effective_answer_count(history: Optional[list], user_message: str) -> int:
    count = count_clarification_answers(history)
    if is_clarification_answer(history, user_message):
        count += 1
    return count


def clarification_finished(history: Optional[list]) -> bool:
    if not history:
        return False
    for msg in reversed(history):
        if msg.get("role") == "assistant":
            if msg.get("clarification_complete"):
                return True
            if msg.get("phase") == "analysis":
                return True
            if msg.get("phase") == "clarification":
                return False
    return False


def should_clarify(history: Optional[list], user_message: str) -> bool:
    if is_skip_clarification(user_message):
        return False

    if clarification_finished(history):
        return False

    if clarification_started(history):
        saved_answers = count_clarification_answers(history)
        if saved_answers >= MAX_CLARIFICATION_QUESTIONS:
            return False
        effective = effective_answer_count(history, user_message)
        return effective <= MAX_CLARIFICATION_QUESTIONS

    if not history and is_start_message(user_message):
        return True

    if history and is_start_message(user_message) and not clarification_started(history):
        return True

    return False


def _question_text_from_assistant(msg: dict) -> str:
    text = (msg.get("question_text") or msg.get("content") or "").strip()
    marker = "Можно написать «начинай анализ»"
    if marker in text:
        text = text.split(marker, 1)[-1].strip()
    return text


def format_clarification_summary(
    history: Optional[list],
    user_message: str = "",
    include_pending_answer: bool = False,
) -> str:
    if not history and not include_pending_answer:
        return ""

    pairs: List[str] = []
    pending_question = ""
    pending_index = 0

    def append_pair(question: str, answer: str, index: int = 0) -> None:
        question = (question or "").strip()
        answer = (answer or "").strip()
        if question and answer:
            label = f"{index}. " if index else ""
            pairs.append(f"{label}В: {question}\nО: {answer}")

    for msg in history or []:
        if msg.get("role") == "assistant" and msg.get("phase") == "clarification":
            pending_question = _question_text_from_assistant(msg)
            pending_index = msg.get("question_index") or len(pairs) + 1
            continue
        if msg.get("role") == "user" and msg.get("phase") == "clarification":
            append_pair(pending_question, msg.get("content", ""), pending_index)
            pending_question = ""
            pending_index = 0

    if include_pending_answer and is_clarification_answer(history, user_message):
        append_pair(pending_question, user_message, pending_index)

    return "\n\n".join(pairs)


def _fallback_question(question_number: int) -> str:
    index = min(max(question_number, 1), len(DEFAULT_QUESTIONS)) - 1
    return DEFAULT_QUESTIONS[index]


def _generate_question(
    question_number: int,
    history: list,
    vnd_text: Optional[str],
    context: str,
    format_history: Callable[[list], str],
) -> str:
    base_question = _fallback_question(question_number)
    topic = QUESTION_TOPICS[min(question_number, len(QUESTION_TOPICS)) - 1]

    if not settings.openai_api_key:
        return base_question

    history_text = format_history(history, max_messages=12) if history else "История пуста."
    previous = format_clarification_summary(history)
    vnd_excerpt = (vnd_text or "")[:1500]

    user_prompt = f"""Сформулируй уточняющий вопрос №{question_number} из {MAX_CLARIFICATION_QUESTIONS}.
Тема вопроса: {topic}.
Базовый шаблон (сохрани смысл, можно переформулировать): {base_question}

Уже полученные ответы клиента:
{previous or "пока нет"}

Фрагмент ВНД:
{vnd_excerpt or "текст документа не передан"}

История диалога:
{history_text}

Ответь только одним новым вопросом клиенту."""

    try:
        client = OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": CLARIFIER_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=350,
        )
        text = (response.choices[0].message.content or "").strip()
        if text and "?" in text:
            return text
    except Exception:
        pass

    return base_question


def process_clarification(
    user_message: str,
    history: Optional[list],
    vnd_text: Optional[str],
    get_context: Callable[[str], str],
    format_history: Callable[[list], str],
) -> dict:
    """Задать следующий уточняющий вопрос или завершить этап уточнений."""
    history = history or []

    if is_skip_clarification(user_message):
        summary = format_clarification_summary(history, user_message, include_pending_answer=False)
        return {
            "content": (
                "Хорошо, перехожу к правовому анализу документа без дополнительных уточнений."
            ),
            "phase": "analysis",
            "clarification_complete": True,
            "clarification_summary": summary,
            "question_index": count_clarification_answers(history),
            "max_questions": MAX_CLARIFICATION_QUESTIONS,
        }

    answers_count = effective_answer_count(history, user_message)

    if clarification_started(history) and answers_count >= MAX_CLARIFICATION_QUESTIONS:
        summary = format_clarification_summary(
            history,
            user_message,
            include_pending_answer=is_clarification_answer(history, user_message),
        )
        return {
            "content": (
                "Спасибо за ответы. Лимит уточняющих вопросов (5) исчерпан — "
                "приступаю к правовому анализу документа."
            ),
            "phase": "analysis",
            "clarification_complete": True,
            "clarification_summary": summary,
            "question_index": MAX_CLARIFICATION_QUESTIONS,
            "max_questions": MAX_CLARIFICATION_QUESTIONS,
        }

    question_number = answers_count + 1 if clarification_started(history) else 1
    if question_number > MAX_CLARIFICATION_QUESTIONS:
        summary = format_clarification_summary(history, user_message, include_pending_answer=False)
        return {
            "content": (
                "Уточняющих вопросов достаточно (не более 5). "
                "Приступаю к правовому анализу документа."
            ),
            "phase": "analysis",
            "clarification_complete": True,
            "clarification_summary": summary,
            "question_index": MAX_CLARIFICATION_QUESTIONS,
            "max_questions": MAX_CLARIFICATION_QUESTIONS,
        }
    query = vnd_text[:300] if vnd_text else user_message
    context = get_context(query) if query else ""

    intro = ""
    if question_number == 1:
        intro = (
            "Перед анализом документа задам несколько уточняющих вопросов (не более "
            f"{MAX_CLARIFICATION_QUESTIONS}), по одному — это поможет точнее определить "
            "применимые нормы. Можно написать «начинай анализ», чтобы пропустить оставшиеся вопросы.\n\n"
        )

    question = _generate_question(
        question_number=question_number,
        history=history,
        vnd_text=vnd_text,
        context=context,
        format_history=format_history,
    )

    return {
        "content": f"{intro}{question}",
        "phase": "clarification",
        "clarification_complete": False,
        "question_index": question_number,
        "question_text": question,
        "max_questions": MAX_CLARIFICATION_QUESTIONS,
    }
