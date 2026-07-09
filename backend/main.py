"""
FastAPI приложение для проверки и создания внутренней нормативной документации
"""
import os
# Отключаем телеметрию ChromaDB до импорта других модулей
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY_DISABLED"] = "1"

from fastapi import FastAPI, HTTPException, UploadFile, File, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response
from typing import Optional
from pydantic import BaseModel
import json
import logging
import re
import time
from urllib.parse import quote

# Подавляем ошибки телеметрии ChromaDB в логах
logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL)
logging.getLogger("posthog").setLevel(logging.CRITICAL)

from database import init_db, Dialog
from zagruzka import (
    initialize_system,
    check_unfinished_dialogs,
    get_dialog_by_id,
    save_dialog,
    update_dialog,
    delete_dialog
)
from analiz import analyze_vnd, resolve_vnd_text
from vector_store import init_vector_stores
from document_loader import process_folder
from config import settings
from error_messages import humanize_error, http_detail

# Определяем путь к корню проекта (родительская директория от backend)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

app = FastAPI(title="НейроКонсультант по ВНД")


@app.exception_handler(HTTPException)
async def handle_http_exception(request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, list):
        detail = "; ".join(str(item) for item in detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": humanize_error(str(detail)),
            "status_code": exc.status_code,
        },
    )


@app.exception_handler(Exception)
async def handle_unhandled_exception(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        raise exc
    import traceback
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={
            "detail": humanize_error(exc),
            "status_code": 500,
        },
    )

# CORS для работы с frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Инициализация БД при старте
@app.on_event("startup")
async def startup_event():
    try:
        from path_config import apply_paths_to_settings
        paths = apply_paths_to_settings()
        print(f"Папка данных: {paths.get('data_root')}")
        print(f"ГОСТ (FZYur): {paths.get('fzyur_folder')}")
    except Exception as e:
        print(f"⚠️  Ошибка загрузки config.cfg: {e}")

    try:
        init_db()
        print("База данных инициализирована")
        
        # Проверяем, что таблица dialogs существует
        from database import engine, Dialog
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        if "dialogs" not in tables:
            print("Предупреждение: таблица dialogs не найдена, пересоздаем...")
            init_db()
        else:
            print("Таблица dialogs существует")
    except Exception as e:
        import traceback
        print(f"Ошибка инициализации БД: {e}")
        print(traceback.format_exc())
    
    # Инициализируем векторные базы при старте
    try:
        from vector_store import init_vector_stores, gost_store, fz_store, vnd_store
        bases_info = init_vector_stores()
        print("Векторные базы инициализированы")
        
        # Показываем информацию о логах
        try:
            from analiz import LOG_FILE
            print(f"Файл логов анализа: {LOG_FILE}")
        except:
            pass
        
        # Проверяем, нужно ли загрузить документы в базы
        # ФЗ - обязательная база, ГОСТ - опциональная
        need_indexing_fz = False
        need_indexing_gost = False
        need_indexing_vnd = False
        
        if not bases_info.get("fz", {}).get("ready", False):
            print("⚠️  База ФЗ пуста, требуется индексация (ФЗ - основной источник)")
            need_indexing_fz = True
        
        if not bases_info.get("gost", {}).get("ready", False):
            print("ℹ️  База ГОСТ пуста (опционально, не критично для анализа)")
            need_indexing_gost = True
        
        if not bases_info.get("vnd", {}).get("ready", False):
            print("ℹ️  База ВНД пуста (для анализа загруженных документов)")
            need_indexing_vnd = True
        
        # Автоматически загружаем документы, если базы пустые
        if need_indexing_fz or need_indexing_gost or need_indexing_vnd:
            print("Начинаем автоматическую индексацию документов...")
            try:
                from document_loader import create_index_bases
                results = create_index_bases()
                print("Результаты индексации:")
                for base_name, result in results.items():
                    if result.get("status") == "success":
                        files_count = result.get('files_processed', 0)
                        chunks_count = result.get('total_chunks', 0)
                        if files_count > 0:
                            print(f"  ✓ {base_name}: обработано {files_count} файлов, {chunks_count} чанков")
                        else:
                            print(f"  ⚠ {base_name}: файлы не обработаны ({result.get('message', 'нет файлов')})")
                    else:
                        status_icon = "⚠" if base_name == "gost" else "✗"
                        print(f"  {status_icon} {base_name}: {result.get('message', 'ошибка')}")
                
                # Проверяем критичность
                if not results.get("fz", {}).get("status") == "success" or results.get("fz", {}).get("files_processed", 0) == 0:
                    print("\n⚠️  ВНИМАНИЕ: База ФЗ не загружена или пуста!")
                    print("   Анализ может работать некорректно без федеральных законов.")
                    print("   Убедитесь, что в папке FZ есть файлы для индексации.")
            except Exception as e:
                print(f"Ошибка при автоматической индексации: {e}")
                import traceback
                traceback.print_exc()
                print("Вы можете запустить индексацию вручную через API: POST /api/bases/reindex")
    except Exception as e:
        print(f"Ошибка инициализации векторных баз: {e}")

# Статические файлы для frontend
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
async def root():
    """Главная страница - отдаем frontend"""
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "НейроКонсультант по ВНД API"}

@app.get("/favicon.ico")
async def favicon():
    """Обработка запроса favicon"""
    raise HTTPException(status_code=404, detail="Favicon not found")

@app.get("/analiz")
async def analiz_page():
    """Страница анализа ВНД"""
    analiz_path = os.path.join(FRONTEND_DIR, "analiz.html")
    if os.path.exists(analiz_path):
        return FileResponse(analiz_path)
    raise HTTPException(status_code=404, detail="Страница не найдена")

@app.get("/search")
async def search_page():
    """Страница поиска по ВНД"""
    search_path = os.path.join(FRONTEND_DIR, "search.html")
    if os.path.exists(search_path):
        return FileResponse(search_path)
    raise HTTPException(status_code=404, detail="Страница не найдена")

@app.get("/create")
async def create_page():
    """Страница помощника в создании ВНД"""
    create_path = os.path.join(FRONTEND_DIR, "create.html")
    if os.path.exists(create_path):
        return FileResponse(create_path)
    raise HTTPException(status_code=404, detail="Страница не найдена")

# API endpoints

@app.get("/api/init")
async def init():
    """Инициализация системы: создание баз и проверка диалогов"""
    try:
        result = initialize_system()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=http_detail(e, "init"))

@app.get("/api/dialogs/unfinished")
async def get_unfinished_dialogs():
    """Получить список незавершенных диалогов"""
    try:
        dialogs = check_unfinished_dialogs()
        return {"dialogs": dialogs, "count": len(dialogs)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=http_detail(e, "dialog_load"))

@app.get("/api/dialogs/{dialog_id}")
async def get_dialog(dialog_id: int):
    """Получить диалог по ID"""
    try:
        dialog = get_dialog_by_id(dialog_id)
        if not dialog:
            raise HTTPException(status_code=404, detail="Диалог не найден")
        return dialog
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=http_detail(e, "dialog_load"))

