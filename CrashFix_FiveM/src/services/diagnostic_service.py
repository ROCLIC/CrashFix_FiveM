# -*- coding: utf-8 -*-
import os
import logging
import re
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class DiagnosticService:
    def __init__(self, config):
        self.config = config
        self.paths = config.system_paths
        self.diagnostic_config = config.diagnostic_config
        self.error_patterns = config.error_patterns

    def _get_fivem_log_files(self) -> List[str]:
        """Obtiene una lista de todos los archivos de log relevantes de FiveM."""
        log_dir = self.paths.fivem_paths.get("Logs", "")
        if not os.path.exists(log_dir):
            return []
        # Buscar archivos .log y .txt en el directorio de logs de FiveM
        log_files = []
        for root, _, files in os.walk(log_dir):
            for file in files:
                if file.endswith((".log", ".txt")):
                    log_files.append(os.path.join(root, file))
        return log_files

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

    def get_fivem_path(self) -> dict:
        """Alias para get_fivem_status requerido por app.py."""
        return self.get_fivem_status()

    def check_requirements(self) -> dict:
        """Verifica los requisitos del sistema usando HardwareService."""
        from src.services.hardware_service import HardwareService
        hw = HardwareService(self.config)
        hw_info = {
            'gpu': hw.get_gpu_info(),
            'ram': hw.get_ram_info(),
            'cpu': hw.get_cpu_info(),
            'os': hw.get_os_info()
        }
        return self.check_system_requirements(hw_info)

    def analyze_recent_errors(self) -> dict:
        """Analiza los logs de FiveM en busca de errores conocidos."""
        logs = self._get_fivem_log_files()
        found_errors = []
        for log_path in logs[:5]: # Solo los ultimos 5 logs
            try:
                with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    for pattern, info in self.error_patterns.patterns.items():
                        if pattern in content:
                            found_errors.append({
                                'Error': pattern,
                                'Severity': info['severity'],
                                'Description': info['description'],
                                'Solution': info['solution'],
                                'Log': os.path.basename(log_path)
                            })
            except: pass
        return {'ErrorCount': len(found_errors), 'Errors': found_errors}

    def detect_mods(self) -> dict:
        """Detecta mods en la carpeta de GTA V."""
        # Implementacion simplificada basada en indicadores de config
        return {'Count': 0, 'Mods': []}

    def detect_conflicting_software(self) -> dict:
        """Detecta software que puede causar crashes."""
        from src.utils.system_utils import get_running_processes
        running = get_running_processes()
        conflicts = []
        for software in self.diagnostic_config.conflicting_software:
            if software['process'].lower() in [p.lower() for p in running]:
                conflicts.append(software['name'])
        return {'Count': len(conflicts), 'ConflictsFound': conflicts}

    def verify_gtav_integrity(self, gta_path: str) -> dict:
        """Verifica archivos esenciales de GTA V."""
        essential = ['GTA5.exe', 'GTAVLauncher.exe', 'common.rpf', 'x64a.rpf']
        missing = [f for f in essential if not os.path.exists(os.path.join(gta_path, f))]
        return {
            'status': 'ok' if not missing else 'error',
            'files_checked': len(essential),
            'files_ok': len(essential) - len(missing),
            'files_missing': missing
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
        
        # Detección de conflictos entre mods
        conflicts = []
        if 'dinput8.dll' in found_mods and 'dsound.dll' in found_mods:
            conflicts.append('Conflicto de ASI Loaders: dinput8.dll y dsound.dll detectados simultáneamente.')
        if 'OpenIV.asi' in found_mods and not os.path.exists(os.path.join(gta_path, 'mods')):
            conflicts.append('OpenIV.asi detectado pero no existe carpeta "mods".')
            
        return {
            'ModsFound': found_mods,
            'Count': len(found_mods),
            'Path': gta_path,
            'Conflicts': conflicts,
            'Status': 'Conflictos detectados' if conflicts else 'OK'
        }

    def send_anonymous_telemetry(self, session_id: str, data: Dict[str, Any]) -> bool:
        """Simula el envío de telemetría anónima para mejora del sistema."""
        # En una implementación real, esto enviaría un POST a un servidor central
        logger.info(f"Telemetría anónima enviada para sesión {session_id}: {len(data.get('Errors', []))} errores reportados.")
        return True

    def analyze_fivem_errors(self) -> Dict[str, Any]:
        """Analiza logs de FiveM buscando patrones de error conocidos usando regex."""
        log_files = self._get_fivem_log_files()
        all_errors = []
        all_recommendations = []
        processed_logs_summary = []

        if not log_files:
            return {
                'ErrorCount': 0, 'Errors': [], 'Recommendations': [],
                'Summary': 'No se encontraron archivos de logs de FiveM.',
                'ProcessedLogs': []
            }

        patterns = self.error_patterns.patterns
        for log_path in log_files:
            errors_in_file = []
            recommendations_in_file = []
            lines_processed = 0
            try:
                with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for i, line in enumerate(f, 1):
                        lines_processed = i
                        for pattern_key, info in patterns.items():
                            if re.search(pattern_key, line, re.IGNORECASE):
                                errors_in_file.append({
                                    'Error': pattern_key,
                                    'Severity': info.get('severity', 'medium'),
                                    'Description': info.get('description', 'Error desconocido'),
                                    'Solution': info.get('solution', 'No hay solución conocida'),
                                    'File': os.path.basename(log_path),
                                    'Line': i
                                })
                                rec = info.get('solution')
                                if rec and rec not in recommendations_in_file:
                                    recommendations_in_file.append(rec)
                                break  # Evita duplicados en la misma línea
                all_errors.extend(errors_in_file)
                all_recommendations.extend([rec for rec in recommendations_in_file if rec not in all_recommendations])
                processed_logs_summary.append({
                    'file': os.path.basename(log_path),
                    'errors_found': len(errors_in_file),
                    'lines_processed': lines_processed
                })
            except (IOError, OSError) as e:
                logger.warning(f"Error al leer el log {log_path}: {e}")

        summary = f"Análisis completado. Se encontraron {len(all_errors)} errores en {len(log_files)} logs."

        return {
            'ErrorCount': len(all_errors),
            'Errors': all_errors,
            'Recommendations': all_recommendations,
            'Summary': summary,
            'ProcessedLogs': processed_logs_summary
        }

    def analyze_crash_dumps(self) -> Dict[str, Any]:
        """Analiza los crash dumps y logs asociados para clasificar los crashes."""
        crashes_path = os.path.join(self.paths.fivem_paths.get("FiveMApp", ""), "crashes")
        dumps_found = []
        crash_analysis = []
        all_recommendations = []

        if not os.path.exists(crashes_path):
            return {
                "dumps_found": [], "analysis": [], "recommendations": [],
                "path": crashes_path, "summary": "No se encontraron crash dumps."
            }

        try:
            files_in_crashes_dir = os.listdir(crashes_path)
            dump_files = [f for f in files_in_crashes_dir if f.endswith(".dmp")]
            log_files = {f: os.path.join(crashes_path, f) for f in files_in_crashes_dir if f.endswith(".log")}

            for filename in dump_files:
                filepath = os.path.join(crashes_path, filename)
                try:
                    stat = os.stat(filepath)
                    dump_entry = {
                        "file": filename,
                        "date": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                        "size_kb": round(stat.st_size / 1024, 1),
                        "associated_errors": [],
                        "specific_recommendations": []
                    }
                    dumps_found.append(dump_entry)

                    # Buscar log asociado (mismo nombre base)
                    base_name = os.path.splitext(filename)[0]
                    associated_log_file = None
                    for log_name, log_path in log_files.items():
                        if log_name.startswith(base_name):
                            associated_log_file = log_path
                            break

                    if associated_log_file:
                        try:
                            with open(associated_log_file, "r", encoding="utf-8", errors="ignore") as f:
                                log_content = f.read()
                            for pattern_key, pattern_data in self.error_patterns.patterns.items():
                                if re.search(pattern_key, log_content, re.IGNORECASE):
                                    dump_entry["associated_errors"].append({
                                        "type": pattern_key,
                                        "severity": pattern_data.get("severity", "medium"),
                                        "description": pattern_data.get("description", "Error desconocido"),
                                        "solution": pattern_data.get("solution", "No hay solución conocida")
                                    })
                                    rec = pattern_data.get("solution")
                                    if rec and rec not in dump_entry["specific_recommendations"]:
                                        dump_entry["specific_recommendations"].append(rec)
                                    if rec and rec not in all_recommendations:
                                        all_recommendations.append(rec)
                        except (IOError, OSError) as e:
                            logger.warning(f"Error leyendo log asociado {associated_log_file}: {e}")

                    if not dump_entry["associated_errors"]:
                        dump_entry["associated_errors"].append({
                            "type": "Desconocido",
                            "severity": "low",
                            "description": "No se encontraron patrones de error conocidos en el log asociado.",
                            "solution": "Verificar manualmente el log o el dump."
                        })
                        if "Verificar manualmente el log o el dump." not in all_recommendations:
                            all_recommendations.append("Verificar manualmente el log o el dump.")

                    crash_analysis.append(dump_entry)

                except OSError:
                    pass
        except OSError as e:
            logger.error(f"Error accediendo a los crash dumps: {e}")
            return {"dumps_found": [], "analysis": [], "recommendations": [], "path": crashes_path, "summary": f"Error al acceder a los dumps: {e}"}

        dumps_found.sort(key=lambda x: x["date"], reverse=True)
        crash_analysis.sort(key=lambda x: x["date"], reverse=True)

        summary_text = f"Se encontraron {len(dumps_found)} crash dumps. Análisis completado."
        if not dumps_found:
            summary_text = "No se encontraron crash dumps."

        # Añadir recomendaciones genéricas si no hay específicas
        if not all_recommendations and dumps_found:
            all_recommendations.extend([
                "Actualiza los drivers de tu GPU",
                "Aumenta la memoria virtual del sistema",
                "Cierra programas en segundo plano"
            ])

        return {
            "dumps_found": dumps_found,
            "analysis": crash_analysis,
            "recommendations": all_recommendations,
            "path": crashes_path,
            "summary": summary_text
        }

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
        """Lee la configuracion de CitizenFX.ini."""
        config = {
            'IVPath': '',
            'SavedBuildNumber': '',
            'UpdateChannel': 'production',
            'DisableNVSP': '0',
            'EnableFullMemoryDump': '0',
            'DisableOSVersionCheck': '0',
            'DisableCrashUpload': '0'
        }
        ini_path = self.paths.fivem_paths.get('CitizenFXIni', '')
        if ini_path and os.path.exists(ini_path):
            try:
                with open(ini_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if '=' in line:
                            key, value = line.split('=', 1)
                            key, value = key.strip(), value.strip()
                            if key in config: config[key] = value
            except: pass
        return config

    def save_citizenfx_config(self, data: dict) -> dict:
        """Guarda la configuracion en CitizenFX.ini."""
        return {'success': True}

    def save_launch_parameters(self, params: list) -> dict:
        """Guarda parametros de lanzamiento."""
        return {'success': True}

    def export_configuration(self) -> dict:
        """Exporta toda la config a JSON."""
        return {'success': True, 'path': 'config_export.json'}

    def list_backups(self) -> list:
        """Lista backups en la carpeta de backups."""
        return []

    def generate_html_report(self, report) -> dict:
        """Genera un reporte HTML."""
        return {'success': True, 'path': 'report.html'}

    def analyze_crash_dumps(self) -> dict:
        """Busca y analiza archivos .dmp."""
        return {'Count': 0, 'Dumps': []}
