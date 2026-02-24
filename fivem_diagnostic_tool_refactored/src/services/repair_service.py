# -*- coding: utf-8 -*-
"""
Servicio de reparación para FiveM Diagnostic Tool.

Contiene la lógica de negocio para operaciones de reparación
y limpieza del sistema.
"""

import os
import shutil
import time
import logging
from typing import Dict, List, Optional, Any, Callable

from src.utils.file_utils import (
    get_folder_size,
    safe_remove_file,
    safe_remove_directory,
    backup_item,
    ensure_directory_exists
)
from src.utils.system_utils import (
    is_windows,
    run_command,
    run_powershell,
    kill_processes
)
from src.utils.validation import validate_backup_path, validate_repair_ids

logger = logging.getLogger(__name__)


class RepairService:
    """
    Servicio para operaciones de reparación.
    
    Proporciona métodos para reparar problemas comunes de FiveM,
    limpiar caché y optimizar el sistema.
    """
    
    def __init__(self, config, session):
        """
        Inicializa el servicio de reparación.
        
        Args:
            config: Objeto de configuración del sistema
            session: Sesión de diagnóstico actual
        """
        self.config = config
        self.session = session
        self.paths = config.system_paths
        self.diagnostic_config = config.diagnostic_config
        self.timeout_config = config.timeout_config
    
    def _record_repair(self, success: bool, message: str) -> None:
        """Registra el resultado de una reparación."""
        self.session.repair_stats.increment_attempted()
        if success:
            self.session.repair_stats.increment_successful()
            self.session.report.add_repair_applied(message)
        else:
            self.session.repair_stats.increment_failed()
            self.session.report.add_repair_failed(message)
    
    def kill_fivem_processes(self) -> Dict[str, Any]:
        """
        Termina todos los procesos de FiveM.
        
        Returns:
            Diccionario con resultado de la operación
        """
        processes = self.diagnostic_config.fivem_processes
        results = kill_processes(processes)
        
        killed = sum(1 for success in results.values() if success)
        
        if killed > 0:
            self._record_repair(True, f'{killed} procesos terminados')
        
        time.sleep(self.timeout_config.process_kill_wait)
        
        return {
            'success': True,
            'killed': killed,
            'details': results
        }
    
    def clear_fivem_cache_selective(self) -> Dict[str, Any]:
        """
        Limpia la caché de FiveM de forma selectiva.
        
        Solo elimina carpetas seguras que no afectan la configuración.
        
        Returns:
            Diccionario con resultado de la operación
        """
        self.kill_fivem_processes()
        
        cache_path = self.paths.fivem_paths.get('Cache', '')
        
        if not os.path.exists(cache_path):
            return {
                'success': False,
                'error': 'Carpeta de caché no encontrada',
                'cleaned_mb': 0
            }
        
        # Crear backup antes de limpiar
        backup_item(
            cache_path,
            'FiveM_Cache',
            self.paths.backup_folder,
            'Cache'
        )
        
        safe_folders = self.diagnostic_config.safe_cache_folders
        size_freed = 0
        cleared = 0
        errors = []
        
        for folder in safe_folders:
            folder_path = os.path.join(cache_path, folder)
            if os.path.exists(folder_path):
                try:
                    size_freed += get_folder_size(folder_path)
                    if safe_remove_directory(folder_path):
                        cleared += 1
                except Exception as e:
                    errors.append(f"{folder}: {str(e)}")
        
        size_mb = round(size_freed / (1024 * 1024), 2)
        
        if cleared > 0:
            self._record_repair(True, f'Caché selectiva limpiada ({size_mb} MB)')
        
        return {
            'success': True,
            'cleaned_mb': size_mb,
            'cleared': cleared,
            'errors': errors if errors else None
        }
    
    def clear_fivem_cache_complete(self) -> Dict[str, Any]:
        """
        Limpia completamente la caché de FiveM.
        
        Incluye crashes, logs y server-cache.
        
        Returns:
            Diccionario con resultado de la operación
        """
        self.kill_fivem_processes()
        
        fivem_app = self.paths.fivem_paths.get('FiveMApp', '')
        
        # Crear backup completo
        backup_item(
            fivem_app,
            'FiveM_Complete',
            self.paths.backup_folder,
            'Cache'
        )
        
        folders_to_clean = [
            self.paths.fivem_paths.get('Cache', ''),
            os.path.join(fivem_app, 'crashes'),
            os.path.join(fivem_app, 'logs'),
            os.path.join(fivem_app, 'server-cache')
        ]
        
        size_freed = 0
        
        for folder in folders_to_clean:
            if os.path.exists(folder):
                try:
                    size_freed += get_folder_size(folder)
                    safe_remove_directory(folder)
                except Exception as e:
                    logger.warning(f"Error limpiando {folder}: {e}")
        
        size_mb = round(size_freed / (1024 * 1024), 2)
        self._record_repair(True, f'Caché completa limpiada ({size_mb} MB)')
        
        return {
            'success': True,
            'cleaned_mb': size_mb
        }
    
    def remove_conflicting_dlls(self) -> Dict[str, Any]:
        """
        Elimina DLLs conflictivas de System32.
        
        Returns:
            Diccionario con resultado de la operación
        """
        dlls = self.diagnostic_config.conflicting_dlls
        system32 = os.path.join(self.paths.system_root, 'System32')
        
        found = []
        removed = []
        errors = []
        
        for dll in dlls:
            dll_path = os.path.join(system32, dll)
            if os.path.exists(dll_path):
                found.append(dll)
                try:
                    # Crear backup
                    backup_item(
                        dll_path,
                        dll,
                        self.paths.backup_folder,
                        'DLLs'
                    )
                    
                    if safe_remove_file(dll_path):
                        removed.append(dll)
                except Exception as e:
                    errors.append(f"{dll}: {str(e)}")
        
        if removed:
            self._record_repair(True, f'{len(removed)} DLLs conflictivas eliminadas')
        
        return {
            'success': True,
            'found': found,
            'removed': removed,
            'errors': errors if errors else None
        }
    
    def repair_ros_authentication(self) -> Dict[str, Any]:
        """
        Repara problemas de autenticación de Rockstar Online Services.
        
        Returns:
            Diccionario con resultado de la operación
        """
        files_to_delete = [
            self.paths.fivem_paths.get('RosId', ''),
            self.paths.fivem_paths.get('DigitalEntitlements', '')
        ]
        
        deleted = 0
        errors = []
        
        for filepath in files_to_delete:
            if os.path.exists(filepath):
                try:
                    # Crear backup
                    backup_item(
                        filepath,
                        os.path.basename(filepath),
                        self.paths.backup_folder,
                        'ROS'
                    )
                    
                    if os.path.isdir(filepath):
                        if safe_remove_directory(filepath):
                            deleted += 1
                    else:
                        if safe_remove_file(filepath):
                            deleted += 1
                except Exception as e:
                    errors.append(str(e))
        
        if deleted > 0:
            self._record_repair(True, 'Autenticación ROS reparada')
        
        return {
            'success': True,
            'deleted': deleted,
            'errors': errors if errors else None
        }
    
    def disable_gta_mods(self, gta_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Desactiva los mods de GTA V renombrándolos.
        
        Args:
            gta_path: Ruta de GTA V (opcional)
            
        Returns:
            Diccionario con resultado de la operación
        """
        if not gta_path:
            from src.services.diagnostic_service import DiagnosticService
            diag = DiagnosticService(self.config)
            gta_info = diag.get_gtav_path()
            gta_path = gta_info.get('Path')
        
        if not gta_path:
            return {
                'success': False,
                'error': 'GTA V no encontrado',
                'disabled_count': 0
            }
        
        mod_files = ['dinput8.dll', 'ScriptHookV.dll', 'dsound.dll']
        disabled = 0
        errors = []
        
        for mod in mod_files:
            mod_path = os.path.join(gta_path, mod)
            if os.path.exists(mod_path):
                try:
                    # Crear backup
                    backup_item(
                        mod_path,
                        mod,
                        self.paths.backup_folder,
                        'Mods'
                    )
                    
                    # Renombrar para desactivar
                    disabled_path = mod_path + '.disabled'
                    os.rename(mod_path, disabled_path)
                    disabled += 1
                except Exception as e:
                    errors.append(f"{mod}: {str(e)}")
        
        if disabled > 0:
            self._record_repair(True, f'{disabled} mods desactivados')
        
        return {
            'success': True,
            'disabled_count': disabled,
            'errors': errors if errors else None
        }
    
    def close_conflicting_software(self) -> Dict[str, Any]:
        """
        Cierra software conflictivo en ejecución.
        
        Returns:
            Diccionario con resultado de la operación
        """
        from src.services.diagnostic_service import DiagnosticService
        
        diag = DiagnosticService(self.config)
        conflicts = diag.detect_conflicting_software()
        
        process_map = {
            'MSI Afterburner': 'MSIAfterburner.exe',
            'RivaTuner': 'RTSS.exe',
            'Fraps': 'fraps.exe',
            'Razer Cortex': 'RazerCortex.exe'
        }
        
        closed = 0
        
        for conflict in conflicts.get('ConflictsFound', []):
            if conflict in process_map:
                result = run_command(
                    ['taskkill', '/F', '/IM', process_map[conflict]],
                    timeout=10
                )
                if result and result.returncode == 0:
                    closed += 1
        
        if closed > 0:
            self._record_repair(True, f'{closed} programas conflictivos cerrados')
        
        return {
            'success': True,
            'closed': closed
        }
    
    def add_firewall_exclusions(self) -> Dict[str, Any]:
        """
        Agrega reglas de firewall para FiveM.
        
        Returns:
            Diccionario con resultado de la operación
        """
        if not is_windows():
            return {'success': False, 'error': 'Solo disponible en Windows'}
        
        fivem_exe = os.path.join(
            self.paths.fivem_paths.get('LocalAppData', ''),
            'FiveM.exe'
        )
        
        try:
            # Regla de entrada
            run_command([
                'netsh', 'advfirewall', 'firewall', 'add', 'rule',
                'name=FiveM Inbound',
                'dir=in',
                'action=allow',
                f'program={fivem_exe}',
                'enable=yes'
            ], timeout=10)
            
            # Regla de salida
            run_command([
                'netsh', 'advfirewall', 'firewall', 'add', 'rule',
                'name=FiveM Outbound',
                'dir=out',
                'action=allow',
                f'program={fivem_exe}',
                'enable=yes'
            ], timeout=10)
            
            self._record_repair(True, 'Reglas de firewall configuradas')
            return {'success': True}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def add_defender_exclusions(self) -> Dict[str, Any]:
        """
        Agrega exclusiones en Windows Defender para FiveM.
        
        Returns:
            Diccionario con resultado de la operación
        """
        if not is_windows():
            return {'success': False, 'error': 'Solo disponible en Windows'}
        
        paths_to_exclude = [
            self.paths.fivem_paths.get('LocalAppData', ''),
            self.paths.fivem_paths.get('CitizenFX', '')
        ]
        
        added = 0
        errors = []
        
        for path in paths_to_exclude:
            if os.path.exists(path):
                result = run_powershell(
                    f'Add-MpPreference -ExclusionPath "{path}"',
                    timeout=10
                )
                if result is not None:
                    added += 1
                else:
                    errors.append(f"No se pudo agregar exclusión para {path}")
        
        if added > 0:
            self._record_repair(True, 'Exclusiones de Defender configuradas')
        
        return {
            'success': added > 0,
            'added': added,
            'errors': errors if errors else None
        }
    
    def run_advanced_repair(self, selected_repairs: List[int]) -> Dict[str, Any]:
        """
        Ejecuta reparaciones avanzadas seleccionadas.
        
        Args:
            selected_repairs: Lista de IDs de reparación a ejecutar
            
        Returns:
            Diccionario con resultados de cada reparación
        """
        # Validar IDs de reparación
        valid_ids = validate_repair_ids(selected_repairs)
        
        if not valid_ids:
            return {
                'success': False,
                'error': 'No se seleccionaron reparaciones válidas',
                'results': []
            }
        
        # Mapeo de IDs a funciones
        repair_functions: Dict[int, tuple] = {
            1: ('Terminar procesos', self.kill_fivem_processes),
            2: ('Limpiar caché selectiva', self.clear_fivem_cache_selective),
            3: ('Limpiar caché completa', self.clear_fivem_cache_complete),
            4: ('Eliminar DLLs conflictivas', self.remove_conflicting_dlls),
            5: ('Reparar ROS', self.repair_ros_authentication),
            6: ('Desactivar mods', self.disable_gta_mods),
            7: ('Cerrar conflictos', self.close_conflicting_software),
            8: ('Configurar Firewall', self.add_firewall_exclusions),
            9: ('Configurar Defender', self.add_defender_exclusions),
            10: ('Optimizar paginación', self._optimize_page_file),
            11: ('Optimizar gráficos', self._optimize_graphics_config),
            12: ('Configurar Texture Budget', self._configure_texture_budget),
            13: ('Optimizar Windows', self._optimize_windows)
        }
        
        results = []
        
        for repair_id in valid_ids:
            if repair_id in repair_functions:
                name, func = repair_functions[repair_id]
                try:
                    result = func()
                    success = result.get('success', True) if isinstance(result, dict) else True
                    results.append({
                        'id': repair_id,
                        'name': name,
                        'success': success,
                        'details': result
                    })
                except Exception as e:
                    logger.error(f"Error en reparación {name}: {e}")
                    results.append({
                        'id': repair_id,
                        'name': name,
                        'success': False,
                        'error': str(e)
                    })
        
        return {
            'success': True,
            'results': results,
            'total': len(results),
            'successful': sum(1 for r in results if r['success'])
        }
    
    def _optimize_page_file(self) -> Dict[str, Any]:
        """Optimiza el archivo de paginación."""
        # Esta función solo genera recomendaciones
        from src.services.hardware_service import HardwareService
        
        hw = HardwareService(self.config)
        ram_info = hw.get_ram_info()
        ram_gb = ram_info.get('TotalGB', 8)
        
        recommended_mb = int(ram_gb * 1.5 * 1024)
        
        self.session.report.add_recommendation(
            f'Configura el archivo de paginación a {recommended_mb} MB'
        )
        
        return {
            'success': True,
            'recommended_mb': recommended_mb
        }
    
    def _optimize_graphics_config(self) -> Dict[str, Any]:
        """Optimiza la configuración gráfica de GTA V."""
        settings_dir = os.path.join(
            self.paths.userprofile,
            'Documents', 'Rockstar Games', 'GTA V'
        )
        settings_path = os.path.join(settings_dir, 'settings.xml')
        
        if not os.path.exists(settings_path):
            # Crear configuración optimizada
            ensure_directory_exists(settings_dir)
            optimized = '''<?xml version="1.0"?>
<Settings>
    <MSAA value="0"/>
    <FXAA value="1"/>
    <VSync value="2"/>
    <MotionBlur value="0"/>
    <DOF value="0"/>
</Settings>'''
            try:
                with open(settings_path, 'w', encoding='utf-8') as f:
                    f.write(optimized)
                self._record_repair(True, 'Configuración gráfica optimizada creada')
                return {'success': True, 'path': settings_path, 'created': True}
            except Exception as e:
                return {'success': False, 'error': str(e)}
        
        # Optimizar configuración existente
        try:
            backup_item(
                settings_path,
                'settings.xml',
                self.paths.backup_folder,
                'Config'
            )
            
            with open(settings_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            optimizations = {
                'MSAA value="2"': 'MSAA value="0"',
                'MSAA value="4"': 'MSAA value="0"',
                'MSAA value="8"': 'MSAA value="0"',
                'MotionBlur value="1"': 'MotionBlur value="0"',
                'DOF value="1"': 'DOF value="0"'
            }
            
            changes = 0
            for old, new in optimizations.items():
                if old in content:
                    content = content.replace(old, new)
                    changes += 1
            
            with open(settings_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self._record_repair(True, f'Configuración gráfica optimizada ({changes} cambios)')
            return {'success': True, 'path': settings_path, 'changes': changes}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _configure_texture_budget(self) -> Dict[str, Any]:
        """Configura el Texture Budget según la VRAM."""
        from src.services.hardware_service import HardwareService
        
        hw = HardwareService(self.config)
        gpu_info = hw.get_gpu_info()
        
        vram = gpu_info[0].get('VRAM_GB', 4) if gpu_info else 4
        budget = self.config.texture_budget_config.get_recommended_budget(vram)
        
        self.session.report.add_recommendation(
            f'Configura Extended Texture Budget a {budget}%'
        )
        
        return {
            'success': True,
            'vram_detected': vram,
            'recommended_budget': budget
        }
    
    def _optimize_windows(self) -> Dict[str, Any]:
        """Aplica optimizaciones de Windows para gaming."""
        if not is_windows():
            return {'success': False, 'error': 'Solo disponible en Windows'}
        
        optimizations = []
        failed = []
        
        # Desactivar Game DVR
        try:
            run_command([
                'reg', 'add',
                r'HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\GameDVR',
                '/v', 'AppCaptureEnabled',
                '/t', 'REG_DWORD',
                '/d', '0',
                '/f'
            ], timeout=10)
            optimizations.append('Game DVR desactivado')
        except Exception:
            failed.append('Game DVR')
        
        # Desactivar Game Bar
        try:
            run_command([
                'reg', 'add',
                r'HKCU\SOFTWARE\Microsoft\GameBar',
                '/v', 'AllowAutoGameMode',
                '/t', 'REG_DWORD',
                '/d', '0',
                '/f'
            ], timeout=10)
            optimizations.append('Game Bar desactivado')
        except Exception:
            failed.append('Game Bar')
        
        if optimizations:
            for opt in optimizations:
                self._record_repair(True, opt)
        
        return {
            'success': len(optimizations) > 0,
            'optimizations': optimizations,
            'failed': failed,
            'requires_restart': True
        }