@app.post("/api/dialogs")
async def create_dialog(vnd_name: Optional[str] = None):
    """Создать новый диалог"""
    try:
        print(f"Создание диалога: vnd_name={vnd_name}")
        dialog_id = save_dialog(vnd_name or "ВНД анализ", [])
        print(f"Диалог создан успешно: ID={dialog_id}")
        return {"dialog_id": dialog_id, "message": "Диалог создан"}
    except Exception as e:
        import traceback
        error_detail = str(e)
        print(f"Ошибка при создании диалога: {error_detail}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=http_detail(e, "dialog_create"))

@app.post("/api/dialogs/{dialog_id}/message")
async def send_message(dialog_id: int, message: dict):
    """Отправить сообщение в диалог и получить ответ"""
    try:
        # Получаем диалог
        dialog = get_dialog_by_id(dialog_id)
        if not dialog:
            raise HTTPException(status_code=404, detail="Диалог не найден")
        
        # Добавляем сообщение пользователя
        messages = dialog["messages"]
        user_entry = {
            "role": "user",
            "content": message.get("content", ""),
        }
        for prev_msg in reversed(messages):
            if prev_msg.get("role") == "assistant":
                if prev_msg.get("phase") == "clarification":
                    user_entry["phase"] = "clarification"
                    if prev_msg.get("question_index"):
                        user_entry["question_index"] = prev_msg.get("question_index")
                break
        messages.append(user_entry)
        
        # Текст ВНД загружается с диска или из запроса, в историю не сохраняется
        vnd_text = resolve_vnd_text(message)
        force_analysis = bool(message.get("start_analysis"))
        print(f"Запрос на анализ: dialog_id={dialog_id}, message_length={len(message.get('content', ''))}, force_analysis={force_analysis}")
        try:
            analysis_result = analyze_vnd(
                user_message=message.get("content", ""),
                history=messages[:-1],  # История без последнего сообщения
                vnd_text=vnd_text,
                force_analysis=force_analysis,
            )
            if isinstance(analysis_result, dict):
                response = analysis_result.get("content", "")
                assistant_meta = {
                    key: value
                    for key, value in analysis_result.items()
                    if key != "content"
                }
            else:
                response = analysis_result
                assistant_meta = {}
            print(f"Анализ завершен, длина ответа: {len(response)} символов")
        except Exception as e:
            import traceback
            error_detail = str(e)
            print(f"Ошибка при анализе: {error_detail}")
            print(traceback.format_exc())
            # Логируем в файл через модуль analiz
            try:
                from analiz import logger
                logger.error(f"Ошибка в API endpoint: {error_detail}", exc_info=True)
            except:
                pass
            response = f"❌ {http_detail(e, 'analysis')}"
            assistant_meta = {}

        # Добавляем ответ системы
        assistant_entry = {
            "role": "assistant",
            "content": response,
        }
        assistant_entry.update(assistant_meta)
        messages.append(assistant_entry)
        
        # Обновляем диалог
        is_completed = message.get("complete", False)
        update_dialog(dialog_id, messages, is_completed)
        
        return {
            "response": response,
            "dialog_id": dialog_id,
            "messages": messages,
            "phase": assistant_meta.get("phase"),
            "question_index": assistant_meta.get("question_index"),
            "max_questions": assistant_meta.get("max_questions"),
            "clarification_complete": assistant_meta.get("clarification_complete", False),
            "analysis_started": assistant_meta.get("analysis_started", False),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=http_detail(e, "analysis"))

@app.post("/api/dialogs/{dialog_id}/continue")
async def continue_dialog(dialog_id: int):
    """Продолжить незавершенный диалог"""
    try:
        dialog = get_dialog_by_id(dialog_id)
        if not dialog:
            raise HTTPException(status_code=404, detail="Диалог не найден")
        return dialog
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=http_detail(e, "dialog_load"))

@app.delete("/api/dialogs/{dialog_id}")
async def remove_dialog(dialog_id: int):
    """Удалить диалог"""
    try:
        print(f"Запрос на удаление диалога: ID={dialog_id}")
        success = delete_dialog(dialog_id)
        if success:
            print(f"Диалог {dialog_id} успешно удален")
            return {"message": "Диалог успешно удален", "dialog_id": dialog_id}
        else:
            raise HTTPException(status_code=404, detail="Диалог не найден")
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = str(e)
        print(f"Ошибка при удалении диалога: {error_detail}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=http_detail(e, "dialog_delete"))


def _save_uploaded_file(in_folder: str, filename: str, content: bytes) -> tuple[str, str, Optional[str]]:
    """
    Сохранить загруженный файл в папку IN.
    Возвращает (путь, имя файла, предупреждение или None).
    """
    os.makedirs(in_folder, exist_ok=True)
    safe_name = os.path.basename(filename)
    target_path = os.path.join(in_folder, safe_name)
    temp_path = os.path.join(in_folder, f".upload_{int(time.time() * 1000)}_{safe_name}")

    with open(temp_path, "wb") as temp_file:
        temp_file.write(content)

    try:
        if os.path.exists(target_path):
            os.remove(target_path)
        os.replace(temp_path, target_path)
        return target_path, safe_name, None
    except PermissionError:
        if os.path.exists(temp_path):
            stem, ext = os.path.splitext(safe_name)
            alt_name = f"{stem}_{int(time.time())}{ext}"
            alt_path = os.path.join(in_folder, alt_name)
            os.replace(temp_path, alt_path)
            warning = (
                f"Файл «{safe_name}» открыт в другой программе (например, Adobe Acrobat). "
                f"Сохранён как «{alt_name}». Закройте исходный файл, если нужно перезаписать его."
            )
            return alt_path, alt_name, warning
        raise


def _file_download_response(content: bytes, filename: str, media_type: str) -> Response:
    """Ответ для скачивания файла в браузере."""
    # Заголовки HTTP кодируются в latin-1: fallback-имя только ASCII.
    ascii_name = re.sub(r"[^A-Za-z0-9._\-]", "_", filename or "") or "download"
    if ascii_name in ("download", "_", "."):
        ext = ".txt" if (filename or "").lower().endswith(".txt") else ""
        ascii_name = f"download{ext}"
    encoded_name = quote(filename or ascii_name, safe="")
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": (
                f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{encoded_name}'
            ),
        },
    )


@app.post("/api/upload/vnd")
async def upload_vnd(file: UploadFile = File(...)):
    """Загрузить ВНД для анализа"""
    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail="Файл не выбран")

        content = await file.read()
        return _handle_vnd_upload(file.filename, content)
    except HTTPException:
        raise
    except PermissionError:
        raise HTTPException(
            status_code=409,
            detail=(
                "Не удалось сохранить файл: он открыт в другой программе "
                "(часто Adobe Acrobat). Закройте PDF и повторите загрузку."
            ),
        )
    except Exception as e:
        import traceback
        error_detail = str(e)
        print(f"Ошибка при загрузке файла: {error_detail}")
        print(traceback.format_exc())
        if (
            isinstance(e, PermissionError)
            or "Permission denied" in error_detail
            or "WinError 32" in error_detail
            or "being used by another process" in error_detail.lower()
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Не удалось сохранить файл: он открыт в другой программе "
                    "(часто Adobe Acrobat). Закройте PDF и повторите загрузку."
                ),
            )
        raise HTTPException(status_code=500, detail=http_detail(e, "upload"))


