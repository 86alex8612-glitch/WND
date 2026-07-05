import os
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
project_root = backend_dir.parent
sys.path.insert(0, str(backend_dir))
os.chdir(project_root)

from config import settings

print("    DATABASE_URL:", settings.database_url)
