"""
Блок анализа ВНД с использованием раздельных промптов агентов
"""
from vector_store import gost_store, fz_store, vnd_store
from openai import OpenAI
from config import settings
import json
import logging
from datetime import datetime
from pathlib import Path
import os
import re
from typing import Optional

# Импортируем промпты агентов
from prompts import (
    SYSTEM_ROLE,
    AGENT_ANALYST,
    AGENT_LAWYER,
    AGENT_COMPARATOR,
    AGENT_METHODIST,
    AGENT_REPORT_EDITOR,
    AGENT_COMMUNICATOR,
    get_stage_from_message,
    get_agent_prompt,
    STAGE_AGENTS
)

# Настройка логирования в файл
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOG_FILE = LOG_DIR / f"analiz_{datetime.now().strftime('%Y%m%d')}.log"

# Настройка логгера
logger = logging.getLogger("analiz")
logger.setLevel(logging.DEBUG)

# Очищаем существующие обработчики
logger.handlers.clear()

# Обработчик для файла
file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)

# Обработчик для консоли
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Формат логов
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

logger.info(f"Логирование инициализировано. Файл логов: {LOG_FILE}")


def fix_analysis_report_typos(text: str) -> str:
    """Исправить типовые обрезки и опечатки в тексте отчёта."""
    if not text:
        return text
    return re.sub(
        r"(?i)Требует\s+пересмот(?:р)?(?=[\s/|\]-]|$)",
        "Требует пересмотра",
        text,
    )


