# -*- coding: utf-8 -*-
import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class DiagnosticService:
    def __init__(self, config):
        self.config = config
        self.paths = config.system_paths
        self.diagnostic_config = config.diagnostic_config
        self.error_patterns = config.error_patterns

    def get_gtav_path(self) -> Dict[str, Any]:
        from src.utils.system_utils import is_windows
        found_paths = []
        if is_windows():
            found_paths.extend(self._detect_gtav_from_registry())
        common_paths = [
            r"C:\Program Files\Rockstar Games\Grand Theft Auto V",
            r"C:\Program Files (x86)\Steam\steamapps\common\Grand Theft Auto V",
            r"D:\Games\Grand Theft Auto V",
            r"D:\SteamLibrary\steamapps\common\Grand Theft Auto V",
            r"E:\Games\Grand Theft Auto V"
        ]
        for path in common_paths:
            if os.path.exists(os.path.join(path, 'GTA5.exe')):
                if not any(p['path'] == path for p in found_paths):
                    found_paths.append({'path': path, 'platform': 'Manual'})
        result = {
            'Path': found_paths[0]['path'] if found_paths else None,
            'AllPaths': found_paths,
            'Status': 'Encontrado' if found_paths else 'No encontrado'
        }
        if found_paths:
            result['Platform'] = found_paths[0]['platform']
        return result

    def get_fivem_status(self) -> dict:
        """Detecta si FiveM está instalado comprobando sus rutas conocidas."""
        fivem_app = self.paths.fivem_paths.get('FiveMApp', '')
        fivem_exe_candidates = [
            os.path.join(os.path.expandvars('%LOCALAPPDATA%'), 'FiveM', 'FiveM.exe'),
            os.path.join(os.path.expandvars('%LOCALAPPDATA%'), 'FiveM', 'FiveM.app', 'FiveM.exe'),
        ]
        found = os.path.isdir(fivem_app) or any(os.path.exists(p) for p in fivem_exe_candidates)
        return {
            'Found': found,
            'Path': fivem_app if found else None,
            'Status': 'Instalado' if found else 'No encontrado',
        }

    def _detect_gtav_from_registry(self) -> List[Dict[str, str]]:
        found = []
        try:
            import winreg
            for key_path, platform in [
                (r"SOFTWARE\WOW6432Node\Rockstar Games\Grand Theft Auto V", 'Rockstar'),
            ]:
                try:
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
                    path, _ = winreg.QueryValueEx(key, "InstallFolder")
                    winreg.CloseKey(key)
                    if path and os.path.exists(os.path.join(path, 'GTA5.exe')):
                        found.append({'path': path, 'platform': platform})
                except (FileNotFoundError, OSError):
                    pass
        except ImportError:
            pass
        return found

    def verify_gtav_integrity(self, gta_path=None) -> Dict[str, Any]:
        if not gta_path:
            gta_info = self.get_gtav_path()
            gta_path = gta_info.get('Path')
        if not gta_path:
            return {'status': 'error', 'error': 'GTA V no encontrado', 'files_checked': 0, 'files_ok': 0, 'files_missing': []}
        required_files = ['GTA5.exe', 'GTAVLauncher.exe', 'bink2w64.dll', 'PlayGTAV.exe']
        files_ok = 0
        files_missing = []
        for filename in required_files:
            if os.path.exists(os.path.join(gta_path, filename)):
                files_ok += 1
            else:
                files_missing.append(filename)
        return {'status': 'ok' if not files_missing else 'incomplete', 'path': gta_path, 'files_checked': len(required_files), 'files_ok': files_ok, 'files_missing': files_missing}

    def detect_gta_mods(self, gta_path=None) -> Dict[str, Any]:
        if not gta_path:
            gta_info = self.get_gtav_path()
            gta_path = gta_info.get('Path')
        if not gta_path:
            return {'ModsFound': [], 'Count': 0, 'Error': 'GTA V no encontrado'}
        found_mods = [i for i in self.diagnostic_config.mod_indicators if os.path.exists(os.path.join(gta_path, i))]
        return {'ModsFound': found_mods, 'Count': len(found_mods), 'Path': gta_path}

    def analyze_fivem_errors(self) -> Dict[str, Any]:
        logs_path = self.paths.fivem_paths.get('Logs', '')
        errors = []
        if not os.path.exists(logs_path):
            return {'ErrorCount': 0, 'Errors': [], 'Recommendations': [], 'LogsPath': logs_path, 'Status': 'No se encontró carpeta de logs'}
        try:
            log_files = sorted(
                [f for f in os.listdir(logs_path) if f.endswith('.log')],
                key=lambda x: os.path.getmtime(os.path.join(logs_path, x)), reverse=True
            )[:5]
            patterns = self.error_patterns.patterns
            for log_file in log_files:
                log_path = os.path.join(logs_path, log_file)
                try:
                    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    for pattern, info in patterns.items():
                        if pattern.lower() in content.lower():
                            errors.append({'Error': pattern, 'Severity': info['severity'], 'Description': info['description'], 'Solution': info['solution'], 'File': log_file})
                except (IOError, OSError) as e:
                    logger.warning(f"Error reading log {log_file}: {e}")
        except (IOError, OSError) as e:
            logger.error(f"Error accessing logs: {e}")
            return {'ErrorCount': 0, 'Errors': [], 'Recommendations': [], 'Error': str(e)}
        recommendations = list(set(e['Solution'] for e in errors))
        return {'ErrorCount': len(errors), 'Errors': errors, 'Recommendations': recommendations, 'LogsPath': logs_path, 'LogsAnalyzed': len(log_files)}

    def analyze_crash_dumps(self) -> Dict[str, Any]:
        crashes_path = os.path.join(self.paths.fivem_paths.get('FiveMApp', ''), 'crashes')
        dumps = []
        if not os.path.exists(crashes_path):
            return {'dumps_found': [], 'analysis': [], 'recommendations': [], 'path': crashes_path}
        try:
            for filename in os.listdir(crashes_path):
                if filename.endswith(('.dmp', '.log')):
                    filepath = os.path.join(crashes_path, filename)
                    try:
                        stat = os.stat(filepath)
                        dumps.append({'file': filename, 'date': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M'), 'size': round(stat.st_size / 1024, 1)})
                    except OSError:
                        pass
        except OSError as e:
            logger.error(f"Error accessing crash dumps: {e}")
        dumps.sort(key=lambda x: x['date'], reverse=True)
        analysis = [{'file': d['file'], 'date': d['date'], 'possible_causes': ['Crash de GPU', 'Falta de memoria', 'Conflicto de software']} for d in dumps[:5]]
        recommendations = ['Actualiza los drivers de tu GPU', 'Aumenta la memoria virtual del sistema', 'Cierra programas en segundo plano'] if dumps else []
        return {'dumps_found': dumps, 'analysis': analysis, 'recommendations': recommendations, 'path': crashes_path}

    def detect_conflicting_software(self) -> Dict[str, Any]:
        from src.utils.system_utils import get_running_processes
        conflicting = self.diagnostic_config.conflicting_software
        processes_lower = '\n'.join(get_running_processes()).lower()
        found = [s['name'] for s in conflicting if s['process'].lower() in processes_lower]
        return {'ConflictsFound': found, 'Count': len(found), 'Recommendations': ['Cierra el software conflictivo antes de jugar'] if found else []}

    def detect_conflicting_overlays(self) -> Dict[str, Any]:
        from src.utils.system_utils import get_running_processes
        overlay_processes = self.diagnostic_config.overlay_processes
        processes_lower = '\n'.join(get_running_processes()).lower()
        found = [{'name': n, 'process': p, 'status': 'running'} for n, p in overlay_processes.items() if p.lower() in processes_lower]
        return {'overlays_found': found, 'count': len(found), 'recommendations': ['Desactiva los overlays antes de jugar'] if found else []}

    def check_system_requirements(self, hardware_info: Dict) -> Dict[str, Any]:
        from config import system_requirements
        checks = {}
        passed = True
        recommendations = []
        ram_gb = hardware_info.get('ram', {}).get('TotalGB', 0)
        checks['RAM'] = {'current': f'{ram_gb} GB', 'required': f'{system_requirements.recommended_ram_gb} GB', 'passed': ram_gb >= system_requirements.recommended_ram_gb}
        if not checks['RAM']['passed']:
            passed = False
            recommendations.append(f'Se recomienda {system_requirements.recommended_ram_gb}GB de RAM')
        gpu_list = hardware_info.get('gpu', [{}])
        vram_gb = gpu_list[0].get('VRAM_GB', 0) if gpu_list else 0
        checks['VRAM'] = {'current': f'{vram_gb} GB', 'required': f'{system_requirements.recommended_vram_gb} GB', 'passed': vram_gb >= system_requirements.recommended_vram_gb}
        if not checks['VRAM']['passed']:
            passed = False
            recommendations.append(f'Se recomienda GPU con {system_requirements.recommended_vram_gb}GB VRAM')
        return {'status': 'ok' if passed else 'warning', 'checks': checks, 'recommendations': recommendations}

    def check_directx(self) -> Dict[str, Any]:
        return {'status': 'good', 'feature_level': 'DirectX 11+', 'recommendations': []}

    def check_vcredist(self) -> Dict[str, Any]:
        from src.utils.system_utils import is_windows
        installed, missing = [], []
        if is_windows():
            try:
                import winreg
                for key_path, label in [
                    (r"SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64", '2015-2022 x64'),
                    (r"SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x86", '2015-2022 x86'),
                ]:
                    try:
                        winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
                        installed.append(label)
                    except FileNotFoundError:
                        missing.append(label)
            except ImportError:
                pass
        return {'status': 'complete' if not missing else 'incomplete', 'installed': installed, 'missing': missing, 'recommendations': ['Instala Visual C++ 2015-2022 Redistributable'] if missing else []}

    def get_citizenfx_config(self) -> Dict[str, str]:
        config = {'UpdateChannel': 'production', 'GameBuild': '', 'DisableNVSP': '0'}
        ini_path = self.paths.fivem_paths.get('CitizenFXIni', '')
        if os.path.exists(ini_path):
            try:
                with open(ini_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if '=' in line:
                            key, value = line.split('=', 1)
                            if key.strip() in config:
                                config[key.strip()] = value.strip()
            except (IOError, OSError) as e:
                logger.warning(f"Error reading CitizenFX.ini: {e}")
        return config
