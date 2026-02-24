# -*- coding: utf-8 -*-
"""
Servicio de hardware para FiveM Diagnostic Tool.

Contiene la lógica para obtener información del hardware del sistema.
"""

import json
import logging
from typing import Dict, List, Any, Optional

from src.utils.system_utils import is_windows, run_powershell, run_command

logger = logging.getLogger(__name__)


class HardwareService:
    """
    Servicio para obtener información del hardware.
    
    Proporciona métodos para detectar GPU, RAM, CPU y temperaturas.
    """
    
    def __init__(self, config):
        """
        Inicializa el servicio de hardware.
        
        Args:
            config: Objeto de configuración del sistema
        """
        self.config = config
        self.timeout_config = config.timeout_config
    
    def get_gpu_info(self) -> List[Dict[str, Any]]:
        """
        Obtiene información de las tarjetas gráficas.
        
        Returns:
            Lista de diccionarios con información de cada GPU
        """
        gpus = []
        
        if is_windows():
            try:
                result = run_powershell(
                    'Get-WmiObject Win32_VideoController | '
                    'Select-Object Name, AdapterRAM, DriverVersion | '
                    'ConvertTo-Json',
                    timeout=self.timeout_config.powershell_timeout
                )
                
                if result:
                    data = json.loads(result)
                    if not isinstance(data, list):
                        data = [data]
                    
                    for gpu in data:
                        adapter_ram = gpu.get('AdapterRAM', 0)
                        # Manejar valores nulos o negativos
                        if adapter_ram and adapter_ram > 0:
                            vram_gb = round(int(adapter_ram) / (1024**3), 1)
                        else:
                            vram_gb = 0
                        
                        gpus.append({
                            'Name': gpu.get('Name', 'Desconocido'),
                            'VRAM_GB': vram_gb,
                            'DriverVersion': gpu.get('DriverVersion', 'N/A')
                        })
                        
            except json.JSONDecodeError as e:
                logger.warning(f"Error parseando información de GPU: {e}")
            except Exception as e:
                logger.error(f"Error obteniendo información de GPU: {e}")
        
        if not gpus:
            gpus = [{
                'Name': 'No detectada',
                'VRAM_GB': 0,
                'DriverVersion': 'N/A'
            }]
        
        return gpus
    
    def get_ram_info(self) -> Dict[str, Any]:
        """
        Obtiene información de la memoria RAM.
        
        Returns:
            Diccionario con información de RAM
        """
        ram_info = {
            'TotalGB': 0,
            'AvailableGB': 0,
            'UsedPercent': 0
        }
        
        if is_windows():
            try:
                result = run_powershell(
                    'Get-WmiObject Win32_OperatingSystem | '
                    'Select-Object TotalVisibleMemorySize, FreePhysicalMemory | '
                    'ConvertTo-Json',
                    timeout=self.timeout_config.powershell_timeout
                )
                
                if result:
                    data = json.loads(result)
                    total_kb = int(data.get('TotalVisibleMemorySize', 0))
                    free_kb = int(data.get('FreePhysicalMemory', 0))
                    
                    if total_kb > 0:
                        ram_info = {
                            'TotalGB': round(total_kb / (1024**2), 1),
                            'AvailableGB': round(free_kb / (1024**2), 1),
                            'UsedPercent': round((1 - free_kb/total_kb) * 100, 1)
                        }
                        
            except json.JSONDecodeError as e:
                logger.warning(f"Error parseando información de RAM: {e}")
            except ZeroDivisionError:
                logger.warning("División por cero al calcular uso de RAM")
            except Exception as e:
                logger.error(f"Error obteniendo información de RAM: {e}")
        
        return ram_info
    
    def get_cpu_info(self) -> Dict[str, Any]:
        """
        Obtiene información del procesador.
        
        Returns:
            Diccionario con información del CPU
        """
        cpu_info = {
            'Name': 'Desconocido',
            'Cores': 0,
            'Threads': 0,
            'MaxSpeed': 0
        }
        
        if is_windows():
            try:
                result = run_powershell(
                    'Get-WmiObject Win32_Processor | '
                    'Select-Object Name, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed | '
                    'ConvertTo-Json',
                    timeout=self.timeout_config.powershell_timeout
                )
                
                if result:
                    data = json.loads(result)
                    if isinstance(data, list):
                        data = data[0]
                    
                    cpu_info = {
                        'Name': data.get('Name', 'Desconocido'),
                        'Cores': data.get('NumberOfCores', 0),
                        'Threads': data.get('NumberOfLogicalProcessors', 0),
                        'MaxSpeed': data.get('MaxClockSpeed', 0)
                    }
                    
            except json.JSONDecodeError as e:
                logger.warning(f"Error parseando información de CPU: {e}")
            except Exception as e:
                logger.error(f"Error obteniendo información de CPU: {e}")
        
        return cpu_info
    
    def get_system_temperatures(self) -> Dict[str, Any]:
        """
        Obtiene las temperaturas del sistema.
        
        Returns:
            Diccionario con temperaturas de CPU y GPU
        """
        temps = {
            'cpu': {'current': None, 'status': 'unknown'},
            'gpu': {'current': None, 'status': 'unknown'},
            'warnings': []
        }
        
        if is_windows():
            # Intentar obtener temperatura de GPU NVIDIA
            try:
                result = run_command(
                    ['nvidia-smi', '--query-gpu=temperature.gpu', '--format=csv,noheader'],
                    timeout=self.timeout_config.nvidia_smi_timeout
                )
                
                if result and result.returncode == 0:
                    gpu_temp = int(result.stdout.strip())
                    status = 'normal' if gpu_temp < 80 else 'high'
                    temps['gpu'] = {
                        'current': gpu_temp,
                        'status': status
                    }
                    
                    if gpu_temp >= 80:
                        temps['warnings'].append(f'Temperatura GPU alta: {gpu_temp}°C')
                        
            except (ValueError, FileNotFoundError):
                pass
            except Exception as e:
                logger.debug(f"No se pudo obtener temperatura de GPU: {e}")
        
        return temps
    
    def get_antivirus_info(self) -> Dict[str, Any]:
        """
        Detecta antivirus instalados en el sistema.
        
        Returns:
            Diccionario con información de antivirus
        """
        antivirus = []
        
        if is_windows():
            try:
                result = run_powershell(
                    'Get-WmiObject -Namespace "root\\SecurityCenter2" '
                    '-Class AntiVirusProduct | '
                    'Select-Object displayName | '
                    'ConvertTo-Json',
                    timeout=self.timeout_config.powershell_timeout
                )
                
                if result:
                    data = json.loads(result)
                    if not isinstance(data, list):
                        data = [data]
                    
                    for av in data:
                        name = av.get('displayName', '')
                        if name:
                            antivirus.append(name)
                            
            except json.JSONDecodeError:
                pass
            except Exception as e:
                logger.debug(f"Error detectando antivirus: {e}")
        
        if not antivirus:
            antivirus = ['Windows Defender']
        
        # Generar recomendaciones según el antivirus
        recommendations = []
        problematic_av = ['Avast', 'AVG', 'Norton', 'McAfee']
        
        for av in antivirus:
            if any(prob in av for prob in problematic_av):
                recommendations.append(f'Agrega exclusiones para FiveM en {av}')
        
        return {
            'Installed': antivirus,
            'Recommendations': recommendations
        }
    
    def run_benchmark(self) -> Dict[str, Any]:
        """
        Ejecuta un benchmark básico del sistema.
        
        Returns:
            Diccionario con resultados del benchmark
        """
        import os
        import time
        
        results = {
            'cpu_score': 0,
            'memory_score': 0,
            'disk_score': 0,
            'overall_score': 0,
            'rating': 'Desconocido',
            'fivem_ready': False,
            'details': {}
        }
        
        # Puntuación de CPU basada en núcleos e hilos
        cpu_info = self.get_cpu_info()
        cores = cpu_info.get('Cores', 2)
        threads = cpu_info.get('Threads', 4)
        results['cpu_score'] = min(100, (cores * 10) + (threads * 5))
        
        # Puntuación de memoria
        ram_info = self.get_ram_info()
        ram_gb = ram_info.get('TotalGB', 8)
        results['memory_score'] = min(100, int(ram_gb * 6))
        
        # Puntuación de disco (test de escritura/lectura)
        try:
            from config import system_paths
            work_folder = system_paths.work_folder
            os.makedirs(work_folder, exist_ok=True)
            
            test_file = os.path.join(work_folder, 'benchmark_test.tmp')
            test_size_mb = 50
            test_data = os.urandom(test_size_mb * 1024 * 1024)
            
            # Test de escritura
            start = time.time()
            with open(test_file, 'wb') as f:
                f.write(test_data)
            write_time = time.time() - start
            write_speed = round(test_size_mb / write_time, 1)
            
            # Test de lectura
            start = time.time()
            with open(test_file, 'rb') as f:
                _ = f.read()
            read_time = time.time() - start
            read_speed = round(test_size_mb / read_time, 1)
            
            # Limpiar archivo de prueba
            os.remove(test_file)
            
            results['disk_score'] = min(100, int((write_speed + read_speed) / 10))
            results['details']['disk_write_speed'] = write_speed
            results['details']['disk_read_speed'] = read_speed
            
        except Exception as e:
            logger.warning(f"Error en benchmark de disco: {e}")
            results['disk_score'] = 50
        
        # Calcular puntuación general
        results['overall_score'] = round(
            (results['cpu_score'] * 0.3) +
            (results['memory_score'] * 0.4) +
            (results['disk_score'] * 0.3)
        )
        
        # Determinar rating
        score = results['overall_score']
        if score >= 80:
            results['rating'] = 'Excelente'
        elif score >= 60:
            results['rating'] = 'Bueno'
        elif score >= 40:
            results['rating'] = 'Regular'
        else:
            results['rating'] = 'Bajo'
        
        # Verificar si está listo para FiveM
        from config import system_requirements
        results['fivem_ready'] = score >= system_requirements.min_benchmark_score
        
        return results
    
    def get_all_hardware_info(self) -> Dict[str, Any]:
        """
        Obtiene toda la información del hardware.
        
        Returns:
            Diccionario con toda la información del hardware
        """
        return {
            'gpu': self.get_gpu_info(),
            'ram': self.get_ram_info(),
            'cpu': self.get_cpu_info(),
            'temperatures': self.get_system_temperatures(),
            'antivirus': self.get_antivirus_info()
        }