def _handle_vnd_upload(original_filename: str, content: bytes) -> dict:
    from federal_refs import clear_session_federal_refs_result

    clear_session_federal_refs_result()

    file_path, saved_filename, save_warning = _save_uploaded_file(
        settings.in_folder,
        original_filename,
        content,
    )

    print(f"Файл сохранен: {file_path}")
    if save_warning:
        print(f"Предупреждение при сохранении: {save_warning}")

    from vector_store import vnd_store, init_vector_stores

    if not vnd_store:
        print("Векторная база не инициализирована, инициализируем...")
        init_vector_stores()
        from vector_store import vnd_store as vnd_store_check
        if not vnd_store_check:
            print("Ошибка: не удалось инициализировать векторную базу ВНД")
            return {
                "message": "Файл загружен, но векторная база не инициализирована",
                "filename": saved_filename,
                "result": {
                    "status": "error",
                    "message": "Векторная база ВНД не инициализирована. Файл сохранен, но не обработан.",
                    "files_processed": 0,
                    "total_chunks": 0,
                },
            }
        vnd_store = vnd_store_check

    print(f"Векторная база готова: {vnd_store is not None}")

    from document_loader import process_single_file

    print(f"Начинаем обработку файла: {file_path}")
    print(f"Векторная база ВНД готова: {vnd_store is not None}")

    try:
        before_count = vnd_store.get_collection_info()["count"]
        print(f"Документов в базе ВНД до обработки: {before_count}")
    except Exception:
        before_count = 0

    result = process_single_file(file_path, vnd_store, "vnd")
    print(f"Обработка завершена. Результат: {result}")

    try:
        after_count = vnd_store.get_collection_info()["count"]
        print(f"Документов в базе ВНД после обработки: {after_count}")
        if after_count > before_count:
            print(f"✓ Документ успешно добавлен в базу ВНД (+{after_count - before_count} фрагментов)")
        else:
            print("⚠️  Внимание: количество документов не изменилось")
    except Exception as e:
        print(f"⚠️  Не удалось проверить состояние базы: {e}")

    print(f"Результат обработки файла: {result}")

    return {
        "message": "Файл загружен и обработан",
        "filename": saved_filename,
        "file_path": file_path,
        "warning": save_warning,
        "result": result,
    }


def _tkinter_browse_vnd_file(initial_dir: str) -> Optional[str]:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        return None

    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass
    selected = filedialog.askopenfilename(
        parent=root,
        initialdir=initial_dir,
        title="Выберите документ ВНД",
        filetypes=[
            ("Документы ВНД", "*.pdf *.docx *.doc *.txt"),
            ("Все файлы", "*.*"),
        ],
    )
    root.destroy()
    return selected or None


@app.post("/api/files/browse-vnd")
async def browse_vnd_file():
    """Локальный Windows: диалог выбора файла, стартовая папка IN."""
    if os.name != "nt":
        raise HTTPException(
            status_code=501,
            detail="Диалог выбора файла доступен только на локальном Windows",
        )

    try:
        from pathlib import Path
        import asyncio

        from path_config import apply_paths_to_settings

        paths = apply_paths_to_settings()
        initial_dir = paths["in_folder"]
        Path(initial_dir).mkdir(parents=True, exist_ok=True)

        selected = await asyncio.to_thread(_tkinter_browse_vnd_file, initial_dir)
        if not selected:
            return {"cancelled": True}

        with open(selected, "rb") as handle:
            content = handle.read()
        if not content:
            raise HTTPException(status_code=400, detail="Выбранный файл пустой")

        return _handle_vnd_upload(os.path.basename(selected), content)
    except HTTPException:
        raise
    except PermissionError:
        raise HTTPException(
            status_code=409,
            detail=(
                "Не удалось прочитать файл: он открыт в другой программе. "
                "Закройте файл и повторите выбор."
            ),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=http_detail(e, "upload"))


class DetectReferencesRequest(BaseModel):
    filename: Optional[str] = ""


class DownloadFederalRequest(BaseModel):
    references: list


class Stage1Request(BaseModel):
    vnd_filename: Optional[str] = ""
    vnd_name: Optional[str] = ""


class AnalyzeVndRequest(BaseModel):
    vnd_filename: Optional[str] = ""
    vnd_name: Optional[str] = ""
    stage1: dict


class CreateStage1Request(BaseModel):
    main_filename: Optional[str] = ""
    vnd_name: Optional[str] = ""


class CreateReworkRequest(BaseModel):
    main_filename: str
    analysis_filename: Optional[str] = ""
    vnd_name: Optional[str] = ""
    stage1: Optional[dict] = None
    analysis_text: Optional[str] = None


class CreateReworkAnalyzeRequest(BaseModel):
    main_filename: str
    vnd_name: Optional[str] = ""
    stage1: dict


class CreateReworkGenerateRequest(BaseModel):
    main_filename: str
    analysis_text: str
    vnd_name: Optional[str] = ""
    stage1: Optional[dict] = None
    analysis_meta: Optional[dict] = None


class CreateNewStage1Request(BaseModel):
    activity_sphere: str
    ownership_form: str
    legal_areas_text: str


class CreateNewAnalyzeRequest(BaseModel):
    document_name: Optional[str] = ""
    document_topic: Optional[str] = ""
    legal_area: Optional[str] = ""
    legal_area_custom: Optional[str] = ""
    activity_sphere: Optional[str] = ""
    ownership_form: Optional[str] = ""
    state_secret: Optional[str] = ""
    employees_count: Optional[str] = ""
    branches: Optional[str] = ""
    target_audience: Optional[str] = ""
    target_audience_custom: Optional[str] = ""
    followup_answers: Optional[dict] = None


class CreateNewGenerateRequest(BaseModel):
    form: dict
    analysis: str
    laws: Optional[list] = None
    download_result: Optional[dict] = None


class CreateSaveRequest(BaseModel):
    document: str
    title: Optional[str] = "ВНД"
    format: Optional[str] = "txt"
    mode: Optional[str] = "new"
    persist_only: Optional[bool] = False


class CreateQAMessageRequest(BaseModel):
    mode: str
    document: str
    title: Optional[str] = "ВНД"
    messages: Optional[list] = None
    user_message: str


class CreateQASaveRequest(BaseModel):
    mode: str
    title: Optional[str] = "ВНД"
    messages: list
    persist_only: Optional[bool] = False


class ReportSaveRequest(BaseModel):
    report_name: Optional[str] = "Отчёт"
    content: Optional[str] = ""
    messages: Optional[list] = None
    persist_only: Optional[bool] = False
    title: Optional[str] = ""
    summary_html: Optional[str] = ""


class WorkFolderRequest(BaseModel):
    work_folder: str


class BrowseFolderRequest(BaseModel):
    initial_dir: Optional[str] = ""


UPLOAD_TARGET_FOLDERS = {
    "IN": "in_folder",
    "FZYur": "fzyur_folder",
    "FZ": "fz_folder",
    "OUT": "out_folder",
    "new-doc": "new_doc_folder",
}


@app.get("/api/vnd/latest-file")
async def get_latest_vnd_file():
    """Получить имя последнего загруженного ВНД из папки IN."""
    try:
        from federal_refs import find_vnd_file

        latest = find_vnd_file()
        return {
            "filename": latest.name,
            "file_path": str(latest),
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=http_detail(e, "upload"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=http_detail(e, "upload"))


@app.post("/api/vnd/detect-references")
async def detect_vnd_references(request: DetectReferencesRequest):
    """Найти ссылки на федеральные документы в загруженном ВНД."""
    try:
        from federal_refs import detect_federal_references_from_file, find_vnd_file

        filename = (request.filename or "").strip()
        try:
            file_path = find_vnd_file(filename)
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=http_detail(e, "references"))

        result = detect_federal_references_from_file(str(file_path))
        result["filename"] = file_path.name
        return result
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=http_detail(e, "references"))

