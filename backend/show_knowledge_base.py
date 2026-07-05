"""
Скрипт для просмотра информации о базах знаний
Показывает статистику и примеры документов из всех баз
"""
from vector_store import init_vector_stores, gost_store, fz_store, vnd_store
import sys

def show_knowledge_base():
    """Показать информацию о базах знаний"""
    
    print("=" * 80)
    print("ИНФОРМАЦИЯ О БАЗАХ ЗНАНИЙ")
    print("=" * 80)
    
    # Инициализируем базы
    try:
        print("\nИнициализация векторных баз...")
        result = init_vector_stores()
        print("✓ Базы инициализированы\n")
        
        # Переимпортируем для получения обновленных глобальных переменных
        from vector_store import gost_store, fz_store, vnd_store
    except Exception as e:
        print(f"✗ Ошибка при инициализации: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # База ФЗ
    print("─" * 80)
    print("📚 БАЗА ЗНАНИЙ ФЗ (ФЕДЕРАЛЬНЫЕ ЗАКОНЫ)")
    print("─" * 80)
    
    if fz_store:
        try:
            info = fz_store.get_collection_info()
            print(f"Название коллекции: {info['name']}")
            print(f"Количество фрагментов (чанков): {info['count']}")
            
            # Подсчитываем количество уникальных файлов
            try:
                all_results = fz_store.collection.get()
                if all_results and all_results.get('metadatas'):
                    unique_files = set()
                    for metadata in all_results['metadatas']:
                        if metadata and 'filename' in metadata:
                            unique_files.add(metadata['filename'])
                    print(f"Количество уникальных файлов: {len(unique_files)}")
                else:
                    print(f"Количество уникальных файлов: не определено")
            except Exception as e:
                print(f"Количество уникальных файлов: не удалось определить ({e})")
            
            print(f"Статус: {'✓ Готова к использованию' if info['ready'] else '⚠ Пустая база'}")
            print(f"\n📝 Пояснение: каждый файл разбивается на фрагменты (~1000 символов),")
            print(f"   поэтому количество фрагментов больше количества файлов.")
            
            if info['count'] > 0:
                print("\nПримеры документов (первые 5):")
                try:
                    # Получаем примеры документов
                    results = fz_store.collection.get(limit=5)
                    if results['ids']:
                        for i, (doc_id, doc_text, metadata) in enumerate(zip(
                            results['ids'],
                            results['documents'],
                            results['metadatas']
                        ), 1):
                            filename = metadata.get('filename', 'Неизвестно') if metadata else 'Неизвестно'
                            source = metadata.get('source', 'Неизвестно') if metadata else 'Неизвестно'
                            preview = doc_text[:150] + "..." if len(doc_text) > 150 else doc_text
                            
                            print(f"\n  {i}. ID: {doc_id}")
                            print(f"     Файл: {filename}")
                            print(f"     Источник: {source}")
                            print(f"     Превью: {preview}")
                except Exception as e:
                    print(f"     ⚠ Не удалось получить примеры: {e}")
        except Exception as e:
            print(f"✗ Ошибка при получении информации о базе ФЗ: {e}")
    else:
        print("✗ База ФЗ не инициализирована")
    
    # База ГОСТ
    print("\n" + "─" * 80)
    print("📚 БАЗА ЗНАНИЙ ГОСТ (ГОСУДАРСТВЕННЫЕ СТАНДАРТЫ)")
    print("─" * 80)
    
    if gost_store:
        try:
            info = gost_store.get_collection_info()
            print(f"Название коллекции: {info['name']}")
            print(f"Количество фрагментов (чанков): {info['count']}")
            
            # Подсчитываем количество уникальных файлов
            try:
                all_results = gost_store.collection.get()
                if all_results and all_results.get('metadatas'):
                    unique_files = set()
                    for metadata in all_results['metadatas']:
                        if metadata and 'filename' in metadata:
                            unique_files.add(metadata['filename'])
                    print(f"Количество уникальных файлов: {len(unique_files)}")
                else:
                    print(f"Количество уникальных файлов: не определено")
            except Exception as e:
                print(f"Количество уникальных файлов: не удалось определить ({e})")
            
            print(f"Статус: {'✓ Готова к использованию' if info['ready'] else '⚠ Пустая база'}")
            print(f"\n📝 Пояснение: каждый файл разбивается на фрагменты (~1000 символов),")
            print(f"   поэтому количество фрагментов больше количества файлов.")
            
            if info['count'] > 0:
                print("\nПримеры документов (первые 5):")
                try:
                    results = gost_store.collection.get(limit=5)
                    if results['ids']:
                        for i, (doc_id, doc_text, metadata) in enumerate(zip(
                            results['ids'],
                            results['documents'],
                            results['metadatas']
                        ), 1):
                            filename = metadata.get('filename', 'Неизвестно') if metadata else 'Неизвестно'
                            source = metadata.get('source', 'Неизвестно') if metadata else 'Неизвестно'
                            preview = doc_text[:150] + "..." if len(doc_text) > 150 else doc_text
                            
                            print(f"\n  {i}. ID: {doc_id}")
                            print(f"     Файл: {filename}")
                            print(f"     Источник: {source}")
                            print(f"     Превью: {preview}")
                except Exception as e:
                    print(f"     ⚠ Не удалось получить примеры: {e}")
        except Exception as e:
            print(f"✗ Ошибка при получении информации о базе ГОСТ: {e}")
    else:
        print("✗ База ГОСТ не инициализирована")
    
    # База ВНД
    print("\n" + "─" * 80)
    print("📚 БАЗА ЗНАНИЙ ВНД (ВНУТРЕННИЕ НОРМАТИВНЫЕ ДОКУМЕНТЫ)")
    print("─" * 80)
    
    if vnd_store:
        try:
            info = vnd_store.get_collection_info()
            print(f"Название коллекции: {info['name']}")
            print(f"Количество фрагментов (чанков): {info['count']}")
            
            # Подсчитываем количество уникальных файлов
            try:
                all_results = vnd_store.collection.get()
                if all_results and all_results.get('metadatas'):
                    unique_files = set()
                    for metadata in all_results['metadatas']:
                        if metadata and 'filename' in metadata:
                            unique_files.add(metadata['filename'])
                    print(f"Количество уникальных файлов: {len(unique_files)}")
                else:
                    print(f"Количество уникальных файлов: не определено")
            except Exception as e:
                print(f"Количество уникальных файлов: не удалось определить ({e})")
            
            print(f"Статус: {'✓ Готова к использованию' if info['ready'] else '⚠ Пустая база'}")
            print(f"\n📝 Пояснение: каждый файл разбивается на фрагменты (~1000 символов),")
            print(f"   поэтому количество фрагментов больше количества файлов.")
            
            if info['count'] > 0:
                print("\nПримеры документов (первые 5):")
                try:
                    results = vnd_store.collection.get(limit=5)
                    if results['ids']:
                        for i, (doc_id, doc_text, metadata) in enumerate(zip(
                            results['ids'],
                            results['documents'],
                            results['metadatas']
                        ), 1):
                            filename = metadata.get('filename', 'Неизвестно') if metadata else 'Неизвестно'
                            source = metadata.get('source', 'Неизвестно') if metadata else 'Неизвестно'
                            preview = doc_text[:150] + "..." if len(doc_text) > 150 else doc_text
                            
                            print(f"\n  {i}. ID: {doc_id}")
                            print(f"     Файл: {filename}")
                            print(f"     Источник: {source}")
                            print(f"     Превью: {preview}")
                except Exception as e:
                    print(f"     ⚠ Не удалось получить примеры: {e}")
        except Exception as e:
            print(f"✗ Ошибка при получении информации о базе ВНД: {e}")
    else:
        print("✗ База ВНД не инициализирована")
    
    # Итоговая статистика
    print("\n" + "=" * 80)
    print("ИТОГОВАЯ СТАТИСТИКА")
    print("=" * 80)
    
    total_docs = 0
    if fz_store:
        try:
            total_docs += fz_store.get_collection_info()['count']
        except:
            pass
    if gost_store:
        try:
            total_docs += gost_store.get_collection_info()['count']
        except:
            pass
    if vnd_store:
        try:
            total_docs += vnd_store.get_collection_info()['count']
        except:
            pass
    
    print(f"Общее количество документов во всех базах: {total_docs}")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    try:
        show_knowledge_base()
    except KeyboardInterrupt:
        print("\n\nПрервано пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

