# -*- coding: utf-8 -*-
"""
Utilidades de validación para FiveM Diagnostic Tool.

Proporciona funciones de validación y sanitización para
prevenir vulnerabilidades de seguridad.
"""

import os
import re
import logging
from pathlib import Path
from typing import List, Optional, Set

logger = logging.getLogger(__name__)

# Caracteres permitidos en nombres de archivo
SAFE_FILENAME_PATTERN = re.compile(r'^[\w\-. ]+$')

# IDs de reparación válidos
VALID_REPAIR_IDS: Set[int] = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13}


def validate_backup_path(path: str, backup_folder: str) -> bool:
    """
    Valida que una ruta de backup sea segura.
    
    Previene ataques de path traversal verificando que la ruta
    esté dentro del directorio de backups permitido.
    
    Args:
        path: Ruta del backup a validar
        backup_folder: Carpeta raíz de backups permitida
        
    Returns:
        True si la ruta es válida y segura, False en caso contrario
    """
    if not path or not backup_folder:
        logger.warning("Ruta o carpeta de backup vacía")
        return False
    
    try:
        # Resolver rutas absolutas para evitar path traversal
        resolved_path = Path(path).resolve()
        resolved_backup = Path(backup_folder).resolve()
        
        # Verificar que la ruta esté dentro del directorio de backups
        is_safe = str(resolved_path).startswith(str(resolved_backup))
        
        if not is_safe:
            logger.warning(f"Intento de acceso fuera del directorio de backups: {path}")
        
        return is_safe
        
    except (ValueError, OSError) as e:
        logger.error(f"Error validando ruta de backup: {e}")
        return False


def validate_repair_ids(repair_ids: List[int]) -> List[int]:
    """
    Valida y filtra IDs de reparación.
    
    Args:
        repair_ids: Lista de IDs de reparación a validar
        
    Returns:
        Lista de IDs válidos
    """
    if not repair_ids:
        return []
    
    valid_ids = []
    for repair_id in repair_ids:
        try:
            rid = int(repair_id)
            if rid in VALID_REPAIR_IDS:
                valid_ids.append(rid)
            else:
                logger.warning(f"ID de reparación inválido ignorado: {repair_id}")
        except (ValueError, TypeError):
            logger.warning(f"ID de reparación no numérico ignorado: {repair_id}")
    
    return valid_ids


def sanitize_filename(filename: str) -> Optional[str]:
    """
    Sanitiza un nombre de archivo para uso seguro.
    
    Args:
        filename: Nombre de archivo a sanitizar
        
    Returns:
        Nombre de archivo sanitizado, None si no es válido
    """
    if not filename:
        return None
    
    # Eliminar caracteres de ruta
    filename = os.path.basename(filename)
    
    # Verificar patrón seguro
    if SAFE_FILENAME_PATTERN.match(filename):
        return filename
    
    # Intentar sanitizar
    sanitized = re.sub(r'[^\w\-. ]', '_', filename)
    
    if sanitized and sanitized != '.' and sanitized != '..':
        logger.debug(f"Nombre de archivo sanitizado: {filename} -> {sanitized}")
        return sanitized
    
    logger.warning(f"Nombre de archivo inválido: {filename}")
    return None


def validate_json_schema(data: dict, required_fields: List[str]) -> bool:
    """
    Valida que un diccionario contenga los campos requeridos.
    
    Args:
        data: Diccionario a validar
        required_fields: Lista de campos requeridos
        
    Returns:
        True si todos los campos están presentes, False en caso contrario
    """
    if not isinstance(data, dict):
        return False
    
    missing = [field for field in required_fields if field not in data]
    
    if missing:
        logger.warning(f"Campos faltantes en JSON: {missing}")
        return False
    
    return True


def validate_ip_address(ip: str) -> bool:
    """
    Valida que una cadena sea una dirección IP válida.
    
    Args:
        ip: Cadena a validar
        
    Returns:
        True si es una IP válida, False en caso contrario
    """
    if not ip:
        return False
    
    # Patrón para IPv4
    ipv4_pattern = re.compile(
        r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
        r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
    )
    
    return bool(ipv4_pattern.match(ip))


def validate_port(port: int) -> bool:
    """
    Valida que un número sea un puerto válido.
    
    Args:
        port: Número de puerto a validar
        
    Returns:
        True si es un puerto válido (1-65535), False en caso contrario
    """
    try:
        port_num = int(port)
        return 1 <= port_num <= 65535
    except (ValueError, TypeError):
        return False


def validate_profile_name(profile: str) -> bool:
    """
    Valida que un nombre de perfil sea válido.
    
    Args:
        profile: Nombre del perfil a validar
        
    Returns:
        True si es un perfil válido, False en caso contrario
    """
    valid_profiles = {'low', 'medium', 'high', 'ultra'}
    return profile.lower() in valid_profiles if profile else False


def sanitize_path_component(component: str) -> str:
    """
    Sanitiza un componente de ruta.
    
    Args:
        component: Componente de ruta a sanitizar
        
    Returns:
        Componente sanitizado
    """
    if not component:
        return ''
    
    # Eliminar caracteres peligrosos
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', component)
    
    # Eliminar puntos al inicio y final
    sanitized = sanitized.strip('. ')
    
    return sanitized
