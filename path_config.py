"""
Пути к данным приложения.

Корень хранилища задаётся в config.cfg:
  data_root — Linux (Beget): /opt/WND/data
  data_win  — Windows:       C:\\WND

Переменная окружения WND_DATA_ROOT имеет приоритет над config.cfg.
"""
from __future__ import annotations

import configparser
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

BASE_DIR = Path(__file__).parent.parent.resolve()
CONFIG_FILE = BASE_DIR / "config.cfg"

DEFAULT_LINUX_DATA_ROOT = "/opt/WND/data"
DEFAULT_WINDOWS_DATA_ROOT = r"C:\WND"

DISPLAY_SUBFOLDERS = ("IN", "FZYur", "FZ", "OUT", "new-doc")

FOLDER_DESCRIPTIONS: Dict[str, str] = {
    "IN": "Документы ВНД для анализа и поиска",
    "FZYur": "ГОСТ и отраслевые стандарты (после загрузки обновляется индекс)",
    "FZ": "Федеральные законы (после загрузки обновляется индекс)",
    "OUT": "Готовые отчёты — скачивание через браузер",
    "new-doc": "Проекты новых и переработанных ВНД",
}

_WINDOWS_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")


def is_windows_absolute_path(value: str) -> bool:
    return bool(_WINDOWS_PATH_RE.match((value or "").strip()))


def _normalize_data_root(value: str) -> str:
    text = (value or "").strip().strip('"').strip("'")
    if not text:
        return str(configured_data_root_for_os())
    if os.name != "nt" and is_windows_absolute_path(text):
        return str(configured_data_root_for_os())
    if os.name == "nt" and text.startswith("/"):
        return str(configured_data_root_for_os())
    return str(Path(text).expanduser().resolve())


def read_configured_roots() -> Tuple[str, str]:
    """Прочитать data_root и data_win из config.cfg."""
    linux_root = DEFAULT_LINUX_DATA_ROOT
    win_root = DEFAULT_WINDOWS_DATA_ROOT

    if CONFIG_FILE.is_file():
        parser = configparser.ConfigParser()
        parser.read(CONFIG_FILE, encoding="utf-8")
        if parser.has_section("paths"):
            if parser.has_option("paths", "data_root"):
                linux_root = parser.get("paths", "data_root").strip()
            if parser.has_option("paths", "data_win"):
                win_root = parser.get("paths", "data_win").strip()
            # Обратная совместимость: work_folder → активный ключ ОС
            if parser.has_option("paths", "work_folder"):
                legacy = parser.get("paths", "work_folder").strip()
                if os.name == "nt":
                    win_root = legacy
                else:
                    linux_root = legacy

    return linux_root, win_root


def configured_data_root_for_os() -> Path:
    """Жёсткий путь хранилища для текущей ОС из config.cfg."""
    linux_root, win_root = read_configured_roots()
    raw = win_root if os.name == "nt" else linux_root
    return Path(raw).expanduser().resolve()


def default_data_root() -> Path:
    env_value = (os.environ.get("WND_DATA_ROOT") or os.environ.get("WND_WORK_FOLDER") or "").strip()
    if env_value:
        return Path(env_value).expanduser().resolve()
    return configured_data_root_for_os()


def resolve_paths(data_root: str) -> Dict[str, str]:
    root = Path(_normalize_data_root(data_root))
    in_folder = root / "IN"
    return {
        "data_root": str(root),
        "work_folder": str(root),
        "in_folder": str(in_folder),
        "in_create_folder": str(in_folder / "create"),
        "fzyur_folder": str(root / "FZYur"),
        "fz_folder": str(root / "FZ"),
        "out_folder": str(root / "OUT"),
        "new_doc_folder": str(root / "new-doc"),
    }


def ensure_directories(paths: Dict[str, str]) -> None:
    for key in (
        "data_root",
        "in_folder",
        "in_create_folder",
        "fzyur_folder",
        "fz_folder",
        "out_folder",
        "new_doc_folder",
    ):
        Path(paths[key]).mkdir(parents=True, exist_ok=True)
    Path(paths["in_folder"], "search").mkdir(parents=True, exist_ok=True)


def is_paths_locked_by_env() -> bool:
    return bool((os.environ.get("WND_DATA_ROOT") or os.environ.get("WND_WORK_FOLDER") or "").strip())


def is_browse_folder_available() -> bool:
    if os.name != "nt" or is_paths_locked_by_env():
        return False
    try:
        import tkinter  # noqa: F401
        return True
    except ImportError:
        return False