@app.get("/api/vnd/federal-references-session")
async def get_federal_references_session():
    """Получить сохранённый результат поиска федеральных ссылок текущей сессии."""
    from federal_refs import get_session_federal_refs_result

    result = get_session_federal_refs_result()
    if not result:
        return {"status": "empty", "message": "Результат поиска ссылок не сохранён"}
    return {"status": "success", "result": result}


@app.delete("/api/vnd/federal-references-session")
async def clear_federal_references_session():
    """Очистить сохранённый результат поиска федеральных ссылок."""
    from federal_refs import clear_session_federal_refs_result

    clear_session_federal_refs_result()
    return {"status": "success", "message": "Результат поиска ссылок очищен"}


@app.post("/api/vnd/download-federal")
async def download_federal_documents(request: DownloadFederalRequest):
    """Скачать федеральные документы с pravo.gov.ru и добавить в базу ФЗ."""
    try:
        from pravo_downloader import download_and_index_references

        references = request.references or []
        if not references:
            raise HTTPException(status_code=400, detail="Список документов пуст")

        result = download_and_index_references(references)
        return result
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=http_detail(e, "federal_download"))


@app.post("/api/vnd/stage1")
async def vnd_stage1(request: Stage1Request):
    """Этап 1: определить сферу деятельности, форму собственности и области законодательства."""
    try:
        from pre_analysis import detect_stage1

        filename = (request.vnd_filename or "").strip()
        vnd_name = (request.vnd_name or "").strip()
        vnd_text = resolve_vnd_text({"vnd_filename": filename, "content": vnd_name})
        if not vnd_text:
            raise HTTPException(
                status_code=404,
                detail="Не удалось прочитать текст документа. Загрузите файл ВНД.",
            )

        safe_name = os.path.basename(filename) if filename else vnd_name or "document"
        result = detect_stage1(safe_name, vnd_name or safe_name, vnd_text)
        result["vnd_filename"] = filename
        return result
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=http_detail(e, "analysis"))


@app.post("/api/vnd/analyze")
async def vnd_analyze(request: AnalyzeVndRequest):
    """Этап 2: правовой анализ ВНД с учётом параметров этапа 1."""
    try:
        from pre_analysis import normalize_stage1_answers

        filename = (request.vnd_filename or "").strip()
        vnd_text = resolve_vnd_text({"vnd_filename": filename})
        if not vnd_text:
            raise HTTPException(
                status_code=404,
                detail="Не удалось прочитать текст документа. Загрузите файл ВНД.",
            )

        pre_analysis = normalize_stage1_answers(request.stage1 or {})
        vnd_name = (request.vnd_name or "").strip() or os.path.basename(filename) or "ВНД"

        analysis_result = analyze_vnd(
            user_message="Приступи к правовому анализу загруженного ВНД.",
            history=[],
            vnd_text=vnd_text,
            force_analysis=True,
            pre_analysis=pre_analysis,
        )

        if isinstance(analysis_result, dict):
            content = analysis_result.get("content", "")
        else:
            content = str(analysis_result)

        return {
            "response": content,
            "stage1": pre_analysis,
            "vnd_name": vnd_name,
            "phase": "analysis",
            "analysis_started": True,
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=http_detail(e, "analysis"))


@app.get("/api/create/options")
async def create_options():
    """Справочники и пояснение для помощника создания ВНД."""
    try:
        from create_vnd import get_create_options

        return get_create_options()
    except Exception as e:
        raise HTTPException(status_code=500, detail=http_detail(e, "create"))


@app.post("/api/create/upload")
async def create_upload(
    file: UploadFile = File(...),
    kind: str = Query("main"),
    main_filename: Optional[str] = Query(None),
):
    """Загрузить документ для создания ВНД (main или analysis)."""
    try:
        if kind not in ("main", "analysis"):
            raise HTTPException(status_code=400, detail="kind должен быть main или analysis")
        if not file.filename:
            raise HTTPException(status_code=400, detail="Файл не выбран")

        if kind == "analysis":
            main = (main_filename or "").strip()
            if not main:
                raise HTTPException(
                    status_code=400,
                    detail="Сначала загрузите основной документ, затем отчёт анализа",
                )
            from search_vnd import validate_analysis_for_main

            try:
                validate_analysis_for_main(main, file.filename)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        content = await file.read()
        from create_vnd import save_create_upload

        result = save_create_upload(file.filename, content, kind)
        return {"message": "Файл загружен", **result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=http_detail(e, "upload"))


@app.post("/api/create/rework/stage1")
async def create_rework_stage1(request: CreateStage1Request):
    """Определить параметры этапа 1 для переработки (если нет отчёта анализа)."""
    try:
        from create_vnd import detect_rework_stage1

        filename = (request.main_filename or "").strip()
        if not filename:
            raise HTTPException(status_code=400, detail="Не указан основной документ")

        return detect_rework_stage1(filename, request.vnd_name or "")
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=http_detail(e, "upload"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=http_detail(e, "create"))


@app.post("/api/create/rework/analyze")
async def create_rework_analyze(request: CreateReworkAnalyzeRequest):
    """Правовой анализ для переработки (как «Анализ ВНД»), отчёт не сохраняется в файл."""
    try:
        from create_vnd import analyze_for_rework

        main = (request.main_filename or "").strip()
        if not main:
            raise HTTPException(status_code=400, detail="Основной документ обязателен")
        if not request.stage1:
            raise HTTPException(status_code=400, detail="Укажите параметры этапа 1")

        return analyze_for_rework(
            main_filename=main,
            vnd_name=request.vnd_name or "",
            stage1=request.stage1,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=http_detail(e, "upload"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=http_detail(e, "create"))


@app.post("/api/create/rework/generate")
async def create_rework_generate(request: CreateReworkGenerateRequest):
    """Переработка ВНД по готовому тексту анализа (сразу после analyze)."""
    try:
        from create_vnd import generate_rework_from_analysis

        main = (request.main_filename or "").strip()
        if not main:
            raise HTTPException(status_code=400, detail="Основной документ обязателен")
        if not (request.analysis_text or "").strip():
            raise HTTPException(status_code=400, detail="Текст анализа отсутствует")

        return generate_rework_from_analysis(
            main_filename=main,
            analysis_text=request.analysis_text,
            vnd_name=request.vnd_name or "",
            stage1=request.stage1,
            analysis_meta=request.analysis_meta,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=http_detail(e, "upload"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=http_detail(e, "create"))


@app.post("/api/create/rework/run")
async def create_rework_run(request: CreateReworkRequest):
    """Переработка документа: анализ (при необходимости) + генерация."""
    try:
        from create_vnd import process_rework

        main = (request.main_filename or "").strip()
        if not main:
            raise HTTPException(status_code=400, detail="Основной документ обязателен")

        analysis = (request.analysis_filename or "").strip() or None
        analysis_text = (request.analysis_text or "").strip() or None
        if analysis:
            from search_vnd import validate_analysis_for_main

            try:
                validate_analysis_for_main(main, analysis)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        if not analysis and not analysis_text and not request.stage1:
            raise HTTPException(
                status_code=400,
                detail="Без отчёта анализа необходимо указать параметры этапа 1",
            )

        result = process_rework(
            main_filename=main,
            analysis_filename=analysis,
            vnd_name=request.vnd_name or "",
            stage1=request.stage1,
            analysis_text=analysis_text,
        )
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=http_detail(e, "upload"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=http_detail(e, "create"))


@app.post("/api/create/new/analyze")
async def create_new_analyze(request: CreateNewAnalyzeRequest):
    """Анализ вводных данных для создания нового ВНД."""
    try:
        from new_vnd_form import validate_new_vnd_form
        from create_vnd import analyze_new_vnd_task

        form_data = request.model_dump()
        normalized, missing = validate_new_vnd_form(form_data)
        if missing:
            followup_missing = [m.replace("followup:", "") for m in missing if m.startswith("followup:")]
            base_missing = [m for m in missing if not m.startswith("followup:")]
            detail = {"message": "Не заполнены обязательные поля", "missing_fields": base_missing}
            if followup_missing:
                detail["missing_followup"] = followup_missing
            raise HTTPException(status_code=400, detail=detail)

        result = analyze_new_vnd_task(normalized)
        return result
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=http_detail(e, "create"))


@app.post("/api/create/new/step2")
async def create_new_step2(request: CreateNewStage1Request):
    """Шаг 2: определить и скачать необходимые федеральные законы."""
    try:
        from create_vnd import download_required_laws, identify_required_federal_laws

        stage1 = {
            "activity_sphere": request.activity_sphere,
            "ownership_form": request.ownership_form,
            "legal_areas_text": request.legal_areas_text,
        }
        laws = identify_required_federal_laws(stage1)
        download_result = download_required_laws(laws)
        return {
            "stage1": stage1,
            "laws": laws,
            "download_result": download_result,
        }
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=http_detail(e, "create"))


