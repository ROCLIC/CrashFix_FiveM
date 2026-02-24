# -*- coding: utf-8 -*-
"""
Utilidades para operaciones del sistema operativo.

Este módulo proporciona funciones para interactuar con el sistema
operativo de forma segura, incluyendo ejecución de comandos y
gestión de procesos.
"""

import subprocess
import sys
import logging
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


def is_windows() -> bool:
    """Verifica si el sistema operativo es Windows."""
    return sys.platform == 'win32'


def run_powershell(
    command: str,
    timeout: int = 30,
    capture_output: bool = True
) -> Optional[str]:
    """
    Ejecuta un comando de PowerShell de forma segura.
    
    Args:
        command: Comando de PowerShell a ejecutar
        timeout: Tiempo máximo de espera en segundos
        capture_output: Si capturar la salida del comando
        
    Returns:
        Salida del comando como string, None si hay error o no es Windows
    """
    if not is_windows():
        logger.debug("PowerShell no disponible en este sistema operativo")
        return None
    
    try:
        result = subprocess.run(
            ['powershell', '-Command', command],
            capture_output=capture_output,
            text=True,
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if is_windows() else 0
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except subprocess.TimeoutExpired:
        logger.warning(f"Timeout ejecutando PowerShell: {command[:50]}...")
        return None
    except subprocess.SubprocessError as e:
        logger.error(f"Error ejecutando PowerShell: {e}")
        return None
    except FileNotFoundError:
        logger.error("PowerShell no encontrado en el sistema")
        return None


def run_command(
    command: List[str],
    timeout: int = 30,
    capture_output: bool = True
) -> Optional[subprocess.CompletedProcess]:
    """
    Ejecuta un comando del sistema de forma segura.
    
    Args:
        command: Lista con el comando y sus argumentos
        timeout: Tiempo máximo de espera en segundos
        capture_output: Si capturar la salida del comando
        
    Returns:
        CompletedProcess con el resultado, None si hay error
    """
    try:
        result = subprocess.run(
            command,
            capture_output=capture_output,
            text=True,
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if is_windows() else 0
        )
        return result
    except subprocess.TimeoutExpired:
        logger.warning(f"Timeout ejecutando comando: {' '.join(command[:3])}...")
        return None
    except subprocess.SubprocessError as e:
        logger.error(f"Error ejecutando comando: {e}")
        return None
    except FileNotFoundError:
        logger.error(f"Comando no encontrado: {command[0]}")
        return None


def get_running_processes() -> List[str]:
    """
    Obtiene la lista de procesos en ejecución.
    
    Returns:
        Lista de nombres de procesos en minúsculas
    """
    if not is_windows():
        return []
    
    try:
        result = run_command(['tasklist'], timeout=10)
        if result and result.returncode == 0:
            return result.stdout.lower().split('\n')
        return []
    except Exception as e:
        logger.error(f"Error obteniendo lista de procesos: {e}")
        return []


def is_process_running(process_name: str) -> bool:
    """
    Verifica si un proceso está en ejecución.
    
    Args:
        process_name: Nombre del proceso (ej: 'FiveM.exe')
        
    Returns:
        True si el proceso está corriendo, False en caso contrario
    """
    processes = get_running_processes()
    return any(process_name.lower() in proc for proc in processes)


def kill_process(process_name: str, force: bool = True) -> bool:
    """
    Termina un proceso por nombre.
    
    Args:
        process_name: Nombre del proceso a terminar
        force: Si usar terminación forzada
        
    Returns:
        True si el proceso fue terminado, False en caso contrario
    """
    if not is_windows():
        logger.debug("Terminación de procesos solo disponible en Windows")
        return False
    
    try:
        args = ['taskkill']
        if force:
            args.append('/F')
        args.extend(['/IM', process_name])
        
        result = run_command(args, timeout=10)
        if result and result.returncode == 0:
            logger.info(f"Proceso terminado: {process_name}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error terminando proceso {process_name}: {e}")
        return False


def kill_processes(process_names: List[str], force: bool = True) -> Dict[str, bool]:
    """
    Termina múltiples procesos.
    
    Args:
        process_names: Lista de nombres de procesos a terminar
        force: Si usar terminación forzada
        
    Returns:
        Diccionario con el resultado de cada proceso
    """
    results = {}
    for process in process_names:
        results[process] = kill_process(process, force)
    return results


def ping_host(
    host: str,
    count: int = 1,
    timeout_ms: int = 1000
) -> Optional[Dict]:
    """
    Realiza ping a un host.
    
    Args:
        host: Dirección IP o hostname
        count: Número de pings a enviar
        timeout_ms: Timeout en milisegundos
        
    Returns:
        Diccionario con resultados del ping, None si hay error
    """
    import re
    
    if is_windows():
        args = ['ping', '-n', str(count), '-w', str(timeout_ms), host]
    else:
        args = ['ping', '-c', str(count), '-W', str(timeout_ms // 1000), host]
    
    try:
        result = run_command(args, timeout=timeout_ms // 1000 + 5)
        if result is None:
            return None
        
        output = result.stdout
        success = result.returncode == 0
        
        # Extraer latencia
        latency = 0
        if success:
            # Patrón para Windows (español e inglés)
            match = re.search(
                r'(?:tiempo|time)[=<](\d+)\s*ms',
                output,
                re.IGNORECASE
            )
            if match:
                latency = int(match.group(1))
        
        return {
            'host': host,
            'success': success,
            'latency_ms': latency,
            'output': output
        }
    except Exception as e:
        logger.error(f"Error haciendo ping a {host}: {e}")
        return None


def get_system_info() -> Dict:
    """
    Obtiene información básica del sistema.
    
    Returns:
        Diccionario con información del sistema
    """
    import platform
    
    return {
        'platform': sys.platform,
        'system': platform.system(),
        'release': platform.release(),
        'version': platform.version(),
        'machine': platform.machine(),
        'processor': platform.processor(),
        'python_version': sys.version
    }
