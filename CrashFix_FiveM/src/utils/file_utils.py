# -*- coding: utf-8 -*-
import os, shutil, logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

def get_folder_size(folder: str) -> int:
    total = 0
    try:
        for dirpath, _, filenames in os.walk(folder):
            for filename in filenames:
                try: total += os.path.getsize(os.path.join(dirpath, filename))
                except (OSError, IOError): pass
    except (OSError, IOError): pass
    return total

def validate_path_safety(path: str, allowed_base: str) -> bool:
    try:
        return str(Path(path).resolve()).startswith(str(Path(allowed_base).resolve()))
    except (ValueError, OSError):
        return False

def ensure_directory_exists(directory: str) -> bool:
    if not directory: return False
    try:
        os.makedirs(directory, exist_ok=True)
        return True
    except (OSError, IOError) as e:
        logger.error(f"Error creating directory {directory}: {e}")
        return False

def safe_remove_file(filepath: str) -> bool:
    try:
        if os.path.isfile(filepath):
            os.remove(filepath)
            return True
        return False
    except (OSError, IOError, PermissionError) as e:
        logger.error(f"Error removing file {filepath}: {e}")
        return False

def safe_remove_directory(directory: str) -> bool:
    try:
        if os.path.isdir(directory):
            shutil.rmtree(directory)
            return True
        return False
    except (OSError, IOError, PermissionError) as e:
        logger.error(f"Error removing directory {directory}: {e}")
        return False

def backup_item(source: str, backup_name: str, backup_folder: str, category: str = 'General', timestamp: Optional[str] = None) -> Optional[str]:
    if not os.path.exists(source): return None
    if timestamp is None:
        from config import get_timestamp
        timestamp = get_timestamp()
    category_folder = os.path.join(backup_folder, category)
    if not ensure_directory_exists(category_folder): return None
    backup_path = os.path.join(category_folder, f"{backup_name}_{timestamp}")
    try:
        if os.path.isdir(source):
            shutil.copytree(source, backup_path)
        else:
            ext = os.path.splitext(source)[1]
            backup_path = f"{backup_path}{ext}"
            shutil.copy2(source, backup_path)
        return backup_path
    except (OSError, IOError, PermissionError) as e:
        logger.error(f"Error creating backup of {source}: {e}")
        return None