@app.post("/api/create/new/generate")
async def create_new_generate(request: CreateNewGenerateRequest):
    """Сформировать новый ВНД по результатам анализа и скачанным НПА."""
    try:
        from create_vnd import generate_new_document_v2

        if not request.analysis:
            raise HTTPException(status_code=400, detail="Отсутствует результат анализа")

        result = generate_new_document_v2(
            form_data=request.form,
            analysis_text=request.analysis,
            laws=request.laws,
            download_result=request.download_result,
        )
        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=http_detail(e, "create"))


@app.post("/api/create/save")
async def create_save_document(request: CreateSaveRequest):
    """Скачать или сохранить сгенерированный ВНД (Word)."""
    try:
        from create_vnd import build_generated_document
        from pathlib import Path

        if not (request.document or "").strip():
            raise HTTPException(status_code=400, detail="Пустой документ")

        fmt = (request.format or "docx").lower()
        if fmt in ("doc", "docx"):
            fmt = "docx"
        elif fmt not in ("txt",):
            fmt = "docx"

        content, filename, media_type = build_generated_document(
            request.document,
            request.title or "ВНД",
            fmt,
        )

        if request.persist_only:
            out_dir = Path(settings.new_doc_folder)
            out_dir.mkdir(parents=True, exist_ok=True)
            target = out_dir / filename
            target.write_bytes(content)
            return {
                "status": "success",
                "filename": filename,
                "filepath": str(target),
                "folder": str(out_dir),
            }

        return _file_download_response(content, filename, media_type)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=http_detail(e, "create"))


@app.post("/api/create/qa/message")
async def create_qa_message(request: CreateQAMessageRequest):
    """Ответ на вопрос по подготовленному ВНД (диалог после создания)."""
    try:
        from create_vnd import answer_create_document_question

        mode = (request.mode or "new").lower()
        if mode not in ("rework", "new"):
            raise HTTPException(status_code=400, detail="mode должен быть rework или new")

        result = answer_create_document_question(
            mode=mode,
            document_text=request.document or "",
            title=request.title or "ВНД",
            messages=request.messages or [],
            user_message=request.user_message or "",
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=http_detail(e, "create"))


@app.post("/api/create/qa/save")
async def create_qa_save(request: CreateQASaveRequest):
    """Скачать диалог по подготовленному ВНД."""
    try:
        from create_vnd import build_create_qa_dialog

        mode = (request.mode or "new").lower()
        if mode not in ("rework", "new"):
            raise HTTPException(status_code=400, detail="mode должен быть rework или new")
        if not request.messages:
            raise HTTPException(status_code=400, detail="Диалог пуст")

        content, filename, media_type = build_create_qa_dialog(
            request.messages,
            request.title or "ВНД",
        )

        if request.persist_only:
            from pathlib import Path
            out_dir = Path(settings.out_folder)
            out_dir.mkdir(parents=True, exist_ok=True)
            target = out_dir / filename
            target.write_bytes(content)
            return {
                "status": "success",
                "filename": filename,
                "filepath": str(target),
                "folder": str(out_dir),
            }

        return _file_download_response(content, filename, media_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=http_detail(e, "create"))


BASE_COLLECTION_NAMES = {
    "fz": "fz_documents",
    "gost": "gost_documents",
    "vnd": "vnd_documents",
}

BASE_SOURCE_FOLDERS = {
    "fz": "fz_folder",
    "gost": "fzyur_folder",
    "vnd": "in_folder",
}

BASE_SOURCE_HINTS = {
    "fz": "FZ",
    "gost": "FZYur",
    "vnd": "IN",
}


def _normalize_base_name(base_name: str) -> str:
    normalized = (base_name or "").lower().strip()
    if normalized not in BASE_COLLECTION_NAMES:
        raise HTTPException(
            status_code=400,
            detail="Неизвестная база. Допустимые значения: gost, fz, vnd",
        )
    return normalized


def _clear_collection_safe(store, collection_name: str) -> int:
    """Безопасно очистить коллекцию. Возвращает число удалённых чанков."""
    if not store or not hasattr(store, "collection"):
        return 0
    deleted = 0
    try:
        result = store.collection.get()
        all_ids = result.get("ids", []) or []
        deleted = len(all_ids)
        if all_ids:
            try:
                store.collection.delete(ids=all_ids)
            except Exception:
                batch_size = 100
                for i in range(0, len(all_ids), batch_size):
                    batch_ids = all_ids[i : i + batch_size]
                    try:
                        store.collection.delete(ids=batch_ids)
                    except Exception:
                        pass
    except Exception as exc:
        print(f"⚠ Ошибка при очистке {collection_name}: {exc}")
        try:
            if hasattr(store, "client"):
                store.client.delete_collection(name=collection_name)
        except Exception as exc2:
            print(f"⚠ Не удалось удалить коллекцию {collection_name}: {exc2}")
    return deleted


def _get_base_store(base_name: str):
    import vector_store

    vector_store.init_vector_stores()
    stores = {
        "gost": vector_store.gost_store,
        "fz": vector_store.fz_store,
        "vnd": vector_store.vnd_store,
    }
    store = stores.get(base_name)
    if not store:
        raise HTTPException(status_code=500, detail="База не инициализирована")
    return store


