# -*- coding: utf-8 -*-
"""
Utilidades para operaciones de archivos y directorios.

Este módulo proporciona funciones seguras para manipulación de archivos,
incluyendo validación de rutas para prevenir ataques de path traversal.
"""

import os
import shutil
import logging
from pathlib import Path
from typing import Optional, Union

logger = logging.getLogger(__name__)


def get_folder_size(folder: str) -> int:
    """
    Calcula el tamaño total de una carpeta en bytes.
    
    Args:
        folder: Ruta a la carpeta
        
    Returns:
        Tamaño total en bytes, 0 si hay error
    """
    total = 0
    try:
        for dirpath, dirnames, filenames in os.walk(folder):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    total += os.path.getsize(filepath)
                except (OSError, IOError) as e:
                    logger.debug(f"No se pudo obtener tamaño de {filepath}: {e}")
    except (OSError, IOError) as e:
        logger.warning(f"Error al recorrer carpeta {folder}: {e}")
    return total


def validate_path_safety(path: str, allowed_base: str) -> bool:
    """
    Valida que una ruta esté dentro de un directorio base permitido.
    
    Previene ataques de path traversal verificando que la ruta
    resuelta esté dentro del directorio permitido.
    
    Args:
        path: Ruta a validar
        allowed_base: Directorio base permitido
        
    Returns:
        True si la ruta es segura, False en caso contrario
    """
    try:
        # Resolver rutas absolutas
        resolved_path = Path(path).resolve()
        resolved_base = Path(allowed_base).resolve()
        
        # Verificar que la ruta esté dentro del directorio base
        return str(resolved_path).startswith(str(resolved_base))
    except (ValueError, OSError) as e:
        logger.warning(f"Error validando ruta {path}: {e}")
        return False


def ensure_directory_exists(directory: str) -> bool:
    """
    Crea un directorio si no existe.
    
    Args:
        directory: Ruta del directorio a crear
        
    Returns:
        True si el directorio existe o fue creado, False en caso de error
    """
    try:
        os.makedirs(directory, exist_ok=True)
        return True
    except (OSError, IOError) as e:
        logger.error(f"Error creando directorio {directory}: {e}")
        return False


def safe_remove_file(filepath: str) -> bool:
    """
    Elimina un archivo de forma segura.
    
    Args:
        filepath: Ruta del archivo a eliminar
        
    Returns:
        True si se eliminó correctamente, False en caso contrario
    """
    try:
        if os.path.isfile(filepath):
            os.remove(filepath)
            logger.info(f"Archivo eliminado: {filepath}")
            return True
        else:
            logger.warning(f"El archivo no existe: {filepath}")
            return False
    except (OSError, IOError, PermissionError) as e:
        logger.error(f"Error eliminando archivo {filepath}: {e}")
        return False


def safe_remove_directory(directory: str) -> bool:
    """
    Elimina un directorio y su contenido de forma segura.
    
    Args:
        directory: Ruta del directorio a eliminar
        
    Returns:
        True si se eliminó correctamente, False en caso contrario
    """
    try:
        if os.path.isdir(directory):
            shutil.rmtree(directory)
            logger.info(f"Directorio eliminado: {directory}")
            return True
        else:
            logger.warning(f"El directorio no existe: {directory}")
            return False
    except (OSError, IOError, PermissionError) as e:
        logger.error(f"Error eliminando directorio {directory}: {e}")
        return False


def backup_item(
    source: str,
    backup_name: str,
    backup_folder: str,
    category: str = 'General',
    timestamp: Optional[str] = None
) -> Optional[str]:
    """
    Crea un backup de un archivo o directorio.
    
    Args:
        source: Ruta del archivo/directorio a respaldar
        backup_name: Nombre base para el backup
        backup_folder: Carpeta raíz de backups
        category: Categoría del backup (Cache, Mods, Config, etc.)
        timestamp: Timestamp para el nombre del backup (opcional)
        
    Returns:
        Ruta del backup creado, None si hubo error
    """
    if not os.path.exists(source):
        logger.warning(f"Origen no existe para backup: {source}")
        return None
    
    # Generar timestamp si no se proporciona
    if timestamp is None:
        from config import get_timestamp
        timestamp = get_timestamp()
    
    # Crear carpeta de categoría
    category_folder = os.path.join(backup_folder, category)
    if not ensure_directory_exists(category_folder):
        return None
    
    # Construir ruta de destino
    backup_path = os.path.join(category_folder, f"{backup_name}_{timestamp}")
    
    try:
        if os.path.isdir(source):
            shutil.copytree(source, backup_path)
        else:
            # Preservar extensión del archivo
            ext = os.path.splitext(source)[1]
            backup_path_with_ext = f"{backup_path}{ext}"
            shutil.copy2(source, backup_path_with_ext)
            backup_path = backup_path_with_ext
        
        logger.info(f"Backup creado: {backup_path}")
        return backup_path
        
    except (OSError, IOError, PermissionError) as e:
        logger.error(f"Error creando backup de {source}: {e}")
        return None


def read_file_safely(
    filepath: str,
    encoding: str = 'utf-8',
    errors: str = 'ignore'
) -> Optional[str]:
    """
    Lee un archivo de texto de forma segura.
    
    Args:
        filepath: Ruta del archivo
        encoding: Codificación del archivo
        errors: Manejo de errores de codificación
        
    Returns:
        Contenido del archivo, None si hay error
    """
    try:
        with open(filepath, 'r', encoding=encoding, errors=errors) as f:
            return f.read()
    except (OSError, IOError) as e:
        logger.error(f"Error leyendo archivo {filepath}: {e}")
        return None


def write_file_safely(
    filepath: str,
    content: str,
    encoding: str = 'utf-8'
) -> bool:
    """
    Escribe contenido a un archivo de forma segura.
    
    Args:
        filepath: Ruta del archivo
        content: Contenido a escribir
        encoding: Codificación del archivo
        
    Returns:
        True si se escribió correctamente, False en caso contrario
    """
    try:
        # Asegurar que el directorio padre existe
        parent_dir = os.path.dirname(filepath)
        if parent_dir and not ensure_directory_exists(parent_dir):
            return False
        
        with open(filepath, 'w', encoding=encoding) as f:
            f.write(content)
        logger.info(f"Archivo escrito: {filepath}")
        return True
    except (OSError, IOError) as e:
        logger.error(f"Error escribiendo archivo {filepath}: {e}")
        return False


def get_file_info(filepath: str) -> Optional[dict]:
    """
    Obtiene información sobre un archivo.
    
    Args:
        filepath: Ruta del archivo
        
    Returns:
        Diccionario con información del archivo, None si hay error
    """
    try:
        stat = os.stat(filepath)
        return {
            'path': filepath,
            'name': os.path.basename(filepath),
            'size': stat.st_size,
            'size_mb': round(stat.st_size / (1024 * 1024), 2),
            'modified': stat.st_mtime,
            'is_file': os.path.isfile(filepath),
            'is_dir': os.path.isdir(filepath)
        }
    except (OSError, IOError) as e:
        logger.error(f"Error obteniendo info de {filepath}: {e}")
        return None
