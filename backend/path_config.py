"""
Чтение и запись рабочих путей из config.cfg в корне проекта.
"""
from __future__ import annotations

import configparser
import os
import re
from pathlib import Path
from typing import Dict, List, Optional

BASE_DIR = Path(__file__).parent.parent.resolve()
CONFIG_FILE = BASE_DIR / "config.cfg"

DISPLAY_SUBFOLDERS = ("IN", "FZYur", "FZ", "OUT", "new-doc")

FOLDER_DESCRIPTIONS: Dict[str, str] = {
    "IN": "Входящие документы: загрузка ВНД для анализа, поиска и создания",
    "FZYur": "База ГОСТ и отраслевых стандартов (нормативная база)",
    "FZ": "Федеральные законы и нормативные акты",
    "OUT": "Сохранённые отчёты, PDF и результаты работы",
    "new-doc": "Проекты новых и переработанных ВНД",
}

_WINDOWS_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")


def default_work_folder() -> Path:
    env_value = (os.environ.get("WND_WORK_FOLDER") or "").strip()
    if env_value:
        return Path(env_value).expanduser().resolve()
    if os.name == "nt":
        return Path(r"C:\WND")
    return BASE_DIR


def is_windows_absolute_path(value: str) -> bool:
    return bool(_WINDOWS_PATH_RE.match((value or "").strip()))


def is_browse_folder_available() -> bool:
    """Диалог «Обзор» работает только на рабочем столе Windows с GUI."""
    if os.name != "nt":
        return False
    if (os.environ.get("DISPLAY") or "").strip():
        return True
    if os.environ.get("WND_ALLOW_BROWSE", "").strip().lower() in {"1", "true", "yes"}:
        return True
    # На Windows-сервере без рабочего стола tkinter обычно недоступен.
    return True


def _normalize_work_folder(value: str) -> str:
    text = (value or "").strip().strip('"').strip("'")
    if not text:
        return str(default_work_folder())
    if os.name != "nt" and is_windows_absolute_path(text):
        return str(default_work_folder())
    return str(Path(text).expanduser().resolve())


def resolve_paths(work_folder: str) -> Dict[str, str]:
    root = Path(_normalize_work_folder(work_folder))
    return {
        "work_folder": str(root),
        "in_folder": str(root / "IN"),
        "fzyur_folder": str(root / "FZYur"),
        "fz_folder": str(root / "FZ"),
        "out_folder": str(root / "OUT"),
        "new_doc_folder": str(root / "new-doc"),
    }


def ensure_directories(paths: Dict[str, str]) -> None:
    for key in ("work_folder", "in_folder", "fzyur_folder", "fz_folder", "out_folder", "new_doc_folder"):
        Path(paths[key]).mkdir(parents=True, exist_ok=True)
    Path(paths["in_folder"], "create").mkdir(parents=True, exist_ok=True)
    Path(paths["in_folder"], "search").mkdir(parents=True, exist_ok=True)


def read_work_folder() -> str:
    if not CONFIG_FILE.is_file():
        return str(write_work_folder(str(default_work_folder()))["work_folder"])

    parser = configparser.ConfigParser()
    parser.read(CONFIG_FILE, encoding="utf-8")
    if parser.has_option("paths", "work_folder"):
        return _normalize_work_folder(parser.get("paths", "work_folder"))
    return str(default_work_folder())


def write_work_folder(work_folder: str) -> Dict[str, str]:
    normalized = _normalize_work_folder(work_folder)
    paths = resolve_paths(normalized)
    ensure_directories(paths)

    parser = configparser.ConfigParser()
    parser["paths"] = {"work_folder": normalized}
    with CONFIG_FILE.open("w", encoding="utf-8") as handle:
        parser.write(handle)

    return paths


def load_paths() -> Dict[str, str]:
    work_folder = read_work_folder()
    paths = resolve_paths(work_folder)
    ensure_directories(paths)
    return paths


def reset_to_defaults() -> Dict[str, str]:
    return write_work_folder(str(default_work_folder()))


def build_display_folders(work_folder: str) -> List[Dict[str, str]]:
    root = Path(_normalize_work_folder(work_folder))
    return [
        {
            "name": name,
            "description": FOLDER_DESCRIPTIONS.get(name, ""),
            "path": str(root / name),
        }
        for name in DISPLAY_SUBFOLDERS
    ]


def browse_folder_dialog(initial_dir: str = "") -> Optional[str]:
    """Нативный диалог выбора папки (только Windows с GUI)."""
    if not is_browse_folder_available():
        return None

    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        return None

    initial = (initial_dir or "").strip().strip('"').strip("'")
    if initial and not Path(initial).is_dir():
        initial = str(Path(initial).parent) if Path(initial).parent.is_dir() else ""

    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass
    try:
        selected = filedialog.askdirectory(
            title="Выберите рабочую папку",
            initialdir=initial or None,
            mustexist=False,
        )
    except Exception:
        selected = None
    finally:
        root.destroy()

    if not selected:
        return None
    return str(Path(selected).resolve())


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
    paths = load_paths()
    display_folders = build_display_folders(paths["work_folder"])
    browse_available = is_browse_folder_available()
    return {
        "work_folder": paths["work_folder"],
        "default_work_folder": str(default_work_folder()),
        "paths": paths,
        "display_folders": display_folders,
        "config_file": str(CONFIG_FILE),
        "browse_folder_available": browse_available,
        "is_server": os.name != "nt",
        "browse_folder_hint": (
            "На сервере Linux укажите путь вручную, например /home/user/wnd"
            if not browse_available
            else "Можно выбрать папку через диалог Windows"
        ),
    }
