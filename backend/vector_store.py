import chromadb
from chromadb.config import Settings as ChromaSettings
import os
from pathlib import Path
from typing import List, Optional
import json
import logging

# Отключаем телеметрию ChromaDB через переменную окружения
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY_DISABLED"] = "1"

# Глобальная настройка ChromaDB с отключенной телеметрией
try:
    chromadb.configure(
        anonymized_telemetry=False,
        allow_reset=True
    )
except Exception:
    pass  # Игнорируем ошибки конфигурации

# Подавляем логи телеметрии
logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL)
logging.getLogger("posthog").setLevel(logging.CRITICAL)

# Определяем корневую директорию проекта
BASE_DIR = Path(__file__).parent.resolve()
CHROMA_DB_DIR = BASE_DIR / "chroma_db"

class VectorStore:
    def __init__(self, collection_name: str, persist_directory: str = "./chroma_db"):
        self.persist_directory = persist_directory
        os.makedirs(persist_directory, exist_ok=True)
        
        # Настройки ChromaDB с отключенной телеметрией
        chroma_settings = ChromaSettings(
            anonymized_telemetry=False,
            allow_reset=True
        )
        
        try:
            self.client = chromadb.PersistentClient(
                path=persist_directory,
                settings=chroma_settings
            )
            
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
        except Exception as e:
            # Если возникла ошибка с телеметрией, пробуем без настроек
            print(f"Предупреждение при инициализации ChromaDB: {e}")
            print("Повторная попытка инициализации без телеметрии...")
            try:
                self.client = chromadb.PersistentClient(path=persist_directory)
                self.collection = self.client.get_or_create_collection(
                    name=collection_name,
                    metadata={"hnsw:space": "cosine"}
                )
            except Exception as e2:
                print(f"Критическая ошибка при инициализации ChromaDB: {e2}")
                raise
    
    def add_documents(self, documents: List[str], metadatas: Optional[List[dict]] = None, ids: Optional[List[str]] = None):
        """Добавить документы в векторную базу"""
        if metadatas is None:
            metadatas = [{}] * len(documents)
        if ids is None:
            ids = [f"doc_{i}" for i in range(len(documents))]
        
        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
    
    def search(self, query: str, n_results: int = 5) -> List[dict]:
        """Поиск похожих документов"""
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        return [
            {
                "document": doc,
                "metadata": meta,
                "distance": dist
            }
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0]
            )
        ]
    
    def get_collection_info(self) -> dict:
        """Получить информацию о коллекции"""
        count = self.collection.count()
        
        # Подсчитываем количество уникальных файлов
        files_count = 0
        try:
            all_results = self.collection.get()
            if all_results and all_results.get('metadatas'):
                unique_files = set()
                for metadata in all_results['metadatas']:
                    if metadata and 'filename' in metadata:
                        unique_files.add(metadata['filename'])
                files_count = len(unique_files)
        except Exception:
            files_count = 0
        
        return {
            "name": self.collection.name,
            "count": count,  # количество чанков
            "files_count": files_count,  # количество уникальных файлов
            "ready": count > 0
        }

    def list_documents(self) -> List[dict]:
        """Список уникальных документов в коллекции с числом чанков."""
        documents: dict = {}
        try:
            all_results = self.collection.get()
            if all_results and all_results.get('metadatas'):
                for metadata in all_results['metadatas']:
                    if not metadata:
                        continue
                    filename = metadata.get('filename') or Path(metadata.get('source', '')).name or 'Неизвестно'
                    if filename not in documents:
                        documents[filename] = {
                            "filename": filename,
                            "source": metadata.get('source', ''),
                            "chunks": 0,
                        }
                    documents[filename]["chunks"] += 1
        except Exception:
            pass
        return sorted(documents.values(), key=lambda item: item["filename"].lower())

    def get_document_text_by_filename(self, filename: str) -> Optional[str]:
        """Восстановить текст документа по имени файла из чанков коллекции."""
        safe_name = os.path.basename(filename or "")
        if not safe_name:
            return None
        try:
            all_results = self.collection.get()
            if not all_results or not all_results.get("documents"):
                return None

            source_path = None
            chunks_with_index: List[tuple] = []
            for doc, meta, chunk_id in zip(
                all_results["documents"],
                all_results.get("metadatas") or [],
                all_results.get("ids") or [],
            ):
                meta = meta or {}
                doc_filename = meta.get("filename") or Path(meta.get("source", "")).name
                if doc_filename != safe_name:
                    continue
                if not source_path and meta.get("source"):
                    source_path = meta.get("source")
                idx = 0
                if chunk_id and "_" in str(chunk_id):
                    try:
                        idx = int(str(chunk_id).rsplit("_", 1)[-1])
                    except ValueError:
                        idx = 0
                chunks_with_index.append((idx, doc or ""))

            if source_path and Path(source_path).is_file():
                from document_loader import extract_full_text
                return extract_full_text(source_path)[:80000]

            if not chunks_with_index:
                return None
            chunks_with_index.sort(key=lambda item: item[0])
            return "\n".join(chunk for _, chunk in chunks_with_index)[:80000]
        except Exception:
            return None
    
    def delete_collection(self):
        """Удалить коллекцию из базы данных"""
        try:
            self.client.delete_collection(name=self.collection.name)
            return True
        except Exception as e:
            print(f"Ошибка при удалении коллекции {self.collection.name}: {e}")
            return False

# Глобальные экземпляры для разных баз
gost_store = None
fz_store = None
vnd_store = None

def init_vector_stores():
    """Инициализация векторных баз"""
    global gost_store, fz_store, vnd_store
    
    gost_store = VectorStore("gost_documents", str(CHROMA_DB_DIR / "gost"))
    fz_store = VectorStore("fz_documents", str(CHROMA_DB_DIR / "fz"))
    vnd_store = VectorStore("vnd_documents", str(CHROMA_DB_DIR / "vnd"))
    
    return {
        "gost": gost_store.get_collection_info(),
        "fz": fz_store.get_collection_info(),
        "vnd": vnd_store.get_collection_info()
    }





