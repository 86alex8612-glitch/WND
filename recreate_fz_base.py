"""
Скрипт для пересоздания базы знаний ФЗ (федеральных законов)
Удаляет существующую базу и создает новую из документов в папке FZ
"""
import os
import shutil
from pathlib import Path
from vector_store import CHROMA_DB_DIR, init_vector_stores, VectorStore
from document_loader import process_folder
from config import settings

def recreate_fz_base():
    """Пересоздать базу знаний ФЗ"""
    
    print("=" * 60)
    print("ПЕРЕСОЗДАНИЕ БАЗЫ ЗНАНИЙ ФЗ")
    print("=" * 60)
    
    # Путь к базе данных ФЗ
    fz_db_path = CHROMA_DB_DIR / "fz"
    
    # Шаг 1: Удаление существующей базы ФЗ
    print("\n1. Удаление существующей базы ФЗ...")
    if fz_db_path.exists():
        try:
            shutil.rmtree(fz_db_path)
            print(f"   ✓ Папка {fz_db_path} удалена")
        except Exception as e:
            print(f"   ✗ Ошибка при удалении: {e}")
            return False
    else:
        print(f"   ℹ Папка {fz_db_path} не существует, пропускаем удаление")
    
    # Создаем папку заново
    fz_db_path.mkdir(parents=True, exist_ok=True)
    print(f"   ✓ Создана новая папка {fz_db_path}")
    
    # Шаг 2: Инициализация новой базы
    print("\n2. Инициализация новой базы ФЗ...")
    try:
        init_vector_stores()
        print("   ✓ Векторные базы инициализированы")
    except Exception as e:
        print(f"   ✗ Ошибка при инициализации: {e}")
        return False
    
    # Шаг 3: Проверка наличия папки с документами ФЗ
    print(f"\n3. Проверка папки с документами ФЗ: {settings.fz_folder}")
    if not os.path.exists(settings.fz_folder):
        print(f"   ✗ Папка {settings.fz_folder} не существует!")
        print(f"   Создайте папку и добавьте туда файлы ФЗ (PDF, DOCX, TXT, MD)")
        return False
    
    if not os.path.isdir(settings.fz_folder):
        print(f"   ✗ {settings.fz_folder} не является папкой!")
        return False
    
    # Подсчет файлов
    fz_path = Path(settings.fz_folder)
    supported_extensions = {".pdf", ".docx", ".doc", ".txt", ".md"}
    files = [f for f in fz_path.rglob("*") if f.is_file() and f.suffix.lower() in supported_extensions]
    
    if not files:
        print(f"   ⚠ В папке {settings.fz_folder} не найдено файлов для обработки")
        print(f"   Поддерживаемые форматы: PDF, DOCX, DOC, TXT, MD")
        return False
    
    print(f"   ✓ Найдено {len(files)} файлов для обработки")
    
    # Шаг 4: Загрузка документов в новую базу
    print("\n4. Загрузка документов в базу ФЗ...")
    try:
        from vector_store import fz_store
        
        if not fz_store:
            print("   ✗ База ФЗ не инициализирована!")
            return False
        
        result = process_folder(settings.fz_folder, fz_store, "fz")
        
        if result.get("status") == "success" and result.get("files_processed", 0) > 0:
            print(f"\n   ✓ База ФЗ успешно пересоздана!")
            print(f"   - Обработано файлов: {result.get('files_processed')}")
            print(f"   - Создано фрагментов: {result.get('total_chunks')}")
            print(f"   - Найдено файлов: {result.get('files_found')}")
            if result.get('files_skipped', 0) > 0:
                print(f"   - Пропущено файлов: {result.get('files_skipped')}")
            
            # Проверка финального состояния
            collection_info = fz_store.get_collection_info()
            print(f"\n   📊 Финальное состояние базы:")
            print(f"   - Коллекция: {collection_info['name']}")
            print(f"   - Документов в базе: {collection_info['count']}")
            
            return True
        else:
            print(f"   ⚠ Предупреждение: {result.get('message', 'неизвестная ошибка')}")
            return False
            
    except Exception as e:
        print(f"   ✗ Ошибка при загрузке документов: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = recreate_fz_base()
    
    print("\n" + "=" * 60)
    if success:
        print("✓ ПЕРЕСОЗДАНИЕ БАЗЫ ФЗ ЗАВЕРШЕНО УСПЕШНО")
    else:
        print("✗ ПЕРЕСОЗДАНИЕ БАЗЫ ФЗ ЗАВЕРШЕНО С ОШИБКАМИ")
    print("=" * 60)



