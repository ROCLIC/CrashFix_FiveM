# -*- coding: utf-8 -*-
import os, re, logging
from pathlib import Path
from typing import List, Optional, Set

logger = logging.getLogger(__name__)
SAFE_FILENAME_PATTERN = re.compile(r'^[\w\-. ]+$')
VALID_REPAIR_IDS: Set[int] = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15}

def validate_backup_path(path: str, backup_folder: str) -> bool:
    if not path or not backup_folder: return False
    try:
        return str(Path(path).resolve()).startswith(str(Path(backup_folder).resolve()))
    except (ValueError, OSError) as e:
        logger.error(f"Error validating backup path: {e}")
        return False

def validate_repair_ids(repair_ids: List) -> List[int]:
    if not repair_ids: return []
    valid = []
    for rid in repair_ids:
        try:
            r = int(rid)
            if r in VALID_REPAIR_IDS: valid.append(r)
            else: logger.warning(f"Invalid repair ID ignored: {rid}")
        except (ValueError, TypeError): logger.warning(f"Non-numeric repair ID ignored: {rid}")
    return valid

def sanitize_filename(filename: str) -> Optional[str]:
    if not filename: return None
    filename = os.path.basename(filename)
    if SAFE_FILENAME_PATTERN.match(filename): return filename
    sanitized = re.sub(r'[^\w\-. ]', '_', filename).strip('. ')
    return sanitized if sanitized and sanitized not in ('.', '..') else None

def validate_ip_address(ip: str) -> bool:
    if not ip: return False
    return bool(re.match(r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$', ip))

def validate_port(port) -> bool:
    try: return 1 <= int(port) <= 65535
    except (ValueError, TypeError): return False

def sanitize_path_component(component: str) -> str:
    if not component: return ''
    return re.sub(r'[<>:"/\\|?*]', '_', component).strip('. ')
