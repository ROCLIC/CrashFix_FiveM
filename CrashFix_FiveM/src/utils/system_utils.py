# -*- coding: utf-8 -*-
"""
Utilidades para operaciones del sistema operativo.

Proporciona wrappers seguros para ejecutar comandos del sistema,
gestionar procesos y realizar operaciones de red, con soporte
multiplataforma (Windows/Linux/macOS).
"""

import subprocess
import sys
import logging
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


def is_windows() -> bool:
    """Verifica si el sistema operativo es Windows."""
    return sys.platform == 'win32'


def _subprocess_flags() -> dict:
    """Devuelve kwargs extra para subprocess segun la plataforma."""
    if is_windows():
        return {'creationflags': subprocess.CREATE_NO_WINDOW}
    return {}


def run_powershell(
    command: str,
    timeout: int = 30,
    capture_output: bool = True
) -> Optional[str]:
    """
    Ejecuta un comando de PowerShell de forma segura (solo Windows).

    Retorna la salida stdout como string, o None si falla.
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
            **_subprocess_flags()
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

    Retorna el CompletedProcess o None si falla.
    """
    try:
        result = subprocess.run(
            command,
            capture_output=capture_output,
            text=True,
            timeout=timeout,
            **_subprocess_flags()
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
    Obtiene la lista de procesos en ejecucion.
    Soporta Windows (tasklist) y Linux/macOS (ps).
    """
    if is_windows():
        try:
            result = run_command(['tasklist'], timeout=10)
            if result and result.returncode == 0:
                return result.stdout.lower().split('\n')
            return []
        except Exception as e:
            logger.error(f"Error obteniendo lista de procesos: {e}")
            return []
    else:
        # Fallback para Linux/macOS
        try:
            result = run_command(['ps', 'aux'], timeout=10)
            if result and result.returncode == 0:
                return result.stdout.lower().split('\n')
            return []
        except Exception as e:
            logger.error(f"Error obteniendo lista de procesos: {e}")
            return []


def is_process_running(process_name: str) -> bool:
    """Verifica si un proceso especifico esta en ejecucion."""
    processes = get_running_processes()
    return any(process_name.lower() in proc for proc in processes)


def kill_process(process_name: str, force: bool = True) -> bool:
    """
    Termina un proceso por nombre.
    Soporta Windows (taskkill) y Linux/macOS (pkill).
    """
    if is_windows():
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
    else:
        # Fallback para Linux/macOS
        try:
            args = ['pkill']
            if force:
                args.append('-9')
            args.append(process_name)
            result = run_command(args, timeout=10)
            if result and result.returncode == 0:
                logger.info(f"Proceso terminado: {process_name}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error terminando proceso {process_name}: {e}")
            return False


def kill_processes(
    process_names: List[str], force: bool = True
) -> Dict[str, bool]:
    """Termina multiples procesos y devuelve el resultado de cada uno."""
    return {process: kill_process(process, force) for process in process_names}


def ping_host(
    host: str, count: int = 1, timeout_ms: int = 1000
) -> Optional[Dict]:
    """
    Realiza un ping a un host y devuelve los resultados.
    Soporta Windows y Linux/macOS.
    """
    import re

    if is_windows():
        args = ['ping', '-n', str(count), '-w', str(timeout_ms), host]
    else:
        args = ['ping', '-c', str(count), '-W',
                str(max(1, timeout_ms // 1000)), host]

    try:
        result = run_command(args, timeout=timeout_ms // 1000 + 5)
        if result is None:
            return None

        output = result.stdout
        success = result.returncode == 0

        latency = 0
        if success:
            # Windows (espanol e ingles): tiempo=Xms / time=Xms / time<Xms
            match = re.search(
                r'(?:tiempo|time)[=<](\d+)\s*ms', output, re.IGNORECASE
            )
            if not match:
                # Linux: time=X.X ms
                match = re.search(
                    r'time[=<](\d+\.?\d*)\s*ms', output, re.IGNORECASE
                )
            if match:
                latency = int(float(match.group(1)))

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
    """Obtiene informacion basica del sistema operativo."""
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