def get_relevant_context(
    query: str,
    max_results: int = 3,
    prioritize_vnd: bool = False,
    pre_analysis: dict = None,
) -> str:
    """Получить релевантный контекст из векторных баз
    
    Args:
        query: Поисковый запрос
        max_results: Максимальное количество результатов из каждой базы
        prioritize_vnd: Если True, приоритет отдается базе ВНД (для загруженных документов)
    """
    logger.info(f"Поиск контекста для запроса: {query[:100]}...")
    logger.info(f"Приоритет ВНД: {prioritize_vnd}")
    context_parts = []
    
    # Инициализируем векторные базы, если они не инициализированы
    from vector_store import init_vector_stores, gost_store, fz_store, vnd_store
    try:
        init_vector_stores()
        logger.debug("Векторные базы инициализированы")
    except Exception as e:
        logger.error(f"Ошибка инициализации векторных баз: {e}", exc_info=True)
    
    from pre_analysis import is_law_document_relevant

    def _include_law_result(result: dict) -> bool:
        if not pre_analysis:
            return True
        filename = result["metadata"].get("filename", result["metadata"].get("source", "N/A"))
        return is_law_document_relevant(str(filename), result.get("document", ""), pre_analysis)

    # Если приоритет у ВНД (работаем с загруженным документом), ищем сначала там
    if prioritize_vnd:
        try:
            if vnd_store:
                logger.debug("Поиск в базе ВНД (ПРИОРИТЕТ)...")
                vnd_results = vnd_store.search(query, n_results=max_results)
                if vnd_results:
                    logger.info(f"Найдено {len(vnd_results)} результатов в базе ВНД")
                    context_parts.append("=== ВНУТРЕННИЙ НОРМАТИВНЫЙ ДОКУМЕНТ ===")
                    for result in vnd_results:
                        filename = result['metadata'].get('filename', result['metadata'].get('source', 'N/A'))
                        source_path = result['metadata'].get('source', '')
                        
                        # Получаем дату создания файла
                        file_date_info = ""
                        if source_path:
                            try:
                                file_path = Path(source_path)
                                if file_path.exists():
                                    # Получаем дату создания файла
                                    creation_time = os.path.getctime(file_path)
                                    creation_date = datetime.fromtimestamp(creation_time)
                                    file_date_info = f"\n📅 Дата создания файла: {creation_date.strftime('%d.%m.%Y')}"
                                    logger.debug(f"Дата создания файла {filename}: {creation_date}")
                            except Exception as e:
                                logger.warning(f"Не удалось получить дату создания файла: {e}")
                        
                        from vnd_masking import mask_vnd_sensitive_data

                        masked_doc = mask_vnd_sensitive_data(result["document"][:500])
                        context_parts.append(f"📄 Документ: {filename}{file_date_info}")
                        context_parts.append(f"Текст: {masked_doc}")
                        context_parts.append("")
                else:
                    logger.warning("В базе ВНД результатов не найдено")
            else:
                logger.warning("База ВНД не инициализирована")
        except Exception as e:
            logger.error(f"Ошибка поиска в базе ВНД: {e}", exc_info=True)
    
    # Ищем в базе ФЗ (основной источник)
    try:
        if fz_store:
            logger.debug("Поиск в базе ФЗ...")
            fz_results = fz_store.search(query, n_results=max_results)
            if fz_results:
                logger.info(f"Найдено {len(fz_results)} результатов в базе ФЗ")
                context_parts.append("=== ФЕДЕРАЛЬНЫЕ ЗАКОНЫ ===")
                added = 0
                for result in fz_results:
                    if not _include_law_result(result):
                        continue
                    context_parts.append(f"Документ: {result['metadata'].get('filename', 'N/A')}")
                    context_parts.append(f"Текст: {result['document'][:500]}")
                    context_parts.append("")
                    added += 1
                if added == 0 and context_parts[-1].startswith("==="):
                    context_parts.pop()
            else:
                logger.debug("В базе ФЗ результатов не найдено")
        else:
            logger.warning("База ФЗ не инициализирована")
    except Exception as e:
        logger.error(f"Ошибка поиска в базе ФЗ: {e}", exc_info=True)
    
    # Если НЕ приоритет ВНД, ищем в базе ВНД после ФЗ
    if not prioritize_vnd:
        try:
            if vnd_store:
                logger.debug("Поиск в базе ВНД...")
                vnd_results = vnd_store.search(query, n_results=max_results)
                if vnd_results:
                    logger.info(f"Найдено {len(vnd_results)} результатов в базе ВНД")
                    context_parts.append("=== ВНУТРЕННИЕ ДОКУМЕНТЫ ===")
                    from vnd_masking import mask_vnd_sensitive_data

                    for result in vnd_results:
                        masked_doc = mask_vnd_sensitive_data(result["document"][:500])
                        context_parts.append(f"Документ: {result['metadata'].get('filename', 'N/A')}")
                        context_parts.append(f"Текст: {masked_doc}")
                        context_parts.append("")
                else:
                    logger.debug("В базе ВНД результатов не найдено")
        except Exception as e:
            logger.warning(f"Ошибка поиска в базе ВНД: {e}")
    
    # Ищем в базе ГОСТ (дополнительно)
    try:
        if gost_store:
            logger.debug("Поиск в базе ГОСТ...")
            gost_results = gost_store.search(query, n_results=max_results)
            if gost_results:
                logger.info(f"Найдено {len(gost_results)} результатов в базе ГОСТ")
                context_parts.append("=== ГОСТ И СТАНДАРТЫ ===")
                added = 0
                for result in gost_results:
                    if not _include_law_result(result):
                        continue
                    context_parts.append(f"Документ: {result['metadata'].get('filename', 'N/A')}")
                    context_parts.append(f"Текст: {result['document'][:500]}")
                    context_parts.append("")
                    added += 1
                if added == 0 and context_parts[-1].startswith("==="):
                    context_parts.pop()
            else:
                logger.debug("В базе ГОСТ результатов не найдено")
    except Exception as e:
        logger.warning(f"Ошибка поиска в базе ГОСТ: {e}")
    
    if context_parts:
        result = "\n".join(context_parts)
        logger.info(f"Контекст получен, длина: {len(result)} символов")
        return result
    else:
        logger.warning("Контекст не найден")
        return "Контекст не найден в базах знаний."


def format_history(history: list, max_messages: int = 6) -> str:
    """Форматировать историю диалога для промпта
    
    Args:
        history: Список сообщений
        max_messages: Максимальное количество сообщений для включения
    """
    if not history:
        return "История пуста. Это начало диалога."
    
    # Берём последние сообщения
    recent = history[-max_messages:] if len(history) > max_messages else history
    
    history_text = []
    for msg in recent:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        # Ограничиваем длину сообщения
        if len(content) > 800:
            content = content[:800] + "..."
        
        role_name = "Клиент" if role == "user" else "Система"
        history_text.append(f"{role_name}: {content}")
    
    return "\n\n".join(history_text)