def _get_base_documents_payload(base_name: str) -> dict:
    normalized = (base_name or "").lower().strip()
    if normalized not in ("gost", "fz", "vnd"):
        raise HTTPException(
            status_code=400,
            detail="Неизвестная база. Допустимые значения: gost, fz, vnd",
        )

    import vector_store

    vector_store.init_vector_stores()
    stores = {
        "gost": vector_store.gost_store,
        "fz": vector_store.fz_store,
        "vnd": vector_store.vnd_store,
    }
    store = stores.get(normalized)
    if not store:
        raise HTTPException(status_code=500, detail="База не инициализирована")

    labels = {"gost": "ГОСТ", "fz": "ФЗ", "vnd": "ВНД"}
    info = store.get_collection_info()
    documents = store.list_documents()
    return {
        "base": normalized,
        "label": labels[normalized],
        "documents": documents,
        "total_documents": len(documents),
        "total_chunks": info.get("count", 0),
    }


@app.get("/api/config")
async def get_app_config():
    """Текущие пути данных."""
    try:
        from path_config import apply_paths_to_settings, get_config_payload

        apply_paths_to_settings()
        return get_config_payload()
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=http_detail(e, "init"))


@app.post("/api/config/save")
async def save_app_config(request: WorkFolderRequest):
    """Сохранить рабочую папку и создать необходимые подпапки."""
    try:
        import asyncio

        from path_config import apply_paths_to_settings, get_config_payload, write_data_root

        paths = await asyncio.to_thread(write_data_root, request.work_folder)
        apply_paths_to_settings()
        payload = get_config_payload()
        return {
            "status": "success",
            "message": f"Рабочая папка сохранена: {paths['data_root']}",
            "paths": paths,
            **payload,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=http_detail(e, "init"))


@app.post("/api/config/default")
async def reset_app_config():
    """Сбросить рабочую папку к значению по умолчанию."""
    try:
        import asyncio

        from path_config import apply_paths_to_settings, get_config_payload, reset_data_root_to_default

        paths = await asyncio.to_thread(reset_data_root_to_default)
        apply_paths_to_settings()
        payload = get_config_payload()
        return {
            "status": "success",
            "message": f"Установлена папка по умолчанию: {paths['data_root']}",
            "paths": paths,
            **payload,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=http_detail(e, "init"))


@app.post("/api/config/browse-folder")
async def browse_app_folder(request: BrowseFolderRequest):
    """Открыть диалог выбора папки (только локальный Windows)."""
    import asyncio

    try:
        from path_config import browse_folder_dialog, is_browse_folder_available, read_data_root

        if not is_browse_folder_available():
            return {
                "available": False,
                "cancelled": True,
                "message": "Диалог выбора папки доступен только на локальном Windows",
            }

        initial = (request.initial_dir or "").strip() or read_data_root()
        selected = await asyncio.to_thread(browse_folder_dialog, initial)
        if not selected:
            return {"available": True, "cancelled": True}

        return {
            "available": True,
            "cancelled": False,
            "work_folder": selected,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=http_detail(e, "init"))


def _safe_relative_upload_path(filename: str) -> str:
    """Сохраняем структуру папки из браузера, но не позволяем выйти из target."""
    from pathlib import PurePosixPath

    raw = (filename or "").replace("\\", "/").strip()
    parts = []
    for part in PurePosixPath(raw).parts:
        clean = re.sub(r'[<>:"\\|?*\x00-\x1f]', "_", part).strip()
        if not clean or clean in {".", ".."}:
            continue
        parts.append(clean)
    if not parts:
        return f"upload_{int(time.time() * 1000)}"
    return "/".join(parts)


@app.post("/api/config/upload-files")
async def upload_config_files(
    target_folder: str = Query("IN"),
    files: list[UploadFile] = File(...),
):
    """Загрузить файлы/папку с ПК пользователя в выбранную рабочую подпапку сервера."""
    try:
        from pathlib import Path

        from path_config import apply_paths_to_settings

        target_key = (target_folder or "").strip()
        if target_key not in UPLOAD_TARGET_FOLDERS:
            raise HTTPException(
                status_code=400,
                detail="Неизвестная папка назначения. Допустимо: IN, FZYur, FZ, OUT, new-doc",
            )

        paths = apply_paths_to_settings()
        base_dir = Path(paths[UPLOAD_TARGET_FOLDERS[target_key]]).resolve()
        base_dir.mkdir(parents=True, exist_ok=True)

        saved_files = []
        skipped = 0
        for file in files:
            if not file or not file.filename:
                skipped += 1
                continue

            relative_name = _safe_relative_upload_path(file.filename)
            destination = (base_dir / relative_name).resolve()
            if base_dir not in destination.parents and destination != base_dir:
                skipped += 1
                continue

            destination.parent.mkdir(parents=True, exist_ok=True)
            content = await file.read()
            if not content:
                skipped += 1
                continue
            destination.write_bytes(content)
            saved_files.append(str(destination))

        if not saved_files:
            raise HTTPException(status_code=400, detail="Файлы не выбраны или пустые")

        reindex_message = ""
        if target_key == "FZYur":
            try:
                from document_loader import process_folder
                import vector_store

                vector_store.init_vector_stores()
                if vector_store.gost_store:
                    result = process_folder(str(base_dir), vector_store.gost_store, "gost")
                    count = result.get("files_processed", 0)
                    reindex_message = f"База ГОСТ обновлена: {count} файл(ов)."
            except Exception as exc:
                reindex_message = f"Файлы загружены, но индексация ГОСТ не выполнена: {exc}"
        elif target_key == "FZ":
            try:
                from document_loader import process_folder
                import vector_store

                vector_store.init_vector_stores()
                if vector_store.fz_store:
                    result = process_folder(str(base_dir), vector_store.fz_store, "fz")
                    count = result.get("files_processed", 0)
                    reindex_message = f"База ФЗ обновлена: {count} файл(ов)."
            except Exception as exc:
                reindex_message = f"Файлы загружены, но индексация ФЗ не выполнена: {exc}"

        return {
            "status": "success",
            "target_folder": target_key,
            "folder": str(base_dir),
            "saved_count": len(saved_files),
            "skipped_count": skipped,
            "files": saved_files[:100],
            "reindex_message": reindex_message,
            "message": f"Загружено файлов: {len(saved_files)} в {target_key}",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=http_detail(e, "upload"))


@app.get("/api/bases/status")
async def get_bases_status(documents: Optional[str] = None):
    """Получить статус готовности баз. Параметр documents=gost|fz|vnd — список файлов базы."""
    try:
        if documents:
            return _get_base_documents_payload(documents)
        bases_info = init_vector_stores()
        return bases_info
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=http_detail(e, "init"))


@app.get("/api/bases/{base_name}/documents")
async def get_base_documents(base_name: str):
    """Список документов в базе знаний (gost, fz, vnd)."""
    try:
        return _get_base_documents_payload(base_name)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=http_detail(e, "init"))


@app.post("/api/bases/reindex")
async def reindex_bases():
    """Переиндексировать базы"""
    try:
        from zagruzka import create_index_bases
        result = create_index_bases()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=http_detail(e, "reindex"))


@app.post("/api/bases/{base_name}/reset")
async def reset_base(base_name: str):
    """Сбросить базу: удалить все чанки и записи."""
    try:
        normalized = _normalize_base_name(base_name)
        labels = {"gost": "ГОСТ", "fz": "ФЗ", "vnd": "ВНД"}
        store = _get_base_store(normalized)
        deleted = _clear_collection_safe(store, BASE_COLLECTION_NAMES[normalized])
        info = store.get_collection_info()
        return {
            "status": "success",
            "base": normalized,
            "label": labels[normalized],
            "message": f"База {labels[normalized]} сброшена. Удалено чанков: {deleted}.",
            "deleted_chunks": deleted,
            "count": info.get("count", 0),
            "files_count": info.get("files_count", 0),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=http_detail(e, "reindex"))