def browse_folder_dialog(initial_dir: Optional[str] = None) -> Optional[str]:
    if not is_browse_folder_available():
        return None

    import tkinter as tk
    from tkinter import filedialog

    start_dir = _normalize_data_root(initial_dir or read_data_root())
    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass
    selected = filedialog.askdirectory(
        parent=root,
        initialdir=start_dir,
        title="Выберите рабочую папку",
    )
    root.destroy()
    return selected or None


def _write_config_roots(linux_root: str, win_root: str) -> None:
    parser = configparser.ConfigParser()
    if CONFIG_FILE.is_file():
        parser.read(CONFIG_FILE, encoding="utf-8")
    if "paths" not in parser:
        parser["paths"] = {}

    parser["paths"]["data_root"] = linux_root
    parser["paths"]["data_win"] = win_root
    if "work_folder" in parser["paths"]:
        del parser["paths"]["work_folder"]

    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as handle:
        parser.write(handle)


def write_data_root(value: str) -> Dict[str, str]:
    if is_paths_locked_by_env():
        raise ValueError(
            "Рабочая папка задана переменной окружения WND_DATA_ROOT и не может быть изменена через интерфейс"
        )

    normalized = _normalize_data_root(value)
    paths = resolve_paths(normalized)
    ensure_directories(paths)

    linux_root, win_root = read_configured_roots()
    if os.name == "nt":
        win_root = normalized
    else:
        linux_root = normalized
    _write_config_roots(linux_root, win_root)

    return paths


def reset_data_root_to_default() -> Dict[str, str]:
    if is_paths_locked_by_env():
        raise ValueError(
            "Рабочая папка задана переменной окружения WND_DATA_ROOT и не может быть сброшена через интерфейс"
        )
    return write_data_root(str(configured_data_root_for_os()))


def read_data_root() -> str:
    env_value = (os.environ.get("WND_DATA_ROOT") or os.environ.get("WND_WORK_FOLDER") or "").strip()
    if env_value:
        return _normalize_data_root(env_value)
    return str(configured_data_root_for_os())


def read_paths() -> Dict[str, str]:
    """Прочитать пути без создания папок (для /api/config)."""
    return resolve_paths(read_data_root())


def load_paths() -> Dict[str, str]:
    paths = read_paths()
    ensure_directories(paths)
    return paths


def build_display_folders(data_root: str) -> List[Dict[str, str]]:
    root = Path(_normalize_data_root(data_root))
    return [
        {
            "name": name,
            "description": FOLDER_DESCRIPTIONS.get(name, ""),
            "path": str(root / name),
        }
        for name in DISPLAY_SUBFOLDERS
    ]


def apply_paths_to_settings() -> Dict[str, str]:
    from config import settings

    paths = load_paths()
    settings.fz_folder = paths["fz_folder"]
    settings.fzyur_folder = paths["fzyur_folder"]
    settings.in_folder = paths["in_folder"]
    settings.out_folder = paths["out_folder"]
    settings.new_doc_folder = paths["new_doc_folder"]
    return paths


def get_config_payload() -> Dict:
    try:
        paths = read_paths()
    except Exception:
        paths = resolve_paths(str(default_data_root()))

    linux_root, win_root = read_configured_roots()
    data_root = paths["data_root"]
    is_windows = os.name == "nt"
    paths_editable = not is_paths_locked_by_env()
    return {
        "data_root": data_root,
        "work_folder": data_root,
        "configured_linux_root": linux_root,
        "configured_windows_root": win_root,
        "default_data_root": str(default_data_root()),
        "paths": paths,
        "display_folders": build_display_folders(data_root),
        "config_file": str(CONFIG_FILE),
        "paths_editable": paths_editable,
        "paths_locked_by_env": is_paths_locked_by_env(),
        "folder_browse_available": is_browse_folder_available(),
        "upload_via_browser": True,
        "download_via_browser": True,
        "is_local_windows": is_windows,
        "data_root_label": "Рабочая папка" if is_windows else "Папка данных на сервере",
        "settings_hint": (
            "Пути хранилища задаются в config.cfg (data_win на Windows, data_root на Linux). "
            "При сохранении создаются подпапки IN, FZYur, FZ, OUT и new-doc."
            if paths_editable
            else "Рабочая папка задана на сервере (WND_DATA_ROOT) и доступна только для просмотра."
        ),
        "file_browse_available": is_windows,
    }