def resolve_vnd_text(message: dict) -> Optional[str]:
    """Получить обезличенный текст ВНД из запроса или из файла в папке IN."""
    from vnd_masking import mask_vnd_sensitive_data

    inline = message.get("vnd_text")
    if inline:
        return mask_vnd_sensitive_data(str(inline))[:80000]

    filename = message.get("vnd_filename")
    if not filename:
        return None

    from document_loader import extract_full_text

    safe_name = os.path.basename(str(filename))
    file_path = Path(settings.in_folder) / safe_name
    if not file_path.is_file():
        logger.warning("Файл ВНД не найден: %s", file_path)
        return None

    try:
        text = extract_full_text(str(file_path), apply_vnd_mask=True)
        return mask_vnd_sensitive_data(text)[:80000] if text else None
    except Exception as exc:
        logger.warning("Не удалось извлечь текст из %s: %s", file_path, exc)
        return None


def analyze_vnd(
    user_message: str,
    history: list = None,
    vnd_text: str = None,
    force_analysis: bool = False,
    pre_analysis: dict = None,
) -> str:
    """Провести анализ ВНД с использованием раздельных промптов агентов
    
    Args:
        user_message: Сообщение пользователя
        history: История диалога
        vnd_text: Текст загруженного ВНД документа
        force_analysis: Пропустить уточняющие вопросы и выполнить анализ
        pre_analysis: Параметры этапа 1 (сфера, собственность, области законодательства)
    """
    logger.info("=" * 80)
    logger.info("НАЧАЛО АНАЛИЗА ВНД (раздельные агенты)")
    logger.info(f"Сообщение: {user_message[:200]}...")
    logger.info(f"История: {len(history) if history else 0} сообщений")
    logger.info(f"ВНД текст: {'да' if vnd_text else 'нет'}")
    
    try:
        if history is None:
            history = []
        
        # Проверяем API ключ
        if not settings.openai_api_key:
            error_msg = "OPENAI_API_KEY не установлен"
            logger.error(error_msg)
            return f"❌ {error_msg}\n\nУстановите API ключ в файле .env"
        
        logger.debug(f"API ключ: {settings.openai_api_key[:10]}...")
        
        # Инициализируем векторные базы
        from vector_store import init_vector_stores
        try:
            init_vector_stores()
            logger.debug("Векторные базы инициализированы")
        except Exception as e:
            logger.error(f"Ошибка инициализации баз: {e}")
        
        # Параметры этапа 1 или уточняющий диалог (legacy)
        from pre_analysis import format_stage1_context

        clarification_summary = ""
        if pre_analysis:
            clarification_summary = format_stage1_context(pre_analysis)
            logger.info("Используются параметры этапа 1: %s", pre_analysis)
        elif not force_analysis:
            from clarification import (
                should_clarify,
                process_clarification,
                format_clarification_summary,
                is_clarification_answer,
            )

            clarification_summary = format_clarification_summary(
                history,
                user_message,
                include_pending_answer=is_clarification_answer(history, user_message),
            )

            if should_clarify(history, user_message):
                logger.info("Этап уточняющих вопросов")
                clarification_result = process_clarification(
                    user_message=user_message,
                    history=history,
                    vnd_text=vnd_text,
                    get_context=lambda q: get_relevant_context(
                        q, max_results=2, prioritize_vnd=bool(vnd_text)
                    ),
                    format_history=format_history,
                )
                if not clarification_result.get("clarification_complete"):
                    logger.info(
                        "Задан уточняющий вопрос %s/%s",
                        clarification_result.get("question_index"),
                        clarification_result.get("max_questions"),
                    )
                    return clarification_result

                logger.info("Уточнения завершены, анализ будет выполнен отдельным запросом")
                return clarification_result

        if force_analysis and not pre_analysis:
            from clarification import is_start_message

            if is_start_message(user_message):
                user_message = (
                    "Приступи к правовому анализу загруженного ВНД с учётом уточнений клиента."
                )

        stage = get_stage_from_message(user_message, history)
        logger.info(f"Определён этап анализа: {stage}")
        
        # Получаем промпт для текущего агента
        agent_prompt = get_agent_prompt(stage)
        logger.info(f"Выбран агент для этапа: {stage}")
        
        # Определяем приоритет ВНД
        prioritize_vnd = bool(vnd_text)
        if not prioritize_vnd and history:
            for msg in history:
                if msg.get("vnd_text") or "загружен" in str(msg.get("content", "")).lower():
                    prioritize_vnd = True
                    break
        
        # Формируем запрос для поиска контекста
        query = user_message if user_message else "анализ документа"
        if vnd_text:
            query = vnd_text[:300] + " " + query
        
        # Получаем контекст
        context = get_relevant_context(
            query,
            max_results=3,
            prioritize_vnd=prioritize_vnd,
            pre_analysis=pre_analysis,
        )

        if clarification_summary:
            header = (
                "=== ПАРАМЕТРЫ ЭТАПА 1 (учитывать при анализе) ==="
                if pre_analysis
                else "=== УТОЧНЕНИЯ ОТ КЛИЕНТА (до анализа) ==="
            )
            context += f"\n\n{header}\n{clarification_summary}"
        
        # Ограничиваем контекст
        max_context = 3000
        if len(context) > max_context:
            context = context[:max_context] + "\n[Контекст сокращён]"
        
        # Форматируем историю
        history_text = format_history(history)
        if clarification_summary:
            header = (
                "=== ПАРАМЕТРЫ ЭТАПА 1 (учитывать при анализе) ==="
                if pre_analysis
                else "=== УТОЧНЕНИЯ ОТ КЛИЕНТА (учитывать при анализе) ==="
            )
            history_text += f"\n\n{header}\n{clarification_summary}"
        
        # Формируем промпт агента
        user_content = user_message if user_message else "Начни работу."
        
        formatted_prompt = agent_prompt.format(
            context=context,
            history=history_text,
            user_message=user_content
        )
        
        # Комбинируем системную роль и промпт агента
        system_prompt = f"{SYSTEM_ROLE}\n\n{formatted_prompt}"
        
        logger.info(f"System prompt: {len(system_prompt)} символов")
        logger.info(f"Этап: {stage}")
        logger.info("Отправка запроса к OpenAI...")
        
        # Вызываем OpenAI
        client = OpenAI(api_key=settings.openai_api_key)
        
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            result = fix_analysis_report_typos(response.choices[0].message.content or "")
            logger.info(f"Ответ получен: {len(result)} символов")
            logger.info("=" * 80)
            logger.info("АНАЛИЗ ЗАВЕРШЕН УСПЕШНО")
            logger.info("=" * 80)
            return {
                "content": result,
                "phase": "analysis",
                "analysis_started": True,
            } if (force_analysis or pre_analysis) else result
            
        except Exception as api_error:
            logger.error(f"Ошибка OpenAI API: {api_error}", exc_info=True)
            raise
        
    except Exception as e:
        import traceback
        error_detail = str(e)
        logger.error("=" * 80)
        logger.error("ОШИБКА ПРИ АНАЛИЗЕ")
        logger.error(f"Тип: {type(e).__name__}")
        logger.error(f"Сообщение: {error_detail}")
        logger.error(traceback.format_exc())
        logger.error("=" * 80)
        
        if "api_key" in error_detail.lower() or "authentication" in error_detail.lower():
            return f"❌ Ошибка аутентификации OpenAI API.\n\nПроверьте API ключ в файле .env"
        elif "rate limit" in error_detail.lower():
            return f"❌ Превышен лимит запросов. Подождите и попробуйте снова."
        elif "insufficient_quota" in error_detail.lower():
            return f"❌ Недостаточно средств на счету OpenAI API."
        else:
            from error_messages import humanize_error
            return f"❌ {humanize_error(e, 'analysis')}"