@app.post("/api/bases/{base_name}/recreate")
async def recreate_base(base_name: str):
    """Пересоздать базу из исходной папки (только ГОСТ и ФЗ)."""
    try:
        normalized = _normalize_base_name(base_name)
        if normalized == "vnd":
            raise HTTPException(
                status_code=400,
                detail="Для базы ВНД доступен только сброс. Пересоздание не выполняется.",
            )

        from config import settings
        from document_loader import process_folder

        labels = {"gost": "ГОСТ", "fz": "ФЗ"}
        folder_attr = BASE_SOURCE_FOLDERS[normalized]
        source_hint = BASE_SOURCE_HINTS[normalized]
        folder_path = getattr(settings, folder_attr)

        store = _get_base_store(normalized)
        deleted = _clear_collection_safe(store, BASE_COLLECTION_NAMES[normalized])

        result = process_folder(folder_path, store, normalized)
        info = store.get_collection_info()

        return {
            "status": result.get("status", "success"),
            "base": normalized,
            "label": labels[normalized],
            "message": (
                f"База {labels[normalized]} пересоздана из папки {source_hint}. "
                f"Удалено чанков: {deleted}. "
                f"Обработано файлов: {result.get('files_processed', 0)}."
            ),
            "deleted_chunks": deleted,
            "result": result,
            "count": info.get("count", 0),
            "files_count": info.get("files_count", 0),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=http_detail(e, "reindex"))


class SearchVndRequest(BaseModel):
    query: str
    n_results: int = 5


class SearchLoadDocumentRequest(BaseModel):
    source: str
    filename: str
    analysis_filename: Optional[str] = ""
    analysis_source: Optional[str] = ""
    auto_match_analysis: bool = True


class SearchQAMessageRequest(BaseModel):
    document: str
    title: Optional[str] = "ВНД"
    analysis_text: Optional[str] = ""
    messages: Optional[list] = None
    user_message: str


class SearchQASaveRequest(BaseModel):
    title: Optional[str] = "ВНД"
    messages: list
    persist_only: Optional[bool] = False


@app.post("/api/search/vnd")
async def search_vnd(request: SearchVndRequest):
    """Поиск по базе ВНД"""
    try:
        query = (request.query or "").strip()
        if not query:
            raise HTTPException(status_code=400, detail="Поисковый запрос не может быть пустым")

        # Ограничиваем количество результатов разумными пределами
        n_results = max(1, min(request.n_results, 20))

        from vector_store import vnd_store, init_vector_stores

        if not vnd_store:
            init_vector_stores()
            from vector_store import vnd_store as vnd_store_ref
            vnd_store = vnd_store_ref

        if not vnd_store:
            raise HTTPException(status_code=500, detail="База ВНД не инициализирована")

        base_info = vnd_store.get_collection_info()
        if base_info.get("count", 0) == 0:
            return {
                "query": query,
                "count": 0,
                "results": [],
                "message": "База ВНД пуста. Загрузите документы в папку IN и выполните индексацию."
            }

        raw_results = vnd_store.search(query=query, n_results=n_results)
        results = []
        for item in raw_results:
            metadata = item.get("metadata") or {}
            distance = item.get("distance")
            # В косинусной метрике Chroma меньше distance -> релевантнее.
            # Показываем score в диапазоне [0..1] для удобства на UI.
            score = None
            if isinstance(distance, (float, int)):
                score = max(0.0, min(1.0, 1.0 - float(distance)))

            results.append(
                {
                    "document": item.get("document", ""),
                    "filename": metadata.get("filename", ""),
                    "source": metadata.get("source", ""),
                    "distance": distance,
                    "score": score,
                }
            )

        return {
            "query": query,
            "count": len(results),
            "results": results
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=http_detail(e, "search"))


@app.post("/api/search/load-document")
async def search_load_document(request: SearchLoadDocumentRequest):
    """Загрузить текст ВНД для диалога (из папки IN или из базы ВНД)."""
    try:
        from search_vnd import load_search_session

        analysis_filename = (request.analysis_filename or "").strip() or None
        analysis_source = (request.analysis_source or "").strip() or None
        return load_search_session(
            request.source or "",
            request.filename or "",
            analysis_filename=analysis_filename,
            analysis_source=analysis_source,
            auto_match_analysis=bool(request.auto_match_analysis),
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=http_detail(e, "search"))


@app.get("/api/search/resolve-analysis")
async def search_resolve_analysis(filename: str = "", source: str = ""):
    """Прочитать текст отчёта анализа из папки OUT, IN/create или search."""
    try:
        from search_vnd import resolve_analysis_text

        safe_name = (filename or "").strip()
        if not safe_name:
            raise HTTPException(status_code=400, detail="Укажите filename")
        text, resolved_name, resolved_source = resolve_analysis_text(safe_name, source or None)
        return {
            "filename": resolved_name,
            "source": resolved_source,
            "text": text,
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=http_detail(e, "search"))


@app.get("/api/search/analysis-candidates")
async def search_analysis_candidates(vnd_filename: str = ""):
    """Список отчётов анализа, подходящих к выбранному ВНД."""
    try:
        from search_vnd import find_analysis_candidates

        filename = (vnd_filename or "").strip()
        if not filename:
            raise HTTPException(status_code=400, detail="Укажите vnd_filename")
        return {
            "vnd_filename": filename,
            "candidates": find_analysis_candidates(filename),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=http_detail(e, "search"))


