"""
Блок загрузки документов и создания индексных баз
"""
from document_loader import create_index_bases
from database import SessionLocal, Dialog
from vector_store import init_vector_stores

def check_unfinished_dialogs():
    """Проверка незавершенных диалогов"""
    db = SessionLocal()
    try:
        unfinished = db.query(Dialog).filter(Dialog.is_completed == False).all()
        return [
            {
                "id": dialog.id,
                "vnd_name": dialog.vnd_name,
                "created_at": dialog.created_at.isoformat(),
                "updated_at": dialog.updated_at.isoformat()
            }
            for dialog in unfinished
        ]
    finally:
        db.close()

def get_dialog_by_id(dialog_id: int):
    """Получить диалог по ID"""
    db = SessionLocal()
    try:
        dialog = db.query(Dialog).filter(Dialog.id == dialog_id).first()
        if dialog:
            import json
            return {
                "id": dialog.id,
                "vnd_name": dialog.vnd_name,
                "messages": json.loads(dialog.messages) if dialog.messages else [],
                "is_completed": dialog.is_completed,
                "created_at": dialog.created_at.isoformat(),
                "updated_at": dialog.updated_at.isoformat()
            }
        return None
    finally:
        db.close()

def save_dialog(vnd_name: str, messages: list, is_completed: bool = False):
    """Сохранить диалог"""
    # ПРИНУДИТЕЛЬНАЯ ПРОВЕРКА: Убеждаемся, что используется SQLite
    from config import settings
    from pathlib import Path
    
    if not settings.database_url.startswith('sqlite'):
        print("=" * 60)
        print("❌ КРИТИЧЕСКАЯ ОШИБКА: Обнаружен не-SQLite URL в save_dialog!")
        print(f"   Текущий URL: {settings.database_url}")
        print("   Принудительно переключаемся на SQLite...")
        
        # Принудительно устанавливаем SQLite URL
        _db_base_dir = Path(__file__).parent.parent.resolve()
        _db_default_path = _db_base_dir / "backend" / "wnd.db"
        _db_default_url = f"sqlite:///{str(_db_default_path).replace(chr(92), '/')}"
        settings.database_url = _db_default_url
        print(f"   Новый URL: {_db_default_url}")
        print("=" * 60)
        
        # Пересоздаем engine с правильным URL
        from database import create_engine, Base, SessionLocal as _SessionLocal
        from sqlalchemy.orm import sessionmaker
        import os
        
        # Создаем новый engine с SQLite
        db_path = _db_default_url.replace('sqlite:///', '').replace('sqlite://', '')
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        
        new_engine = create_engine(
            _db_default_url,
            connect_args={"check_same_thread": False},
            echo=False
        )
        
        # Обновляем глобальный SessionLocal
        global SessionLocal
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=new_engine)
        
        # Обновляем engine в database.py
        import database
        database.engine = new_engine
        database.SessionLocal = SessionLocal
    
    db = SessionLocal()
    try:
        import json
        # Убеждаемся, что messages - это список
        if not isinstance(messages, list):
            messages = []
        
        # Сериализуем сообщения в JSON
        messages_json = json.dumps(messages, ensure_ascii=False) if messages else "[]"
        
        dialog = Dialog(
            vnd_name=vnd_name,
            messages=messages_json,
            is_completed=is_completed
        )
        db.add(dialog)
        db.commit()
        db.refresh(dialog)
        dialog_id = dialog.id
        print(f"Диалог сохранен: ID={dialog_id}, vnd_name={vnd_name}")
        return dialog_id
    except Exception as e:
        db.rollback()
        import traceback
        error_msg = f"Ошибка при сохранении диалога: {e}"
        print(error_msg)
        print(f"Используемая база данных: {settings.database_url}")
        print(traceback.format_exc())
        raise
    finally:
        db.close()

def update_dialog(dialog_id: int, messages: list, is_completed: bool = False):
    """Обновить диалог"""
    db = SessionLocal()
    try:
        import json
        dialog = db.query(Dialog).filter(Dialog.id == dialog_id).first()
        if dialog:
            dialog.messages = json.dumps(messages, ensure_ascii=False)
            dialog.is_completed = is_completed
            db.commit()
            print(f"Диалог обновлен: ID={dialog_id}")
            return True
        print(f"Диалог не найден: ID={dialog_id}")
        return False
    except Exception as e:
        db.rollback()
        import traceback
        error_msg = f"Ошибка при обновлении диалога: {e}"
        print(error_msg)
        print(traceback.format_exc())
        raise
    finally:
        db.close()

def delete_dialog(dialog_id: int):
    """Удалить диалог"""
    db = SessionLocal()
    try:
        dialog = db.query(Dialog).filter(Dialog.id == dialog_id).first()
        if dialog:
            vnd_name = dialog.vnd_name
            db.delete(dialog)
            db.commit()
            print(f"Диалог удален: ID={dialog_id}, vnd_name={vnd_name}")
            return True
        print(f"Диалог не найден: ID={dialog_id}")
        return False
    except Exception as e:
        db.rollback()
        import traceback
        error_msg = f"Ошибка при удалении диалога: {e}"
        print(error_msg)
        print(traceback.format_exc())
        raise
    finally:
        db.close()

def initialize_system():
    """Инициализация системы: создание баз и проверка диалогов"""
    # Создаем индексные базы
    index_results = create_index_bases()
    
    # Проверяем незавершенные диалоги
    unfinished_dialogs = check_unfinished_dialogs()
    
    # Получаем информацию о готовности баз
    bases_info = init_vector_stores()
    
    return {
        "index_bases": index_results,
        "unfinished_dialogs": unfinished_dialogs,
        "bases_info": bases_info
    }

