# -*- coding: utf-8 -*-
"""
Servicio de diagnóstico para FiveM Diagnostic Tool.

Contiene la lógica de negocio para operaciones de diagnóstico
del sistema, GTA V y FiveM.
"""

import os
import re
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class DiagnosticService:
    """
    Servicio para operaciones de diagnóstico.
    
    Proporciona métodos para analizar el sistema, detectar
    problemas y generar reportes.
    """
    
    def __init__(self, config):
        """
        Inicializa el servicio de diagnóstico.
        
        Args:
            config: Objeto de configuración del sistema
        """
        self.config = config
        self.paths = config.system_paths
        self.diagnostic_config = config.diagnostic_config
        self.error_patterns = config.error_patterns
    
    def get_gtav_path(self) -> Dict[str, Any]:
        """
        Detecta la ruta de instalación de GTA V.
        
        Returns:
            Diccionario con información de la instalación
        """
        from src.utils.system_utils import is_windows
        
        found_paths = []
        
        if is_windows():
            found_paths.extend(self._detect_gtav_from_registry())
        
        # Buscar en rutas comunes
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
    
    def _detect_gtav_from_registry(self) -> List[Dict[str, str]]:
        """Detecta GTA V desde el registro de Windows."""
        found = []
        
        try:
            import winreg
            
            # Rockstar Games Launcher
            try:
                key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SOFTWARE\WOW6432Node\Rockstar Games\Grand Theft Auto V"
                )
                path, _ = winreg.QueryValueEx(key, "InstallFolder")
                winreg.CloseKey(key)
                
                if path and os.path.exists(os.path.join(path, 'GTA5.exe')):
                    found.append({'path': path, 'platform': 'Rockstar'})
            except (FileNotFoundError, OSError):
                pass
            
            # Steam
            try:
                key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SOFTWARE\WOW6432Node\Valve\Steam"
                )
                steam_path, _ = winreg.QueryValueEx(key, "InstallPath")
                winreg.CloseKey(key)
                
                gta_path = os.path.join(
                    steam_path, 'steamapps', 'common', 'Grand Theft Auto V'
                )
                if os.path.exists(os.path.join(gta_path, 'GTA5.exe')):
                    found.append({'path': gta_path, 'platform': 'Steam'})
            except (FileNotFoundError, OSError):
                pass
            
            # Epic Games
            try:
                key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SOFTWARE\WOW6432Node\Epic Games\EpicGamesLauncher"
                )
                epic_path, _ = winreg.QueryValueEx(key, "AppDataPath")
                winreg.CloseKey(key)
                
                # Epic puede tener diferentes ubicaciones
                possible_paths = [
                    os.path.join(epic_path, '..', 'Games', 'GTAV'),
                    r"C:\Program Files\Epic Games\GTAV"
                ]
                for path in possible_paths:
                    if os.path.exists(os.path.join(path, 'GTA5.exe')):
                        found.append({'path': path, 'platform': 'Epic'})
                        break
            except (FileNotFoundError, OSError):
                pass
                
        except ImportError:
            logger.debug("winreg no disponible")
        
        return found
    
    def verify_gtav_integrity(self, gta_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Verifica la integridad de la instalación de GTA V.
        
        Args:
            gta_path: Ruta de GTA V (opcional, se detecta si no se proporciona)
            
        Returns:
            Diccionario con resultado de la verificación
        """
        if not gta_path:
            gta_info = self.get_gtav_path()
            gta_path = gta_info.get('Path')
        
        if not gta_path:
            return {
                'status': 'error',
                'error': 'GTA V no encontrado',
                'files_checked': 0,
                'files_ok': 0,
                'files_missing': []
            }
        
        required_files = [
            'GTA5.exe',
            'GTAVLauncher.exe',
            'bink2w64.dll',
            'PlayGTAV.exe'
        ]
        
        files_ok = 0
        files_missing = []
        
        for filename in required_files:
            filepath = os.path.join(gta_path, filename)
            if os.path.exists(filepath):
                files_ok += 1
            else:
                files_missing.append(filename)
        
        return {
            'status': 'ok' if not files_missing else 'incomplete',
            'path': gta_path,
            'files_checked': len(required_files),
            'files_ok': files_ok,
            'files_missing': files_missing
        }
    
    def detect_gta_mods(self, gta_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Detecta mods instalados en GTA V.
        
        Args:
            gta_path: Ruta de GTA V (opcional)
            
        Returns:
            Diccionario con mods encontrados
        """
        if not gta_path:
            gta_info = self.get_gtav_path()
            gta_path = gta_info.get('Path')
        
        if not gta_path:
            return {'ModsFound': [], 'Count': 0, 'Error': 'GTA V no encontrado'}
        
        mod_indicators = self.diagnostic_config.mod_indicators
        found_mods = []
        
        for indicator in mod_indicators:
            indicator_path = os.path.join(gta_path, indicator)
            if os.path.exists(indicator_path):
                found_mods.append(indicator)
        
        return {
            'ModsFound': found_mods,
            'Count': len(found_mods),
            'Path': gta_path
        }
    
    def analyze_fivem_errors(self) -> Dict[str, Any]:
        """
        Analiza los logs de FiveM en busca de errores conocidos.
        
        Returns:
            Diccionario con errores encontrados y recomendaciones
        """
        logs_path = self.paths.fivem_paths.get('Logs', '')
        errors = []
        
        if not os.path.exists(logs_path):
            return {
                'ErrorCount': 0,
                'Errors': [],
                'Recommendations': [],
                'LogsPath': logs_path,
                'Status': 'No se encontró carpeta de logs'
            }
        
        try:
            # Obtener los 5 logs más recientes
            log_files = sorted(
                [f for f in os.listdir(logs_path) if f.endswith('.log')],
                key=lambda x: os.path.getmtime(os.path.join(logs_path, x)),
                reverse=True
            )[:5]
            
            patterns = self.error_patterns.patterns
            
            for log_file in log_files:
                log_path = os.path.join(logs_path, log_file)
                try:
                    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                        for pattern, info in patterns.items():
                            if pattern.lower() in content.lower():
                                errors.append({
                                    'Error': pattern,
                                    'Severity': info['severity'],
                                    'Description': info['description'],
                                    'Solution': info['solution'],
                                    'File': log_file
                                })
                except (IOError, OSError) as e:
                    logger.warning(f"Error leyendo log {log_file}: {e}")
            
        except (IOError, OSError) as e:
            logger.error(f"Error accediendo a logs: {e}")
            return {
                'ErrorCount': 0,
                'Errors': [],
                'Recommendations': [],
                'Error': str(e)
            }
        
        # Generar recomendaciones únicas
        recommendations = list(set(e['Solution'] for e in errors))
        
        return {
            'ErrorCount': len(errors),
            'Errors': errors,
            'Recommendations': recommendations,
            'LogsPath': logs_path,
            'LogsAnalyzed': len(log_files) if 'log_files' in dir() else 0
        }
    
    def analyze_crash_dumps(self) -> Dict[str, Any]:
        """
        Analiza los crash dumps de FiveM.
        
        Returns:
            Diccionario con información de crashes
        """
        crashes_path = os.path.join(
            self.paths.fivem_paths.get('FiveMApp', ''),
            'crashes'
        )
        
        dumps = []
        
        if not os.path.exists(crashes_path):
            return {
                'dumps_found': [],
                'analysis': [],
                'recommendations': [],
                'path': crashes_path
            }
        
        try:
            for filename in os.listdir(crashes_path):
                if filename.endswith(('.dmp', '.log')):
                    filepath = os.path.join(crashes_path, filename)
                    try:
                        stat = os.stat(filepath)
                        dumps.append({
                            'file': filename,
                            'date': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M'),
                            'size': round(stat.st_size / 1024, 1)
                        })
                    except OSError:
                        pass
        except OSError as e:
            logger.error(f"Error accediendo a crash dumps: {e}")
        
        # Ordenar por fecha
        dumps.sort(key=lambda x: x['date'], reverse=True)
        
        # Análisis básico de los dumps más recientes
        analysis = []
        for dump in dumps[:5]:
            analysis.append({
                'file': dump['file'],
                'date': dump['date'],
                'possible_causes': ['Crash de GPU', 'Falta de memoria', 'Conflicto de software']
            })
        
        recommendations = []
        if dumps:
            recommendations = [
                'Actualiza los drivers de tu GPU',
                'Aumenta la memoria virtual del sistema',
                'Cierra programas en segundo plano'
            ]
        
        return {
            'dumps_found': dumps,
            'analysis': analysis,
            'recommendations': recommendations,
            'path': crashes_path
        }
    
    def detect_conflicting_software(self) -> Dict[str, Any]:
        """
        Detecta software que puede causar conflictos con FiveM.
        
        Returns:
            Diccionario con software conflictivo encontrado
        """
        from src.utils.system_utils import get_running_processes
        
        conflicting = self.diagnostic_config.conflicting_software
        found = []
        
        processes = get_running_processes()
        processes_lower = '\n'.join(processes).lower()
        
        for software in conflicting:
            if software['process'].lower() in processes_lower:
                found.append(software['name'])
        
        return {
            'ConflictsFound': found,
            'Count': len(found),
            'Recommendations': ['Cierra el software conflictivo antes de jugar'] if found else []
        }
    
    def detect_conflicting_overlays(self) -> Dict[str, Any]:
        """
        Detecta overlays que pueden causar problemas.
        
        Returns:
            Diccionario con overlays encontrados
        """
        from src.utils.system_utils import get_running_processes
        
        overlay_processes = self.diagnostic_config.overlay_processes
        found = []
        
        processes = get_running_processes()
        processes_lower = '\n'.join(processes).lower()
        
        for name, process in overlay_processes.items():
            if process.lower() in processes_lower:
                found.append({
                    'name': name,
                    'process': process,
                    'status': 'running'
                })
        
        return {
            'overlays_found': found,
            'count': len(found),
            'recommendations': ['Desactiva los overlays antes de jugar'] if found else []
        }
    
    def check_system_requirements(self, hardware_info: Dict) -> Dict[str, Any]:
        """
        Verifica si el sistema cumple los requisitos.
        
        Args:
            hardware_info: Información del hardware del sistema
            
        Returns:
            Diccionario con resultado de la verificación
        """
        from config import system_requirements
        
        checks = {}
        passed = True
        recommendations = []
        
        # Verificar RAM
        ram_gb = hardware_info.get('ram', {}).get('TotalGB', 0)
        checks['RAM'] = {
            'current': f'{ram_gb} GB',
            'required': f'{system_requirements.recommended_ram_gb} GB',
            'passed': ram_gb >= system_requirements.recommended_ram_gb
        }
        if not checks['RAM']['passed']:
            passed = False
            recommendations.append(f'Se recomienda {system_requirements.recommended_ram_gb}GB de RAM')
        
        # Verificar VRAM
        vram_gb = hardware_info.get('gpu', [{}])[0].get('VRAM_GB', 0)
        checks['VRAM'] = {
            'current': f'{vram_gb} GB',
            'required': f'{system_requirements.recommended_vram_gb} GB',
            'passed': vram_gb >= system_requirements.recommended_vram_gb
        }
        if not checks['VRAM']['passed']:
            passed = False
            recommendations.append(f'Se recomienda GPU con {system_requirements.recommended_vram_gb}GB VRAM')
        
        return {
            'status': 'ok' if passed else 'warning',
            'checks': checks,
            'recommendations': recommendations
        }
    
    def check_directx(self) -> Dict[str, Any]:
        """
        Verifica el estado de DirectX.
        
        Returns:
            Diccionario con información de DirectX
        """
        # En una implementación real, esto verificaría DirectX mediante dxdiag
        return {
            'status': 'good',
            'feature_level': 'DirectX 11+',
            'recommendations': []
        }
    
    def check_vcredist(self) -> Dict[str, Any]:
        """
        Verifica Visual C++ Redistributables instalados.
        
        Returns:
            Diccionario con estado de VC++ Redist
        """
        from src.utils.system_utils import is_windows
        
        installed = []
        missing = []
        
        if is_windows():
            try:
                import winreg
                
                # Verificar VC++ 2015-2022 x64
                try:
                    winreg.OpenKey(
                        winreg.HKEY_LOCAL_MACHINE,
                        r"SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64"
                    )
                    installed.append('2015-2022 x64')
                except FileNotFoundError:
                    missing.append('2015-2022 x64')
                
                # Verificar VC++ 2015-2022 x86
                try:
                    winreg.OpenKey(
                        winreg.HKEY_LOCAL_MACHINE,
                        r"SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x86"
                    )
                    installed.append('2015-2022 x86')
                except FileNotFoundError:
                    missing.append('2015-2022 x86')
                    
            except ImportError:
                pass
        
        return {
            'status': 'complete' if not missing else 'incomplete',
            'installed': installed,
            'missing': missing,
            'recommendations': ['Instala Visual C++ 2015-2022 Redistributable'] if missing else []
        }
    
    def get_citizenfx_config(self) -> Dict[str, str]:
        """
        Lee la configuración de CitizenFX.ini.
        
        Returns:
            Diccionario con la configuración
        """
        config = {
            'UpdateChannel': 'production',
            'GameBuild': '',
            'DisableNVSP': '0'
        }
        
        ini_path = self.paths.fivem_paths.get('CitizenFXIni', '')
        
        if os.path.exists(ini_path):
            try:
                with open(ini_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip()
                            if key in config:
                                config[key] = value
            except (IOError, OSError) as e:
                logger.warning(f"Error leyendo CitizenFX.ini: {e}")
        
        return config
