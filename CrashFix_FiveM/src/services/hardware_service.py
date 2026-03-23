# -*- coding: utf-8 -*-
import json
import logging
from typing import Dict, List, Any, Optional
from src.utils.system_utils import is_windows, run_powershell, run_command

logger = logging.getLogger(__name__)

class HardwareService:
    def __init__(self, config):
        self.config = config
        self.timeout_config = config.timeout_config

    def get_gpu_info(self) -> List[Dict[str, Any]]:
        """Detecta informacion de GPU con VRAM precisa.

        Win32_VideoController.AdapterRAM es uint32 y trunca a 4 GB para GPUs
        con mas de 4 GB de VRAM. Para obtener el valor real se usan fuentes
        alternativas en este orden:
        1. nvidia-smi (NVIDIA GPUs - valor exacto)
        2. Registro de Windows (qwMemorySize - valor de 64 bits)
        3. Win32_VideoController como fallback
        """
        gpus = []
        if is_windows():
            # Fuente 1: nvidia-smi (mas precisa para NVIDIA)
            nvidia_vram = self._get_nvidia_vram()

            # Fuente 2: WMI para nombres y drivers + correccion de VRAM
            try:
                result = run_powershell(
                    'Get-WmiObject Win32_VideoController | Select-Object Name, AdapterRAM, DriverVersion, PNPDeviceID | ConvertTo-Json',
                    timeout=self.timeout_config.powershell_timeout
                )
                if result:
                    data = json.loads(result)
                    if not isinstance(data, list): data = [data]
                    for gpu in data:
                        name = gpu.get('Name', 'Desconocido')
                        driver = gpu.get('DriverVersion', 'N/A')
                        pnp_id = gpu.get('PNPDeviceID', '')

                        # Determinar VRAM con la mejor fuente disponible
                        vram_gb = 0

                        # Intentar nvidia-smi primero (si es NVIDIA)
                        if nvidia_vram and 'nvidia' in name.lower():
                            vram_gb = nvidia_vram
                        else:
                            # Intentar leer del registro (soporta >4 GB)
                            reg_vram = self._get_vram_from_registry(pnp_id)
                            if reg_vram > 0:
                                vram_gb = reg_vram

                        # Fallback: WMI AdapterRAM (trunca a 4 GB)
                        if vram_gb == 0:
                            adapter_ram = gpu.get('AdapterRAM', 0)
                            if adapter_ram and int(adapter_ram) > 0:
                                vram_gb = round(int(adapter_ram) / (1024**3), 1)

                        gpus.append({
                            'Name': name,
                            'VRAM_GB': vram_gb,
                            'DriverVersion': driver
                        })
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"GPU info error: {e}")

        if not gpus:
            gpus = [{'Name': 'No detectada', 'VRAM_GB': 0, 'DriverVersion': 'N/A'}]
        return gpus

    def _get_nvidia_vram(self) -> float:
        """Obtiene VRAM total via nvidia-smi (preciso, sin limite de 4 GB)."""
        try:
            result = run_command(
                ['nvidia-smi', '--query-gpu=memory.total', '--format=csv,noheader,nounits'],
                timeout=self.timeout_config.nvidia_smi_timeout
            )
            if result and result.returncode == 0:
                vram_mb = int(result.stdout.strip().split('\n')[0])
                return round(vram_mb / 1024, 1)
        except Exception as e:
            logger.debug(f"nvidia-smi VRAM query failed: {e}")
        return 0

    def _get_vram_from_registry(self, pnp_device_id: str) -> float:
        """Lee VRAM desde el registro de Windows (qwMemorySize, 64 bits).

        El registro almacena el valor real sin truncar a 4 GB.
        """
        if not pnp_device_id:
            return 0
        try:
            # Buscar en las subclaves de video del registro
            result = run_powershell(
                'Get-ItemProperty -Path "HKLM:\\SYSTEM\\ControlSet001\\Control\\Class\\{4d36e968-e325-11ce-bfc1-08002be10318}\\0*" '
                '-Name HardwareInformation.qwMemorySize -ErrorAction SilentlyContinue | '
                'Select-Object -ExpandProperty "HardwareInformation.qwMemorySize" | '
                'Select-Object -First 1',
                timeout=self.timeout_config.powershell_timeout
            )
            if result:
                vram_bytes = int(result.strip())
                if vram_bytes > 0:
                    return round(vram_bytes / (1024**3), 1)
        except Exception as e:
            logger.debug(f"Registry VRAM query failed: {e}")
        return 0

    def get_ram_info(self) -> Dict[str, Any]:
        ram_info = {'TotalGB': 0, 'AvailableGB': 0, 'UsedPercent': 0}
        if is_windows():
            try:
                result = run_powershell('Get-WmiObject Win32_OperatingSystem | Select-Object TotalVisibleMemorySize, FreePhysicalMemory | ConvertTo-Json', timeout=self.timeout_config.powershell_timeout)
                if result:
                    data = json.loads(result)
                    total_kb = int(data.get('TotalVisibleMemorySize', 0))
                    free_kb = int(data.get('FreePhysicalMemory', 0))
                    if total_kb > 0:
                        ram_info = {'TotalGB': round(total_kb / (1024**2), 1), 'AvailableGB': round(free_kb / (1024**2), 1), 'UsedPercent': round((1 - free_kb/total_kb) * 100, 1)}
            except Exception as e:
                logger.warning(f"RAM info error: {e}")
        return ram_info

    def get_cpu_info(self) -> Dict[str, Any]:
        cpu_info = {'Name': 'Desconocido', 'Cores': 0, 'Threads': 0, 'MaxSpeed': 0}
        if is_windows():
            try:
                result = run_powershell('Get-WmiObject Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed | ConvertTo-Json', timeout=self.timeout_config.powershell_timeout)
                if result:
                    data = json.loads(result)
                    if isinstance(data, list): data = data[0]
                    cpu_info = {'Name': data.get('Name', 'Desconocido'), 'Cores': data.get('NumberOfCores', 0), 'Threads': data.get('NumberOfLogicalProcessors', 0), 'MaxSpeed': data.get('MaxClockSpeed', 0)}
            except Exception as e:
                logger.warning(f"CPU info error: {e}")
        return cpu_info

    def get_system_temperatures(self) -> Dict[str, Any]:
        temps = {'cpu': {'current': None, 'status': 'unknown'}, 'gpu': {'current': None, 'status': 'unknown'}, 'warnings': []}
        if is_windows():
            try:
                result = run_command(['nvidia-smi', '--query-gpu=temperature.gpu', '--format=csv,noheader'], timeout=self.timeout_config.nvidia_smi_timeout)
                if result and result.returncode == 0:
                    gpu_temp = int(result.stdout.strip())
                    status = 'normal' if gpu_temp < 80 else 'high'
                    temps['gpu'] = {'current': gpu_temp, 'status': status}
                    if gpu_temp >= 80:
                        temps['warnings'].append(f'Temperatura GPU alta: {gpu_temp}°C')
            except Exception:
                pass
        return temps

    def get_antivirus_info(self) -> Dict[str, Any]:
        antivirus = []
        if is_windows():
            try:
                result = run_powershell('Get-WmiObject -Namespace "root\\SecurityCenter2" -Class AntiVirusProduct | Select-Object displayName | ConvertTo-Json', timeout=self.timeout_config.powershell_timeout)
                if result:
                    data = json.loads(result)
                    if not isinstance(data, list): data = [data]
                    antivirus = [av.get('displayName', '') for av in data if av.get('displayName')]
            except Exception:
                pass
        if not antivirus:
            antivirus = ['Windows Defender']
        recommendations = []
        for av in antivirus:
            if any(p in av for p in ['Avast', 'AVG', 'Norton', 'McAfee']):
                recommendations.append(f'Agrega exclusiones para FiveM en {av}')
        return {'Installed': antivirus, 'Recommendations': recommendations}

    def run_benchmark(self) -> Dict[str, Any]:
        import os, time
        results = {'cpu_score': 0, 'memory_score': 0, 'disk_score': 0, 'overall_score': 0, 'rating': 'Desconocido', 'fivem_ready': False, 'details': {}}
        cpu_info = self.get_cpu_info()
        cores = cpu_info.get('Cores', 2)
        threads = cpu_info.get('Threads', 4)
        results['cpu_score'] = min(100, (cores * 10) + (threads * 5))
        ram_info = self.get_ram_info()
        ram_gb = ram_info.get('TotalGB', 8)
        results['memory_score'] = min(100, int(ram_gb * 6))
        try:
            from config import system_paths
            work_folder = system_paths.work_folder
            os.makedirs(work_folder, exist_ok=True)
            test_file = os.path.join(work_folder, 'benchmark_test.tmp')
            test_size_mb = 50
            test_data = os.urandom(test_size_mb * 1024 * 1024)
            start = time.time()
            with open(test_file, 'wb') as f: f.write(test_data)
            write_speed = round(test_size_mb / (time.time() - start), 1)
            start = time.time()
            with open(test_file, 'rb') as f: _ = f.read()
            read_speed = round(test_size_mb / (time.time() - start), 1)
            os.remove(test_file)
            results['disk_score'] = min(100, int((write_speed + read_speed) / 10))
            results['details']['disk_write_speed'] = write_speed
            results['details']['disk_read_speed'] = read_speed
        except Exception as e:
            logger.warning(f"Disk benchmark error: {e}")
            results['disk_score'] = 50
        results['overall_score'] = round((results['cpu_score'] * 0.3) + (results['memory_score'] * 0.4) + (results['disk_score'] * 0.3))
        score = results['overall_score']
        results['rating'] = 'Excelente' if score >= 80 else 'Bueno' if score >= 60 else 'Regular' if score >= 40 else 'Bajo'
        from config import system_requirements
        results['fivem_ready'] = score >= system_requirements.min_benchmark_score
        return results

    def get_os_info(self) -> Dict[str, Any]:
        """Obtiene informacion del sistema operativo."""
        from src.utils.system_utils import get_system_info
        sys_info = get_system_info()
        os_name = f"{sys_info.get('system', 'Desconocido')} {sys_info.get('release', '')}".strip()
        os_version = sys_info.get('version', 'N/A')
        os_arch = sys_info.get('machine', 'N/A')
        return {
            'Name': os_name,
            'Version': os_version,
            'Architecture': os_arch,
            'Processor': sys_info.get('processor', 'N/A')
        }

    def get_all_hardware_info(self) -> Dict[str, Any]:
        """Obtiene toda la informacion de hardware y sistema operativo."""
        return {
            'gpu': self.get_gpu_info(),
            'ram': self.get_ram_info(),
            'cpu': self.get_cpu_info(),
            'os': self.get_os_info(),
            'temperatures': self.get_system_temperatures(),
            'antivirus': self.get_antivirus_info()
        }
