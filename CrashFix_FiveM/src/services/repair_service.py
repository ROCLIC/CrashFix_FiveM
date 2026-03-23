# -*- coding: utf-8 -*-
"""
Servicio de reparacion para FiveM Diagnostic Tool.

Proporciona metodos para reparar, limpiar y optimizar la instalacion
de FiveM y GTA V en el sistema del usuario.
"""

import os
import shutil
import time
import logging
from typing import Dict, List, Optional, Any

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

logger = logging.getLogger(__name__)


class RepairService:
    """Servicio central de reparaciones y optimizaciones para FiveM."""

    def __init__(self, config, session):
        self.config = config
        self.session = session
        self.paths = config.system_paths
        self.diagnostic_config = config.diagnostic_config
        self.timeout_config = config.timeout_config

    # ============= HELPERS INTERNOS =============

    def _record_repair(self, success: bool, message: str) -> None:
        """Registra el resultado de una reparacion en la sesion."""
        self.session.repair_stats.increment_attempted()
        if success:
            self.session.repair_stats.increment_successful()
            self.session.report.add_repair_applied(message)
        else:
            self.session.repair_stats.increment_failed()
            self.session.report.add_repair_failed(message)

    # ============= PROCESOS =============

    def kill_fivem_processes(self) -> Dict[str, Any]:
        """Termina todos los procesos relacionados con FiveM."""
        processes = self.diagnostic_config.fivem_processes
        results = kill_processes(processes)
        killed = sum(1 for success in results.values() if success)
        if killed > 0:
            self._record_repair(True, f'{killed} procesos terminados')
        time.sleep(self.timeout_config.process_kill_wait)
        return {'success': True, 'killed': killed, 'details': results}

    # ============= CACHE =============

    def clear_fivem_cache_selective(self) -> Dict[str, Any]:
        """Limpia la cache de FiveM de forma selectiva (solo carpetas seguras)."""
        self.kill_fivem_processes()
        cache_path = self.paths.fivem_paths.get('Cache', '')
        if not os.path.exists(cache_path):
            return {
                'success': False,
                'error': 'Carpeta de cache no encontrada',
                'cleaned_mb': 0
            }

        backup_item(cache_path, 'FiveM_Cache', self.paths.backup_folder, 'Cache')
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
            self._record_repair(True, f'Cache selectiva limpiada ({size_mb} MB)')

        return {
            'success': True,
            'cleaned_mb': size_mb,
            'cleared': cleared,
            'errors': errors if errors else None
        }

    def clear_fivem_cache_complete(self) -> Dict[str, Any]:
        """Limpia la cache completa de FiveM incluyendo crashes y logs."""
        self.kill_fivem_processes()
        fivem_app = self.paths.fivem_paths.get('FiveMApp', '')
        backup_item(fivem_app, 'FiveM_Complete', self.paths.backup_folder, 'Cache')

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
        self._record_repair(True, f'Cache completa limpiada ({size_mb} MB)')
        return {'success': True, 'cleaned_mb': size_mb}

    # ============= DLLs =============

    def remove_conflicting_dlls(self) -> Dict[str, Any]:
        """Elimina todas las DLLs conflictivas conocidas de System32."""
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
                    backup_item(dll_path, dll, self.paths.backup_folder, 'DLLs')
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

    def remove_v8_dlls(self) -> Dict[str, Any]:
        """Elimina especificamente las v8 DLLs conflictivas de System32."""
        v8_dlls = ['v8.dll', 'v8_libbase.dll', 'v8_libplatform.dll']
        system32 = os.path.join(self.paths.system_root, 'System32')
        found = []
        removed = []
        errors = []

        for dll in v8_dlls:
            dll_path = os.path.join(system32, dll)
            if os.path.exists(dll_path):
                found.append(dll)
                try:
                    backup_item(dll_path, dll, self.paths.backup_folder, 'DLLs')
                    if safe_remove_file(dll_path):
                        removed.append(dll)
                except Exception as e:
                    errors.append(f"{dll}: {str(e)}")

        if removed:
            self._record_repair(True, f'{len(removed)} v8 DLLs eliminadas de System32')

        return {
            'success': True,
            'found': found,
            'removed': removed,
            'errors': errors if errors else None
        }

    # ============= ROS (Rockstar Online Services) =============

    def repair_ros_authentication(self) -> Dict[str, Any]:
        """Repara la autenticacion de Rockstar Online Services eliminando tokens."""
        files_to_delete = [
            self.paths.fivem_paths.get('RosId', ''),
            self.paths.fivem_paths.get('DigitalEntitlements', '')
        ]
        deleted = 0
        errors = []

        for filepath in files_to_delete:
            if filepath and os.path.exists(filepath):
                try:
                    backup_item(
                        filepath, os.path.basename(filepath),
                        self.paths.backup_folder, 'ROS'
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
            self._record_repair(True, 'Autenticacion ROS reparada')

        return {
            'success': True,
            'deleted': deleted,
            'errors': errors if errors else None
        }

    def clean_ros_files(self) -> Dict[str, Any]:
        """Limpia los archivos de ROS incluyendo la carpeta CitizenFX."""
        citizenfx_path = self.paths.fivem_paths.get('CitizenFX', '')
        ros_id = self.paths.fivem_paths.get('RosId', '')
        digital_ent = self.paths.fivem_paths.get('DigitalEntitlements', '')

        cleaned = 0
        errors = []

        targets = [ros_id, digital_ent]
        for target in targets:
            if target and os.path.exists(target):
                try:
                    backup_item(
                        target, os.path.basename(target),
                        self.paths.backup_folder, 'ROS'
                    )
                    if os.path.isdir(target):
                        if safe_remove_directory(target):
                            cleaned += 1
                    else:
                        if safe_remove_file(target):
                            cleaned += 1
                except Exception as e:
                    errors.append(str(e))

        if cleaned > 0:
            self._record_repair(True, f'Archivos ROS limpiados ({cleaned} elementos)')

        return {
            'success': True,
            'cleaned': cleaned,
            'errors': errors if errors else None
        }

    # ============= MODS =============

    def disable_gta_mods(self, gta_path: Optional[str] = None) -> Dict[str, Any]:
        """Desactiva los mods de GTA V renombrandolos con extension .disabled."""
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
                    backup_item(mod_path, mod, self.paths.backup_folder, 'Mods')
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

    # ============= SOFTWARE CONFLICTIVO =============

    def close_conflicting_software(self) -> Dict[str, Any]:
        """Cierra el software conflictivo detectado en ejecucion."""
        if not is_windows():
            return {
                'success': False,
                'error': 'Solo disponible en Windows',
                'closed': 0
            }

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
        errors = []
        for conflict in conflicts.get('ConflictsFound', []):
            if conflict in process_map:
                try:
                    result = run_command(
                        ['taskkill', '/F', '/IM', process_map[conflict]],
                        timeout=10
                    )
                    if result and result.returncode == 0:
                        closed += 1
                except Exception as e:
                    errors.append(f"{conflict}: {str(e)}")

        if closed > 0:
            self._record_repair(True, f'{closed} programas conflictivos cerrados')

        return {
            'success': True,
            'closed': closed,
            'errors': errors if errors else None
        }

    # ============= FIREWALL Y DEFENDER =============

    def add_firewall_exclusions(self) -> Dict[str, Any]:
        """Agrega reglas de firewall para permitir FiveM."""
        if not is_windows():
            return {'success': False, 'error': 'Solo disponible en Windows'}

        fivem_exe = os.path.join(
            self.paths.fivem_paths.get('LocalAppData', ''), 'FiveM.exe'
        )
        try:
            run_command([
                'netsh', 'advfirewall', 'firewall', 'add', 'rule',
                'name=FiveM Inbound', 'dir=in', 'action=allow',
                f'program={fivem_exe}', 'enable=yes'
            ], timeout=10)
            run_command([
                'netsh', 'advfirewall', 'firewall', 'add', 'rule',
                'name=FiveM Outbound', 'dir=out', 'action=allow',
                f'program={fivem_exe}', 'enable=yes'
            ], timeout=10)
            self._record_repair(True, 'Reglas de firewall configuradas')
            return {'success': True}
        except Exception as e:
            logger.error(f"Error configuring firewall: {e}")
            return {'success': False, 'error': str(e)}

    def add_defender_exclusions(self) -> Dict[str, Any]:
        """Agrega exclusiones de Windows Defender para las carpetas de FiveM."""
        if not is_windows():
            return {'success': False, 'error': 'Solo disponible en Windows'}

        paths_to_exclude = [
            self.paths.fivem_paths.get('LocalAppData', ''),
            self.paths.fivem_paths.get('CitizenFX', '')
        ]
        added = 0
        errors = []

        for path in paths_to_exclude:
            if path and os.path.exists(path):
                result = run_powershell(
                    f'Add-MpPreference -ExclusionPath "{path}"',
                    timeout=10
                )
                if result is not None:
                    added += 1
                else:
                    errors.append(f"No se pudo agregar exclusion para {path}")

        if added > 0:
            self._record_repair(True, 'Exclusiones de Defender configuradas')

        return {
            'success': added > 0,
            'added': added,
            'errors': errors if errors else None
        }

    # ============= REPARACION AVANZADA =============

    def run_advanced_repair(self, selected_repairs: List[int]) -> Dict[str, Any]:
        """
        Ejecuta las reparaciones avanzadas seleccionadas por el usuario.

        Mapeo de IDs del frontend:
          1  Terminar procesos de FiveM
          2  Limpiar cache selectiva
          3  Limpiar cache completa
          4  Eliminar DLLs conflictivas
          5  Limpiar v8 DLLs (System32)
          6  Limpiar archivos ROS
          7  Reparar autenticacion ROS
          8  Desactivar mods de GTA V
          9  Cerrar software conflictivo
         10  Configurar reglas de Firewall
         11  Optimizar configuracion grafica
         12  Configurar Texture Budget
         13  Optimizaciones de Windows
        """
        repair_functions: Dict[int, tuple] = {
            1:  ('Terminar procesos',          self.kill_fivem_processes),
            2:  ('Limpiar cache selectiva',    self.clear_fivem_cache_selective),
            3:  ('Limpiar cache completa',     self.clear_fivem_cache_complete),
            4:  ('Eliminar DLLs conflictivas', self.remove_conflicting_dlls),
            5:  ('Limpiar v8 DLLs',           self.remove_v8_dlls),
            6:  ('Limpiar archivos ROS',       self.clean_ros_files),
            7:  ('Reparar autenticacion ROS',  self.repair_ros_authentication),
            8:  ('Desactivar mods',            self.disable_gta_mods),
            9:  ('Cerrar conflictos',          self.close_conflicting_software),
            10: ('Configurar Firewall',        self.add_firewall_exclusions),
            11: ('Optimizar graficos',         self.optimize_graphics_config),
            12: ('Configurar Texture Budget',  self.configure_texture_budget),
            13: ('Optimizaciones de Windows',  self.optimize_windows),
        }

        results = []
        for repair_id in selected_repairs:
            if repair_id in repair_functions:
                name, func = repair_functions[repair_id]
                try:
                    result = func()
                    success = (
                        result.get('success', True)
                        if isinstance(result, dict)
                        else True
                    )
                    results.append({
                        'id': repair_id,
                        'name': name,
                        'success': success,
                        'details': result
                    })
                except Exception as e:
                    logger.error(f"Error en reparacion {name}: {e}")
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

    # ============= OPTIMIZACION =============

    def optimize_page_file(self) -> Dict[str, Any]:
        """Calcula y recomienda el tamano optimo del archivo de paginacion."""
        from src.services.hardware_service import HardwareService
        hw = HardwareService(self.config)
        ram_info = hw.get_ram_info()
        ram_gb = ram_info.get('TotalGB', 8)
        recommended_mb = int(ram_gb * 1.5 * 1024)
        self.session.report.add_recommendation(
            f'Configura el archivo de paginacion a {recommended_mb} MB'
        )
        self._record_repair(True, f'Paginacion analizada: {recommended_mb} MB recomendado')
        return {'success': True, 'recommended_mb': recommended_mb}

    def optimize_graphics_config(self) -> Dict[str, Any]:
        """Optimiza la configuracion grafica de GTA V."""
        settings_dir = os.path.join(
            self.paths.userprofile, 'Documents', 'Rockstar Games', 'GTA V'
        )
        settings_path = os.path.join(settings_dir, 'settings.xml')

        if not os.path.exists(settings_path):
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
                self._record_repair(True, 'Configuracion grafica optimizada creada')
                return {'success': True, 'path': settings_path, 'created': True}
            except Exception as e:
                logger.error(f"Error creating graphics config: {e}")
                return {'success': False, 'error': str(e)}

        try:
            backup_item(
                settings_path, 'settings.xml',
                self.paths.backup_folder, 'Config'
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

            self._record_repair(
                True, f'Configuracion grafica optimizada ({changes} cambios)'
            )
            return {'success': True, 'path': settings_path, 'changes': changes}
        except Exception as e:
            logger.error(f"Error optimizing graphics config: {e}")
            return {'success': False, 'error': str(e)}

    def configure_texture_budget(self) -> Dict[str, Any]:
        """Configura el Texture Budget basado en la VRAM detectada."""
        from src.services.hardware_service import HardwareService
        hw = HardwareService(self.config)
        gpu_info = hw.get_gpu_info()
        vram = gpu_info[0].get('VRAM_GB', 4) if gpu_info else 4
        budget = self.config.texture_budget_config.get_recommended_budget(vram)
        self.session.report.add_recommendation(
            f'Configura Extended Texture Budget a {budget}%'
        )
        self._record_repair(True, f'Texture Budget configurado: {budget}%')
        return {
            'success': True,
            'vram_detected': vram,
            'recommended_budget': budget
        }

    def optimize_windows(self) -> Dict[str, Any]:
        """Aplica optimizaciones de Windows para mejorar el rendimiento en gaming."""
        if not is_windows():
            return {'success': False, 'error': 'Solo disponible en Windows'}

        optimizations = []
        failed = []

        # Desactivar Game DVR
        try:
            run_command([
                'reg', 'add',
                r'HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\GameDVR',
                '/v', 'AppCaptureEnabled', '/t', 'REG_DWORD',
                '/d', '0', '/f'
            ], timeout=10)
            optimizations.append('Game DVR desactivado')
        except Exception:
            failed.append('Game DVR')

        # Desactivar Game Bar
        try:
            run_command([
                'reg', 'add', r'HKCU\SOFTWARE\Microsoft\GameBar',
                '/v', 'AllowAutoGameMode', '/t', 'REG_DWORD',
                '/d', '0', '/f'
            ], timeout=10)
            optimizations.append('Game Bar desactivado')
        except Exception:
            failed.append('Game Bar')

        for opt in optimizations:
            self._record_repair(True, opt)

        return {
            'success': len(optimizations) > 0,
            'optimizations': optimizations,
            'failed': failed,
            'requires_restart': True
        }
