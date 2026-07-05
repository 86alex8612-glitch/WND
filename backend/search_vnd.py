"""
Диалог «Поиск в ВНД»: вопросы по содержанию выбранного документа.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from openai import OpenAI

from config import settings
from document_loader import extract_full_text

logger = logging.getLogger("search_vnd")

SEARCH_VND_SYSTEM_PROMPT = """Ты — юрист. Проанализируй приложенный документ (ВНД) и ответь строго по его содержанию. При ответе можешь использовать базу FZ (ФЗ). Не используй внешние источники, не придумывай и не дополняй текст.

Ответ должен быть основан исключительно на формулировках документа. Если ответ невозможен из‑за отсутствия данных в документе — напиши: «В предоставленном документе нет сведений для ответа на этот вопрос».
Стиль ответа — деловой, без лишней воды. При наличии прямого основания в тексте — приведи цитату (с указанием пункта/раздела).
Если вопрос задан не по теме документа — вежливо верни диалог в русло документа. Сохраняй историю диалога и не повторяйся."""

SEARCH_VND_WELCOME = (
    "Документ загружен. Задайте вопрос по его содержанию — "
    "отвечу строго на основании текста ВНД."
)

SEARCH_VND_WELCOME_WITH_ANALYSIS = (
    "Документ и отчёт анализа подключены. Задайте вопрос по содержанию ВНД "
    "или по выявленным недостаткам из отчёта."
)

SEARCH_ANALYSIS_PROMPT_SUFFIX = """
При наличии отчёта анализа используй его для ответов на вопросы о выявленных недостатках, рисках и рекомендациях.
На вопросы о нормах и положениях ВНД отвечай по тексту документа."""

SEARCH_REPORT_PREFIXES = ("отчёт", "отчет", "report", "analysis_")
SEARCH_REPORT_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md"}


def _get_openai_client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY не установлен")
    return OpenAI(api_key=settings.openai_api_key)


def _get_fz_context(query: str, max_results: int = 3) -> str:
    """Релевантные фрагменты из базы ФЗ для уточнения ссылок в ВНД."""
    try:
        from vector_store import fz_store, init_vector_stores

        init_vector_stores()
        if not fz_store:
            return ""
        results = fz_store.search(query, n_results=max_results)
        if not results:
            return ""
        parts = ["=== СПРАВОЧНО: ФРАГМЕНТЫ ИЗ БАЗЫ ФЗ (только для пояснения ссылок в ВНД) ==="]
        for item in results:
            meta = item.get("metadata") or {}
            filename = meta.get("filename", "N/A")
            text = (item.get("document") or "")[:600]
            parts.append(f"Документ: {filename}\n{text}")
        return "\n\n".join(parts)
    except Exception as exc:
        logger.warning("Поиск в базе ФЗ: %s", exc)
        return ""


def ensure_search_folder() -> Path:
    folder = Path(settings.in_folder) / "search"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def save_search_analysis_upload(filename: str, content: bytes) -> dict:
    """Сохранить отчёт анализа для диалога поиска в IN/search/."""
    folder = ensure_search_folder()
    safe = os.path.basename(filename or "analysis")
    stem, ext = os.path.splitext(safe)
    stamped = f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{stem}{ext}"
    path = folder / stamped
    path.write_bytes(content)
    return {"filename": stamped, "file_path": str(path), "source": "search"}


def _normalize_name_for_match(name: str) -> str:
    stem = Path(name or "").stem.lower()
    stem = re.sub(r"^analysis_\d{8}_\d{6}_", "", stem)
    stem = re.sub(r"^main_\d{8}_\d{6}_", "", stem)
    stem = re.sub(r"^отчёт[_\s-]*", "", stem, flags=re.IGNORECASE)
    stem = re.sub(r"^отчет[_\s-]*", "", stem, flags=re.IGNORECASE)
    stem = re.sub(r"^report[_\s-]*", "", stem, flags=re.IGNORECASE)
    stem = re.sub(r"_\d{8}_\d{6}$", "", stem)
    stem = re.sub(r"[^\wа-яё\s\-]", " ", stem, flags=re.IGNORECASE)
    stem = re.sub(r"\s+", " ", stem).strip()
    return stem


def names_match(vnd_name: str, candidate_name: str) -> bool:
    """Проверить, относится ли имя файла отчёта к основному документу ВНД."""
    return _names_match(vnd_name, candidate_name)


def validate_analysis_for_main(main_filename: str, analysis_filename: str) -> None:
    """Убедиться, что отчёт анализа соответствует основному документу."""
    main_safe = os.path.basename((main_filename or "").strip())
    analysis_safe = os.path.basename((analysis_filename or "").strip())
    if not main_safe:
        raise ValueError("Не указан основной документ")
    if not analysis_safe:
        raise ValueError("Не указан отчёт анализа")
    if not names_match(main_safe, analysis_safe):
        raise ValueError(
            "Загруженный отчёт анализа не соответствует основному документу. "
            "По имени файлов они относятся к разным ВНД. "
            "Выберите отчёт, подготовленный именно по этому документу, "
            "или не загружайте отчёт — тогда анализ будет выполнен автоматически."
        )


def _names_match(vnd_name: str, candidate_name: str) -> bool:
    vnd_key = _normalize_name_for_match(vnd_name)
    cand_key = _normalize_name_for_match(candidate_name)
    if not vnd_key or not cand_key:
        return False
    if vnd_key == cand_key:
        return True
    if len(vnd_key) >= 5 and (vnd_key in cand_key or cand_key in vnd_key):
        return True
    vnd_tokens = {t for t in vnd_key.split() if len(t) >= 4}
    cand_tokens = {t for t in cand_key.split() if len(t) >= 4}
    if vnd_tokens and cand_tokens:
        overlap = len(vnd_tokens & cand_tokens) / max(len(vnd_tokens), 1)
        return overlap >= 0.5
    return False


def _is_analysis_report_file(path: Path) -> bool:
    if not path.is_file():
        return False
    if path.suffix.lower() not in SEARCH_REPORT_EXTENSIONS:
        return False
    name_lower = path.name.lower()
    if any(name_lower.startswith(prefix) for prefix in SEARCH_REPORT_PREFIXES):
        return True
    if "отчёт" in name_lower or "отчет" in name_lower:
        return True
    return name_lower.startswith("analysis_")


def _analysis_search_roots() -> List[tuple]:
    roots = [
        ("out", Path(settings.out_folder)),
        ("create", Path(settings.in_folder) / "create"),
        ("search", ensure_search_folder()),
    ]
    return roots


def find_analysis_candidates(vnd_filename: str) -> List[dict]:
    """Найти отчёты анализа, подходящие к выбранному ВНД."""
    safe_vnd = os.path.basename(vnd_filename or "")
    candidates: List[dict] = []

    for source, folder in _analysis_search_roots():
        if not folder.is_dir():
            continue
        for path in folder.iterdir():
            if not _is_analysis_report_file(path):
                continue
            if not _names_match(safe_vnd, path.name):
                continue
            try:
                mtime = path.stat().st_mtime
            except OSError:
                mtime = 0
            candidates.append(
                {
                    "filename": path.name,
                    "source": source,
                    "folder": str(folder),
                    "mtime": mtime,
                    "auto_matched": True,
                }
            )

    candidates.sort(key=lambda item: item.get("mtime", 0), reverse=True)
    return candidates


def resolve_analysis_text(filename: str, source: Optional[str] = None) -> tuple[str, str, str]:
    """Прочитать текст отчёта анализа из известной папки."""
    safe_name = os.path.basename((filename or "").strip())
    if not safe_name:
        raise ValueError("Укажите имя отчёта анализа")

    normalized_source = (source or "").lower().strip()
    path: Optional[Path] = None

    if normalized_source == "out":
        path = Path(settings.out_folder) / safe_name
    elif normalized_source == "create":
        path = Path(settings.in_folder) / "create" / safe_name
    elif normalized_source == "search":
        path = ensure_search_folder() / safe_name
    else:
        for src, folder in _analysis_search_roots():
            candidate = folder / safe_name
            if candidate.is_file():
                path = candidate
                normalized_source = src
                break

    if not path or not path.is_file():
        raise FileNotFoundError(f"Отчёт анализа не найден: {safe_name}")

    text = extract_full_text(str(path))[:50000]
    if not text.strip():
        raise ValueError("Не удалось извлечь текст из отчёта анализа")
    return text, safe_name, normalized_source or "out"


def load_vnd_document_text(source: str, filename: str) -> dict:
    """
    Загрузить текст ВНД для диалога.
    source: upload — файл из папки IN; database — из базы ВНД.
    """
    safe_name = os.path.basename((filename or "").strip())
    if not safe_name:
        raise ValueError("Укажите имя документа")

    normalized_source = (source or "").lower().strip()
    if normalized_source == "upload":
        file_path = Path(settings.in_folder) / safe_name
        if not file_path.is_file():
            raise FileNotFoundError(f"Файл не найден в папке загрузки: {safe_name}")
        text = extract_full_text(str(file_path))[:80000]
        if not text.strip():
            raise ValueError("Не удалось извлечь текст из загруженного файла")
        return {
            "filename": safe_name,
            "title": safe_name,
            "source": "upload",
            "text": text,
        }

    if normalized_source == "database":
        from vector_store import init_vector_stores, vnd_store

        init_vector_stores()
        if not vnd_store:
            raise RuntimeError("База ВНД не инициализирована")
        text = vnd_store.get_document_text_by_filename(safe_name)
        if not text or not text.strip():
            raise FileNotFoundError(f"Документ «{safe_name}» не найден в базе ВНД")
        return {
            "filename": safe_name,
            "title": safe_name,
            "source": "database",
            "text": text,
        }

    raise ValueError("source должен быть upload или database")


def load_search_session(
    source: str,
    filename: str,
    analysis_filename: Optional[str] = None,
    analysis_source: Optional[str] = None,
    auto_match_analysis: bool = True,
) -> dict:
    """Загрузить ВНД и при необходимости отчёт анализа (вручную или автоматически)."""
    result = load_vnd_document_text(source, filename)
    result.update(
        {
            "analysis_filename": None,
            "analysis_source": None,
            "analysis_text": "",
            "analysis_auto_matched": False,
            "analysis_candidates": [],
        }
    )

    candidates = find_analysis_candidates(filename)
    result["analysis_candidates"] = [
        {
            "filename": item["filename"],
            "source": item["source"],
        }
        for item in candidates
    ]

    if analysis_filename:
        text, afn, asrc = resolve_analysis_text(analysis_filename, analysis_source)
        result["analysis_text"] = text
        result["analysis_filename"] = afn
        result["analysis_source"] = asrc
        return result

    if auto_match_analysis and candidates:
        best = candidates[0]
        text, afn, asrc = resolve_analysis_text(best["filename"], best["source"])
        result["analysis_text"] = text
        result["analysis_filename"] = afn
        result["analysis_source"] = asrc
        result["analysis_auto_matched"] = True

    return result


def build_search_system_prompt(
    document_text: str,
    title: str,
    user_query: str = "",
    analysis_text: str = "",
) -> str:
    doc_excerpt = (document_text or "")[:14000]
    safe_title = (title or "ВНД").strip()
    fz_context = _get_fz_context(user_query or safe_title) if user_query else ""
    parts = [
        SEARCH_VND_SYSTEM_PROMPT,
        "",
        f"=== ВНД («{safe_title}») ===",
        doc_excerpt,
    ]
    analysis_excerpt = (analysis_text or "")[:12000]
    if analysis_excerpt.strip():
        parts.extend(
            [
                "",
                SEARCH_ANALYSIS_PROMPT_SUFFIX,
                "",
                "=== ОТЧЁТ АНАЛИЗА ===",
                analysis_excerpt,
            ]
        )
    if fz_context:
        parts.extend(["", fz_context])
    return "\n".join(parts)


def answer_search_vnd_question(
    document_text: str,
    title: str,
    messages: List[dict],
    user_message: str,
    analysis_text: str = "",
) -> dict:
    """Ответ на вопрос по ВНД с учётом истории диалога."""
    user_message = (user_message or "").strip()
    if not user_message:
        raise ValueError("Введите вопрос")
    if not (document_text or "").strip():
        raise ValueError("Текст документа отсутствует")

    history: List[dict] = []
    for item in messages or []:
        role = item.get("role")
        content = (item.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            history.append({"role": role, "content": content})

    system_prompt = build_search_system_prompt(
        document_text,
        title,
        user_message,
        analysis_text=analysis_text,
    )
    api_messages: List[dict] = [{"role": "system", "content": system_prompt}]
    api_messages.extend(history[-24:])
    api_messages.append({"role": "user", "content": user_message})

    client = _get_openai_client()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=api_messages,
        temperature=0.2,
        max_tokens=2000,
    )
    reply = (response.choices[0].message.content or "").strip()
    if not reply:
        reply = "Не удалось сформировать ответ. Попробуйте переформулировать вопрос."

    updated = history + [
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": reply},
    ]
    return {"reply": reply, "messages": updated}


def build_search_qa_dialog(messages: List[dict], title: str) -> tuple[bytes, str, str]:
    """Сформировать файл диалога в памяти."""
    has_user = any(
        (item.get("role") == "user" and (item.get("content") or "").strip())
        for item in (messages or [])
    )
    if not has_user:
        raise ValueError("В диалоге нет вопросов для сохранения")

    safe_title = re.sub(r'[<>:"/\\|?*]', "_", title or "ВНД")[:80]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"Диалог_поиск_{safe_title}_{timestamp}.txt"

    lines = [
        "ДИАЛОГ ПО ВНД (ПОИСК)",
        f"Документ: {title or 'ВНД'}",
        f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        "",
    ]
    for item in messages or []:
        role = item.get("role")
        content = (item.get("content") or "").strip()
        if not content:
            continue
        label = "Пользователь" if role == "user" else "Юрист"
        lines.append(f"{label}:")
        lines.append(content)
        lines.append("")

    return "\n".join(lines).strip().encode("utf-8") + b"\n", filename, "text/plain; charset=utf-8"
