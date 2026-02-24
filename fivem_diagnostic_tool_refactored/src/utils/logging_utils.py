# -*- coding: utf-8 -*-
"""
Utilidades de logging para FiveM Diagnostic Tool.

Proporciona un sistema de logging centralizado con soporte
para archivo y consola.
"""

import os
import logging
from datetime import datetime
from typing import Optional


class Logger:
    """
    Clase de logging centralizada para la aplicación.
    
    Attributes:
        name: Nombre del logger
        log_file: Ruta del archivo de log
        logger: Instancia del logger de Python
    """
    
    _instances = {}
    
    def __new__(cls, name: str = 'fivem_diagnostic', log_dir: Optional[str] = None):
        """Implementa patrón singleton por nombre de logger."""
        if name not in cls._instances:
            instance = super().__new__(cls)
            cls._instances[name] = instance
        return cls._instances[name]
    
    def __init__(self, name: str = 'fivem_diagnostic', log_dir: Optional[str] = None):
        """
        Inicializa el logger.
        
        Args:
            name: Nombre del logger
            log_dir: Directorio para archivos de log
        """
        if hasattr(self, '_initialized'):
            return
        
        self.name = name
        self.logger = logging.getLogger(name)
        
        # Evitar duplicación de handlers
        if not self.logger.handlers:
            self.logger.setLevel(logging.DEBUG)
            
            # Handler para consola
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_format = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s',
                datefmt='%H:%M:%S'
            )
            console_handler.setFormatter(console_format)
            self.logger.addHandler(console_handler)
            
            # Handler para archivo si se especifica directorio
            if log_dir:
                self._setup_file_handler(log_dir)
        
        self._initialized = True
    
    def _setup_file_handler(self, log_dir: str) -> None:
        """Configura el handler de archivo."""
        try:
            os.makedirs(log_dir, exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_file = os.path.join(log_dir, f'FiveM_Diagnostic_{timestamp}.log')
            
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_format = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
            )
            file_handler.setFormatter(file_format)
            self.logger.addHandler(file_handler)
            
            self.log_file = log_file
        except (OSError, IOError) as e:
            self.logger.warning(f"No se pudo crear archivo de log: {e}")
            self.log_file = None
    
    def debug(self, message: str) -> None:
        """Log de nivel DEBUG."""
        self.logger.debug(message)
    
    def info(self, message: str) -> None:
        """Log de nivel INFO."""
        self.logger.info(message)
    
    def warning(self, message: str) -> None:
        """Log de nivel WARNING."""
        self.logger.warning(message)
    
    def error(self, message: str) -> None:
        """Log de nivel ERROR."""
        self.logger.error(message)
    
    def critical(self, message: str) -> None:
        """Log de nivel CRITICAL."""
        self.logger.critical(message)
    
    def exception(self, message: str) -> None:
        """Log de excepción con traceback."""
        self.logger.exception(message)


# Logger global de la aplicación
_app_logger: Optional[Logger] = None


def get_logger(log_dir: Optional[str] = None) -> Logger:
    """
    Obtiene la instancia del logger de la aplicación.
    
    Args:
        log_dir: Directorio para archivos de log (solo se usa en primera llamada)
        
    Returns:
        Instancia del Logger
    """
    global _app_logger
    if _app_logger is None:
        _app_logger = Logger('fivem_diagnostic', log_dir)
    return _app_logger


def setup_logging(log_dir: str) -> Logger:
    """
    Configura el sistema de logging.
    
    Args:
        log_dir: Directorio para archivos de log
        
    Returns:
        Instancia del Logger configurado
    """
    return get_logger(log_dir)