@app.post("/api/search/upload-analysis")
async def search_upload_analysis(file: UploadFile = File(...)):
    """Загрузить отчёт анализа для диалога «Поиск в ВНД»."""
    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail="Файл не выбран")
        content = await file.read()
        from search_vnd import save_search_analysis_upload

        saved = save_search_analysis_upload(file.filename, content)
        return {
            "message": "Отчёт анализа загружен",
            "filename": saved["filename"],
            "source": saved["source"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=http_detail(e, "search"))


@app.post("/api/search/qa/message")
async def search_qa_message(request: SearchQAMessageRequest):
    """Ответ на вопрос по ВНД в режиме «Поиск в ВНД»."""
    try:
        from search_vnd import answer_search_vnd_question

        result = answer_search_vnd_question(
            document_text=request.document or "",
            title=request.title or "ВНД",
            messages=request.messages or [],
            user_message=request.user_message or "",
            analysis_text=request.analysis_text or "",
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=http_detail(e, "search"))


@app.post("/api/search/qa/save")
async def search_qa_save(request: SearchQASaveRequest):
    """Скачать диалог «Поиск в ВНД» в текстовый файл."""
    try:
        from search_vnd import build_search_qa_dialog

        if not request.messages:
            raise HTTPException(status_code=400, detail="Диалог пуст")
        content, filename, media_type = build_search_qa_dialog(
            request.messages,
            request.title or "ВНД",
        )

        if request.persist_only:
            from pathlib import Path
            out_dir = Path(settings.out_folder)
            out_dir.mkdir(parents=True, exist_ok=True)
            target = out_dir / filename
            target.write_bytes(content)
            return {
                "status": "success",
                "filename": filename,
                "filepath": str(target),
                "folder": str(out_dir),
            }

        return _file_download_response(content, filename, media_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=http_detail(e, "search"))


@app.post("/api/bases/recreate")
async def recreate_bases():
    """Пересоздать все базы знаний (очистить все документы и заново загрузить)"""
    try:
        import vector_store
        import gc
        import time

        vector_store.init_vector_stores()
        deleted = {}
        for base_key, collection_name in BASE_COLLECTION_NAMES.items():
            store = getattr(vector_store, f"{base_key}_store", None)
            deleted[base_key] = _clear_collection_safe(store, collection_name)

        gc.collect()
        time.sleep(0.5)

        from document_loader import create_index_bases
        results = create_index_bases()

        return {
            "status": "success",
            "message": "Базы знаний успешно пересозданы (очищены и заново загружены)",
            "deleted_chunks": deleted,
            "results": results,
        }
    except Exception as e:
        import traceback
        error_detail = str(e)
        error_type = type(e).__name__
        traceback.print_exc()
        
        # Если ошибка связана с блокировкой файла, возвращаем предупреждение, а не ошибку
        if "WinError 32" in error_detail or "cannot access the file" in error_detail.lower() or "PermissionError" in error_type:
            # Коллекции уже очищены, просто нужно перезапустить сервер
            return {
                "status": "warning",
                "message": "Базы были очищены успешно. Для полного пересоздания перезапустите сервер, чтобы освободить файлы базы данных.",
                "note": "Это происходит из-за того, что ChromaDB держит файлы открытыми. Перезапуск сервера решит проблему.",
                "results": {
                    "fz": {"status": "warning", "message": "Требуется перезапуск сервера"},
                    "gost": {"status": "warning", "message": "Требуется перезапуск сервера"},
                    "vnd": {"status": "warning", "message": "Требуется перезапуск сервера"}
                }
            }
        
        raise HTTPException(status_code=500, detail=http_detail(error_detail, "reindex"))

def escape_xml(text):
    """Безопасное экранирование текста для XML/HTML (ReportLab Paragraph)"""
    if not text:
        return ""
    # Преобразуем в строку на случай если это не строка
    text = str(text)
    # Экранируем XML/HTML спецсимволы
    text = (
        text.replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
        .replace("'", '&apos;')
    )
    # Удаляем управляющие символы (кроме табуляции, новой строки, возврата каретки)
    # Разрешаем: табуляция (\t), новая строка (\n), возврат каретки (\r), обычные печатаемые символы
    cleaned = ''.join(char if char.isprintable() or char in '\t\n\r' else ' ' for char in text)
    return cleaned

@app.post("/api/report/save")
async def save_report(request: ReportSaveRequest):
    """Скачать отчёт анализа в формате PDF."""
    try:
        from datetime import datetime
        from report_pdf import build_analysis_report_pdf_bytes

        print("📄 Запрос на скачивание PDF отчёта...")

        report_name = request.report_name or "Отчёт"
        content = request.content or ""
        messages = request.messages

        if not content and messages:
            parts = []
            for msg in messages:
                if not msg:
                    continue
                msg_content = str(msg.get("content", "")).strip()
                if msg_content:
                    parts.append(msg_content)
            content = "\n\n".join(parts)

        print(f"   report_name: {report_name}, content length: {len(content)}")

        if not (content or "").strip():
            raise HTTPException(status_code=400, detail="Пустой отчёт")

        safe_name = re.sub(r'[<>:"/\\|?*]', "_", report_name)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Отчёт_{safe_name}_{timestamp}.pdf"

        pdf_bytes = build_analysis_report_pdf_bytes(
            content,
            report_name,
            title=request.title or "",
            summary_html=request.summary_html or "",
        )
        if not pdf_bytes:
            raise HTTPException(status_code=500, detail="Не удалось сформировать PDF-файл отчёта")
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as pdf_error:
        import traceback
        print(f"❌ Ошибка формирования PDF: {pdf_error}")
        traceback.print_exc()
        # Запасной вариант: сохранить как текст с той же структурой, что и PDF
        from datetime import datetime
        from report_pdf import build_analysis_report_plaintext

        safe_name = re.sub(r'[<>:"/\\|?*]', "_", request.report_name or "Отчёт")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        txt_filename = f"Отчёт_{safe_name}_{timestamp}.txt"
        try:
            txt_body = build_analysis_report_plaintext(
                content,
                report_name,
                title=request.title or "",
                summary_html=request.summary_html or "",
            )
        except ValueError:
            raise HTTPException(status_code=500, detail=http_detail(pdf_error, "report"))
        txt_bytes = txt_body.encode("utf-8")
        print(f"⚠ PDF не создан, сохраняем TXT: {txt_filename}")
        filename = txt_filename
        pdf_bytes = txt_bytes
        media_type = "text/plain; charset=utf-8"
    else:
        media_type = "application/pdf"

    try:
        from pathlib import Path

        out_dir = Path(settings.out_folder)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / filename).write_bytes(pdf_bytes)
        saved_path = str(out_dir / filename)
    except Exception as exc:
        print(f"⚠ Не удалось сохранить отчёт в OUT: {exc}")
        saved_path = ""

    if request.persist_only:
        if not saved_path:
            raise HTTPException(status_code=500, detail="Не удалось сохранить отчёт в рабочую папку")
        return {
            "status": "success",
            "filename": filename,
            "filepath": saved_path,
            "folder": str(Path(settings.out_folder)),
        }

    print(f"✅ Отчёт сформирован для скачивания: {filename}")
    return _file_download_response(pdf_bytes, filename, media_type)

if __name__ == "__main__":
    import uvicorn
    import subprocess
    import time
    
    # Проверяем и освобождаем порт 8011 перед запуском
    def check_and_free_port(port):
        """Проверить и освободить порт"""
        try:
            result = subprocess.run(
                ['netstat', '-ano'],
                capture_output=True,
                text=True,
                shell=True
            )
            for line in result.stdout.split('\n'):
                if f':{port}' in line and 'LISTENING' in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        try:
                            subprocess.run(['taskkill', '/F', '/PID', pid], 
                                         capture_output=True, shell=True)
                            print(f"✓ Остановлен процесс {pid} на порту {port}")
                            time.sleep(2)  # Ждем освобождения порта
                        except:
                            pass
        except:
            pass
    
    print("=" * 60)
    print("Запуск сервера НейроКонсультант по ВНД")
    print("=" * 60)
    print(f"Порт: 8011")
    print(f"URL: http://localhost:8011")
    print("=" * 60)
    print()
    
    # Освобождаем порт перед запуском
    check_and_free_port(8011)
    
    try:
        uvicorn.run(app, host="0.0.0.0", port=8011, log_level="info", reload=False)
    except OSError as e:
        if "10048" in str(e) or "address already in use" in str(e).lower():
            print("\n" + "=" * 60)
            print("❌ ОШИБКА: Порт 8011 занят!")
            print("=" * 60)
            print("Выполните следующие действия:")
            print("1. Запустите kill_port_8011.bat от имени администратора")
            print("2. Или выполните в командной строке:")
            print("   netstat -ano | findstr :8011")
            print("   taskkill /F /PID <номер_процесса>")
            print("3. Затем запустите сервер снова")
            print("=" * 60)
        raise
    except Exception as e:
        import traceback
        print(f"❌ Ошибка при запуске сервера: {e}")
        traceback.print_exc()
        raise

