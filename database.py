from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from pathlib import Path
import os

# ПРИНУДИТЕЛЬНО загружаем .env перед импортом settings
from dotenv import load_dotenv
load_dotenv()

# Проверяем DATABASE_URL из окружения напрямую
_env_db_url = os.getenv("DATABASE_URL", "").strip()

# Определяем корневую директорию для базы данных
BASE_DIR = Path(__file__).parent.resolve()
_db_base_dir = Path(__file__).parent.parent.resolve()
_db_default_path = _db_base_dir / "backend" / "wnd.db"
_db_default_url = f"sqlite:///{str(_db_default_path).replace(chr(92), '/')}"

# ПРИНУДИТЕЛЬНАЯ ПРОВЕРКА: Всегда используем SQLite
# Это гарантирует, что приложение будет работать без PostgreSQL
if _env_db_url.startswith("postgresql") or (not _env_db_url.startswith("sqlite") and _env_db_url):
    print("=" * 60)
    print("⚠️  КРИТИЧЕСКОЕ ПРЕДУПРЕЖДЕНИЕ")
    print(f"   Обнаружен не-SQLite URL в .env: {_env_db_url}")
    print(f"   Принудительно переключаемся на SQLite")
    print(f"   Новый DATABASE_URL: {_db_default_url}")
    print("=" * 60)
    # Устанавливаем правильный URL в окружение
    os.environ["DATABASE_URL"] = _db_default_url
    _db_url = _db_default_url
elif _env_db_url.startswith("sqlite"):
    _db_url = _env_db_url
else:
    # Если не указан, используем SQLite по умолчанию
    _db_url = _db_default_url
    os.environ["DATABASE_URL"] = _db_url

# Теперь импортируем settings (он должен использовать правильный URL)
from config import settings

# Дополнительная проверка после импорта settings
if not settings.database_url.startswith('sqlite'):
    print("=" * 60)
    print("❌ КРИТИЧЕСКАЯ ОШИБКА: settings.database_url все еще не-SQLite!")
    print(f"   settings.database_url: {settings.database_url}")
    print(f"   Принудительно устанавливаем SQLite...")
    print("=" * 60)
    settings.database_url = _db_url

Base = declarative_base()

# Поддержка SQLite
print(f"Инициализация базы данных: {_db_url}")

# Всегда используем SQLite после проверки выше
if _db_url.startswith('sqlite'):
    # Извлекаем путь к файлу базы данных из URL
    db_path = _db_url.replace('sqlite:///', '').replace('sqlite://', '')
    # Создаем директорию, если её нет
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
        print(f"✓ Создана директория для базы данных: {db_dir}")
    
    print(f"✓ Использование SQLite: {db_path}")
    engine = create_engine(
        _db_url,
        connect_args={"check_same_thread": False},
        echo=False  # Установите в True для отладки SQL запросов
    )
else:
    # Это не должно произойти, но на всякий случай
    print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Не удалось переключиться на SQLite!")
    print(f"   Текущий URL: {_db_url}")
    raise ValueError(f"Неподдерживаемый тип базы данных: {_db_url}. Используйте SQLite.")

class Dialog(Base):
    __tablename__ = "dialogs"
    
    id = Column(Integer, primary_key=True, index=True)
    vnd_name = Column(String, nullable=True)  # Название ВНД
    user_id = Column(String, nullable=True)  # ID пользователя (можно расширить)
    messages = Column(Text, nullable=True, default="[]")  # JSON строка с сообщениями
    is_completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Инициализация базы данных - создание всех таблиц"""
    try:
        # Дополнительная проверка перед созданием таблиц
        if not _db_url.startswith('sqlite'):
            print("=" * 60)
            print("❌ КРИТИЧЕСКАЯ ОШИБКА: init_db вызван с не-SQLite URL!")
            print(f"   Текущий URL: {_db_url}")
            print("=" * 60)
            raise ValueError(f"Неподдерживаемый тип базы данных: {_db_url}. Используйте SQLite.")
        
        Base.metadata.create_all(bind=engine)
        print(f"✓ База данных инициализирована: {_db_url}")
    except Exception as e:
        print(f"❌ Ошибка при создании таблиц: {e}")
        print(f"   Используемый URL: {_db_url}")
        raise

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

