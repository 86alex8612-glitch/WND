from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os
from pathlib import Path

load_dotenv()

# Определяем корневую директорию проекта (родительская от backend)
BASE_DIR = Path(__file__).parent.parent.resolve()

# Путь к базе данных SQLite (по умолчанию)
DEFAULT_DB_PATH = BASE_DIR / "backend" / "wnd.db"
# Конвертируем путь в формат, понятный SQLite (заменяем обратные слэши на прямые)
DEFAULT_DB_URL = f"sqlite:///{str(DEFAULT_DB_PATH).replace(chr(92), '/')}"

# Получаем DATABASE_URL из переменных окружения и обрабатываем
_env_db_url = os.getenv("DATABASE_URL", "").strip()

# Принудительно используем SQLite, если указан PostgreSQL или URL пустой
if _env_db_url.startswith("postgresql"):
    print(f"⚠️  Обнаружен PostgreSQL URL в .env, принудительно используется SQLite")
    print(f"   DATABASE_URL будет: {DEFAULT_DB_URL}")
    _final_db_url = DEFAULT_DB_URL
elif _env_db_url.startswith("sqlite"):
    _final_db_url = _env_db_url
else:
    # Если не указан или пустой, используем SQLite по умолчанию
    _final_db_url = DEFAULT_DB_URL

class Settings(BaseSettings):
    database_url: str = _final_db_url
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    secret_key: str = os.getenv("SECRET_KEY", "default-secret-key")
    
    # Пути к папкам (абсолютные пути относительно корня проекта)
    fz_folder: str = str(BASE_DIR / "FZ")
    fzyur_folder: str = str(BASE_DIR / "FZYur")
    in_folder: str = str(BASE_DIR / "IN")
    out_folder: str = str(BASE_DIR / "OUT")
    new_doc_folder: str = str(BASE_DIR / "new-doc")
    
    class Config:
        env_file = ".env"

settings = Settings()

try:
    from path_config import apply_paths_to_settings
    _resolved_paths = apply_paths_to_settings()
    print(f"Рабочая папка: {_resolved_paths.get('work_folder')}")
except Exception as exc:
    print(f"⚠️  Не удалось загрузить config.cfg: {exc}")





