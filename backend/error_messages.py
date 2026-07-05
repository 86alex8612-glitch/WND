"""
Понятные сообщения об ошибках на русском языке для API.
"""
from __future__ import annotations

import re
from typing import Any, Optional, Union


ErrorLike = Union[BaseException, str, Any]

_SERVER_HINT = "Убедитесь, что сервер запущен (start_server.bat) и доступен по адресу http://localhost:8011."


def _normalize_text(error: ErrorLike) -> str:
    if error is None:
        return ""
    if isinstance(error, BaseException):
        parts = [str(error).strip()]
        cause = error.__cause__
        if cause and str(cause).strip() and str(cause).strip() not in parts[0]:
            parts.append(str(cause).strip())
        text = ": ".join(part for part in parts if part)
    else:
        text = str(error).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _looks_like_technical(text: str) -> bool:
    markers = (
        "traceback",
        "errno",
        "winerror",
        "exception",
        "error:",
        "http error",
        "status code",
        "permission denied",
        "[",
        " at ",
        "\\",
        ".py",
    )
    lower = text.lower()
    return any(marker in lower for marker in markers)


def humanize_error(error: ErrorLike, context: Optional[str] = None) -> str:
    """Преобразовать техническую ошибку в понятное сообщение на русском."""
    text = _normalize_text(error)
    lower = text.lower()

    if not text:
        return _contextual_fallback(context)

    rules = (
        (
            ("permission denied", "errno 13", "being used by another process"),
            "Не удалось сохранить файл: он открыт в другой программе (часто Adobe Acrobat). "
            "Закройте документ и повторите загрузку.",
        ),
        (
            ("winerror 32", "cannot access the file because it is being used"),
            "Файл используется другой программой. Закройте его и повторите операцию.",
        ),
        (
            ("filenotfounderror", "no such file", "файл не найден", "in\\", "in/"),
            "Файл не найден. Загрузите документ ВНД заново или проверьте папку IN.",
        ),
        (
            ("connection refused", "failed to connect", "connection error", "network is unreachable"),
            f"Не удалось подключиться к серверу. {_SERVER_HINT}",
        ),
        (
            ("timeout", "timed out", "read timed out"),
            "Превышено время ожидания ответа сервера. Попробуйте ещё раз позже.",
        ),
        (
            ("openai_api_key", "api key", "authentication", "incorrect api key", "invalid api key"),
            "Ошибка доступа к OpenAI API. Проверьте ключ OPENAI_API_KEY в файле .env.",
        ),
        (
            ("rate limit", "ratelimit"),
            "Превышен лимит запросов к OpenAI API. Подождите немного и повторите попытку.",
        ),
        (
            ("insufficient_quota", "quota", "billing"),
            "Исчерпана квота OpenAI API. Проверьте баланс и настройки аккаунта.",
        ),
        (
            ("chromadb", "chroma", "sqlite", "database is locked"),
            "Ошибка доступа к базе данных. Перезапустите сервер и повторите операцию.",
        ),
        (
            ("unsupported format", "неподдерживаемый формат"),
            "Неподдерживаемый формат файла. Загрузите PDF, DOCX или TXT.",
        ),
        (
            ("не содержит текста", "no text", "empty document"),
            "Из документа не удалось извлечь текст. Возможно, это скан без текстового слоя.",
        ),
        (
            ("папка in не найдена", "in не найдена"),
            "Папка для загруженных документов IN не найдена. Проверьте настройки проекта.",
        ),
        (
            ("нет загруженных документов", "список документов пуст"),
            "Документ не загружен. Сначала выберите и загрузите файл ВНД.",
        ),
        (
            ("диалог не найден",),
            "Диалог не найден. Возможно, он уже удалён — начните анализ заново.",
        ),
        (
            ("not found", "404"),
            "Запрашиваемые данные не найдены.",
        ),
    )

    for patterns, message in rules:
        if any(pattern in lower for pattern in patterns):
            return message

    if context:
        prefix = {
            "upload": "Не удалось загрузить файл",
            "dialog_create": "Не удалось создать диалог анализа",
            "dialog_delete": "Не удалось удалить диалог",
            "dialog_load": "Не удалось загрузить диалог",
            "analysis": "Не удалось выполнить анализ",
            "references": "Не удалось проверить ссылки на федеральные документы",
            "federal_download": "Не удалось скачать федеральные документы",
            "search": "Не удалось выполнить поиск",
            "reindex": "Не удалось пересоздать базы знаний",
            "report": "Не удалось сохранить отчёт",
            "init": "Не удалось инициализировать систему",
        }.get(context, "Произошла ошибка")

        if _looks_like_technical(text):
            return f"{prefix}. Попробуйте ещё раз или перезапустите сервер."
        if text.lower().startswith(prefix.lower()):
            return text
        return f"{prefix}: {text}"

    if _looks_like_technical(text):
        return "Произошла внутренняя ошибка сервера. Попробуйте ещё раз или перезапустите сервер."

    return text


def _contextual_fallback(context: Optional[str]) -> str:
    return humanize_error("unknown", context) if context else "Произошла неизвестная ошибка. Попробуйте ещё раз."


def http_detail(error: ErrorLike, context: Optional[str] = None) -> str:
    """Сформировать detail для HTTPException."""
    return humanize_error(error, context)
