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
        """Deteccion mejorada de GTA V: registros multiples, Steam, Epic, escaneo inteligente.

        Orden de busqueda (de mas rapido a mas lento):
        1. Claves de registro (Rockstar, Steam, Epic)
        2. Steam libraryfolders.vdf
        3. Epic Games manifests
        4. Rutas comunes hardcodeadas (fallback original)
        5. Escaneo inteligente de unidades disponibles
        """
        from src.utils.system_utils import is_windows
        found_paths = []
        seen_paths = set()

        def _add_path(path, platform):
            """Agrega una ruta si es valida y no duplicada."""
            if not path:
                return
            path = os.path.normpath(path)
            path_lower = path.lower()
            if path_lower in seen_paths:
                return
            if os.path.exists(os.path.join(path, 'GTA5.exe')):
                seen_paths.add(path_lower)
                found_paths.append({'path': path, 'platform': platform})

        # --- 1. Registros de Windows (multiples plataformas) ---
        if is_windows():
            found_paths.extend(self._detect_gtav_from_registry())
            for p in found_paths:
                seen_paths.add(os.path.normpath(p['path']).lower())

        # --- 2. Steam libraryfolders.vdf ---
        if is_windows():
            for steam_path in self._detect_gtav_from_steam():
                _add_path(steam_path, 'Steam')

        # --- 3. Epic Games manifests ---
        if is_windows():
            for epic_path in self._detect_gtav_from_epic():
                _add_path(epic_path, 'Epic Games')

        # --- 4. Rutas comunes (fallback original) ---
        common_paths = [
            r"C:\Program Files\Rockstar Games\Grand Theft Auto V",
            r"C:\Program Files (x86)\Steam\steamapps\common\Grand Theft Auto V",
            r"D:\Games\Grand Theft Auto V",
            r"D:\SteamLibrary\steamapps\common\Grand Theft Auto V",
            r"E:\Games\Grand Theft Auto V"
        ]
        for path in common_paths:
            _add_path(path, 'Manual')

        # --- 5. Escaneo inteligente de unidades (solo si no se encontro) ---
        if not found_paths and is_windows():
            for scan_path in self._smart_scan_drives():
                _add_path(scan_path, 'Escaneo')
                if found_paths:
                    break  # Encontrado, no seguir escaneando

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
        """Busca GTA V en multiples claves de registro (Rockstar, Steam, Epic)."""
        found = []
        try:
            import winreg
            registry_entries = [
                # Rockstar Games Launcher
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Rockstar Games\Grand Theft Auto V", "InstallFolder", 'Rockstar'),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Rockstar Games\Grand Theft Auto V", "InstallFolder", 'Rockstar'),
                # Steam
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App 271590", "InstallLocation", 'Steam'),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Steam App 271590", "InstallLocation", 'Steam'),
                # Epic Games
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Epic Games\EpicGamesLauncher", "AppDataPath", 'Epic Games'),
                # Rockstar Social Club (legacy)
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Rockstar Games\GTAV", "InstallFolderEpic", 'Epic Games'),
            ]
            seen = set()
            for hive, key_path, value_name, platform in registry_entries:
                try:
                    key = winreg.OpenKey(hive, key_path)
                    path, _ = winreg.QueryValueEx(key, value_name)
                    winreg.CloseKey(key)
                    if path:
                        path = os.path.normpath(path)
                        if path.lower() not in seen and os.path.exists(os.path.join(path, 'GTA5.exe')):
                            seen.add(path.lower())
                            found.append({'path': path, 'platform': platform})
                except (FileNotFoundError, OSError, PermissionError):
                    pass
        except ImportError:
            pass
        return found

    def _detect_gtav_from_steam(self) -> List[str]:
        """Busca GTA V en las librerias de Steam leyendo libraryfolders.vdf."""
        paths = []
        try:
            import winreg
            # Obtener ruta de instalacion de Steam
            steam_path = None
            for key_path in [
                r"SOFTWARE\WOW6432Node\Valve\Steam",
                r"SOFTWARE\Valve\Steam"
            ]:
                try:
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
                    steam_path, _ = winreg.QueryValueEx(key, "InstallPath")
                    winreg.CloseKey(key)
                    if steam_path:
                        break
                except (FileNotFoundError, OSError):
                    pass

            if not steam_path:
                return paths

            # Leer libraryfolders.vdf
            vdf_path = os.path.join(steam_path, 'steamapps', 'libraryfolders.vdf')
            if not os.path.exists(vdf_path):
                return paths

            library_dirs = [os.path.join(steam_path, 'steamapps')]
            try:
                with open(vdf_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                # Parsear rutas de librerias (formato VDF simple)
                import re
                # Buscar "path" "valor" en el VDF
                for match in re.finditer(r'"path"\s*"([^"]+)"', content):
                    lib_path = match.group(1).replace('\\\\', '\\').replace('\\\\', '\\')
                    steamapps = os.path.join(lib_path, 'steamapps')
                    if os.path.isdir(steamapps) and steamapps not in library_dirs:
                        library_dirs.append(steamapps)
            except (IOError, OSError) as e:
                logger.warning(f"Error reading libraryfolders.vdf: {e}")

            # Buscar GTA V en cada libreria de Steam
            for lib_dir in library_dirs:
                gta_path = os.path.join(lib_dir, 'common', 'Grand Theft Auto V')
                if os.path.exists(os.path.join(gta_path, 'GTA5.exe')):
                    paths.append(gta_path)

        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"Error detecting GTA V from Steam: {e}")
        return paths

    def _detect_gtav_from_epic(self) -> List[str]:
        """Busca GTA V en los manifests de Epic Games Launcher."""
        paths = []
        try:
            # Epic Games guarda manifests en ProgramData
            manifests_dir = os.path.join(
                os.environ.get('ProgramData', r'C:\ProgramData'),
                'Epic', 'EpicGamesLauncher', 'Data', 'Manifests'
            )
            if not os.path.isdir(manifests_dir):
                return paths

            import json
            for filename in os.listdir(manifests_dir):
                if not filename.endswith('.item'):
                    continue
                try:
                    filepath = os.path.join(manifests_dir, filename)
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        manifest = json.load(f)
                    # GTA V en Epic tiene AppName "9d2d0eb64d5c44529cece33fe2a46482"
                    # pero tambien podemos buscar por DisplayName
                    display_name = manifest.get('DisplayName', '').lower()
                    install_location = manifest.get('InstallLocation', '')
                    if ('grand theft auto' in display_name or 'gta' in display_name) and install_location:
                        if os.path.exists(os.path.join(install_location, 'GTA5.exe')):
                            paths.append(install_location)
                except (json.JSONDecodeError, IOError, OSError, KeyError):
                    pass
        except (OSError, PermissionError) as e:
            logger.warning(f"Error detecting GTA V from Epic: {e}")
        return paths

    def _smart_scan_drives(self) -> List[str]:
        """Escaneo inteligente: busca GTA5.exe en ubicaciones probables de todas las unidades.

        Solo escanea directorios de primer y segundo nivel para evitar lentitud.
        Busca en carpetas tipicas de juegos, no en todo el disco.
        """
        paths = []
        try:
            import string
            # Obtener unidades disponibles
            drives = []
            for letter in string.ascii_uppercase:
                drive = f"{letter}:\\"
                if os.path.isdir(drive):
                    drives.append(drive)

            # Carpetas tipicas donde se instalan juegos
            game_folders = [
                'Games', 'Juegos', 'Program Files', 'Program Files (x86)',
                'SteamLibrary', 'Steam', 'EpicGames', 'Epic Games',
                'Rockstar Games', 'GOG Games', 'Origin Games'
            ]

            # Subcarpetas tipicas dentro de las carpetas de juegos
            sub_patterns = [
                'Grand Theft Auto V',
                'GTAV',
                'GTA5',
                os.path.join('steamapps', 'common', 'Grand Theft Auto V'),
                os.path.join('Rockstar Games', 'Grand Theft Auto V'),
            ]

            for drive in drives:
                # Buscar directamente en la raiz
                for sub in sub_patterns:
                    candidate = os.path.join(drive, sub)
                    if os.path.exists(os.path.join(candidate, 'GTA5.exe')):
                        paths.append(candidate)
                        return paths  # Encontrado, retornar inmediatamente

                # Buscar en carpetas tipicas de juegos
                for folder in game_folders:
                    base = os.path.join(drive, folder)
                    if not os.path.isdir(base):
                        continue
                    for sub in sub_patterns:
                        candidate = os.path.join(base, sub)
                        if os.path.exists(os.path.join(candidate, 'GTA5.exe')):
                            paths.append(candidate)
                            return paths  # Encontrado, retornar inmediatamente

        except (OSError, PermissionError) as e:
            logger.warning(f"Error during smart drive scan: {e}")
        return paths

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
        """Verifica los requisitos del sistema para FiveM.

        Evalua RAM, VRAM, CPU y sistema operativo, devolviendo ademas
        los datos de hardware para que el frontend pueda renderizarlos
        directamente sin necesidad de llamadas adicionales.
        """
        from config import system_requirements
        checks = {}
        passed = True
        recommendations = []

        # --- RAM ---
        ram_gb = hardware_info.get('ram', {}).get('TotalGB', 0)
        checks['RAM'] = {
            'current': f'{ram_gb} GB',
            'required': f'{system_requirements.recommended_ram_gb} GB',
            'passed': ram_gb >= system_requirements.recommended_ram_gb
        }
        if not checks['RAM']['passed']:
            passed = False
            recommendations.append(f'Se recomienda {system_requirements.recommended_ram_gb}GB de RAM')

        # --- VRAM ---
        gpu_list = hardware_info.get('gpu', [{}])
        vram_gb = gpu_list[0].get('VRAM_GB', 0) if gpu_list else 0
        checks['VRAM'] = {
            'current': f'{vram_gb} GB',
            'required': f'{system_requirements.recommended_vram_gb} GB',
            'passed': vram_gb >= system_requirements.recommended_vram_gb
        }
        if not checks['VRAM']['passed']:
            passed = False
            recommendations.append(f'Se recomienda GPU con {system_requirements.recommended_vram_gb}GB VRAM')

        # --- CPU (informativo, no bloquea) ---
        cpu_data = hardware_info.get('cpu', {})
        cpu_cores = cpu_data.get('Cores', 0)
        checks['CPU'] = {
            'current': f"{cpu_data.get('Name', 'Desconocido')} ({cpu_cores} nucleos)",
            'required': '4 nucleos',
            'passed': cpu_cores >= 4 if cpu_cores > 0 else True
        }
        if cpu_cores > 0 and cpu_cores < 4:
            recommendations.append('Se recomienda un procesador con al menos 4 nucleos')

        # --- Sistema Operativo (informativo) ---
        os_data = hardware_info.get('os', {})
        os_name = os_data.get('Name', 'Desconocido')
        checks['OS'] = {
            'current': f"{os_name} ({os_data.get('Architecture', 'N/A')})",
            'required': 'Windows 10/11 64-bit',
            'passed': True
        }

        return {
            'status': 'ok' if passed else 'warning',
            'checks': checks,
            'recommendations': recommendations,
            'gpu': gpu_list,
            'ram': hardware_info.get('ram', {}),
            'cpu': cpu_data,
            'os': os_data
        }

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

    def get_citizenfx_config(self) -> Dict[str, Any]:
        """Lee la configuracion de CitizenFX.ini.

        Busca el archivo en la ruta oficial (%localappdata%/FiveM/FiveM.app/)
        y como fallback en la ruta legacy (%appdata%/CitizenFX/).

        Formato real del archivo (segun docs.fivem.net):
            [Game]
            IVPath=C:\\...
            SavedBuildNumber=1604
            UpdateChannel=production
            DisableNVSP=0
            EnableFullMemoryDump=0
        """
        config = {
            'IVPath': '',
            'SavedBuildNumber': '',
            'UpdateChannel': 'production',
            'DisableNVSP': '0',
            'EnableFullMemoryDump': '0',
            'DisableOSVersionCheck': '0',
            'DisableCrashUpload': '0'
        }

        # Buscar archivo en ruta principal y legacy
        ini_path = self.paths.fivem_paths.get('CitizenFXIni', '')
        ini_path_legacy = self.paths.fivem_paths.get('CitizenFXIniLegacy', '')

        actual_path = None
        if ini_path and os.path.exists(ini_path):
            actual_path = ini_path
        elif ini_path_legacy and os.path.exists(ini_path_legacy):
            actual_path = ini_path_legacy

        if actual_path:
            try:
                with open(actual_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        # Ignorar secciones [Game] y comentarios
                        if not line or line.startswith('[') or line.startswith(';') or line.startswith('#'):
                            continue
                        if '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip()
                            if key in config:
                                config[key] = value
            except (IOError, OSError) as e:
                logger.warning(f"Error reading CitizenFX.ini: {e}")

        config['_path'] = actual_path or ini_path
        config['_exists'] = actual_path is not None
        return config
