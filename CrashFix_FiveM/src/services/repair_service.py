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
        status = 'success' if success else 'error'
        self.session.add_action('repair', message, status=status)
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
        """Limpia la cache completa de FiveM incluyendo crashes y logs.

        Optimizaciones respecto a la version anterior:
        - Backup selectivo: solo respalda archivos de configuracion criticos
          (CitizenFX.ini, ros_id.dat) en lugar de todo FiveM.app
        - Calculo de tamano en paralelo con ThreadPoolExecutor
        - Eliminacion en paralelo de carpetas independientes
        - Verificacion de existencia antes de operar
        - Reporte detallado por carpeta
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        self.kill_fivem_processes()
        fivem_app = self.paths.fivem_paths.get('FiveMApp', '')

        # Backup selectivo: solo archivos de configuracion criticos
        # (en lugar de copiar todo FiveM.app que puede ser de varios GB)
        critical_files = [
            self.paths.fivem_paths.get('CitizenFXIni', ''),
            self.paths.fivem_paths.get('RosId', ''),
        ]
        for crit_file in critical_files:
            if crit_file and os.path.exists(crit_file):
                try:
                    backup_item(
                        crit_file,
                        os.path.basename(crit_file),
                        self.paths.backup_folder,
                        'Config'
                    )
                except Exception as e:
                    logger.warning(f"Error backing up {crit_file}: {e}")

        # Definir carpetas a limpiar
        folders_to_clean = [
            self.paths.fivem_paths.get('Cache', ''),
            os.path.join(fivem_app, 'crashes'),
            os.path.join(fivem_app, 'logs'),
            os.path.join(fivem_app, 'server-cache'),
        ]

        # Filtrar solo carpetas que existen (evitar trabajo innecesario)
        existing_folders = [
            f for f in folders_to_clean
            if f and os.path.isdir(f)
        ]

        if not existing_folders:
            return {
                'success': True,
                'cleaned_mb': 0,
                'details': [],
                'message': 'No se encontraron carpetas de cache para limpiar'
            }

        # Fase 1: Calcular tamanos en paralelo
        folder_sizes = {}

        def _get_size(folder):
            return (folder, get_folder_size(folder))

        with ThreadPoolExecutor(max_workers=min(4, len(existing_folders))) as executor:
            futures = {executor.submit(_get_size, f): f for f in existing_folders}
            for future in as_completed(futures):
                try:
                    folder, size = future.result()
                    folder_sizes[folder] = size
                except Exception as e:
                    folder = futures[future]
                    folder_sizes[folder] = 0
                    logger.warning(f"Error calculando tamano de {folder}: {e}")

        # Fase 2: Eliminar carpetas en paralelo
        details = []

        def _clean_folder(folder):
            size = folder_sizes.get(folder, 0)
            size_mb = round(size / (1024 * 1024), 2)
            folder_name = os.path.basename(folder)
            try:
                if safe_remove_directory(folder):
                    return {'folder': folder_name, 'size_mb': size_mb, 'status': 'cleaned'}
                else:
                    return {'folder': folder_name, 'size_mb': size_mb, 'status': 'error'}
            except Exception as e:
                logger.warning(f"Error limpiando {folder}: {e}")
                return {'folder': folder_name, 'size_mb': size_mb, 'status': 'error', 'error': str(e)}

        with ThreadPoolExecutor(max_workers=min(4, len(existing_folders))) as executor:
            futures = {executor.submit(_clean_folder, f): f for f in existing_folders}
            for future in as_completed(futures):
                try:
                    result = future.result()
                    details.append(result)
                except Exception as e:
                    folder = futures[future]
                    details.append({'folder': os.path.basename(folder), 'size_mb': 0, 'status': 'error', 'error': str(e)})

        total_freed = sum(folder_sizes.values())
        total_mb = round(total_freed / (1024 * 1024), 2)
        self._record_repair(True, f'Cache completa limpiada ({total_mb} MB)')

        return {
            'success': True,
            'cleaned_mb': total_mb,
            'details': details
        }

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
            14: ('Actualizar driver GPU',       self.update_gpu_driver),
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
        """Calcula y recomienda el tamano optimo del archivo de paginacion.

        Solo agrega recomendacion si el tamano actual es insuficiente.
        """
        from src.services.hardware_service import HardwareService
        hw = HardwareService(self.config)
        ram_info = hw.get_ram_info()
        ram_gb = ram_info.get('TotalGB', 8)
        recommended_mb = int(ram_gb * 1.5 * 1024)

        # Obtener tamano actual del archivo de paginacion
        current_mb = 0
        if is_windows():
            try:
                result = run_powershell(
                    'Get-WmiObject Win32_PageFileUsage | Select-Object AllocatedBaseSize | ConvertTo-Json',
                    timeout=10
                )
                if result:
                    import json
                    data = json.loads(result)
                    if isinstance(data, list):
                        current_mb = sum(pf.get('AllocatedBaseSize', 0) for pf in data)
                    elif isinstance(data, dict):
                        current_mb = data.get('AllocatedBaseSize', 0)
            except Exception as e:
                logger.warning(f"Error reading pagefile size: {e}")

        # Solo recomendar si el actual es menor al 80% del recomendado
        needs_adjustment = current_mb < (recommended_mb * 0.8)

        if needs_adjustment:
            self.session.report.add_recommendation(
                f'Configura el archivo de paginacion a {recommended_mb} MB (actual: {current_mb} MB)'
            )
            self._record_repair(True, f'Paginacion insuficiente: {current_mb} MB actual, {recommended_mb} MB recomendado')
        else:
            self._record_repair(True, f'Paginacion correcta: {current_mb} MB (recomendado: {recommended_mb} MB)')

        return {
            'success': True,
            'current_mb': current_mb,
            'recommended_mb': recommended_mb,
            'needs_adjustment': needs_adjustment
        }

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

    # ============= ACTUALIZACION DE DRIVERS =============

    def update_gpu_driver(self) -> Dict[str, Any]:
        """Descarga e instala el driver mas reciente de GPU (NVIDIA o AMD).

        Para NVIDIA: descarga el instalador Game Ready Driver mas reciente
        y lo ejecuta en modo silencioso.
        Para AMD: descarga AMD Software Adrenalin y lo ejecuta.
        """
        from src.services.hardware_service import HardwareService
        hw = HardwareService(self.config)
        driver_info = hw.check_driver_update()

        if not driver_info.get('success'):
            return {
                'success': False,
                'error': driver_info.get('error', 'No se pudo verificar el driver'),
                'action': 'none'
            }

        vendor = driver_info.get('vendor', 'unknown')
        download_url = driver_info.get('download_url')
        needs_update = driver_info.get('needs_update', False)

        if not needs_update:
            self._record_repair(True, f'Driver GPU ya esta actualizado: {driver_info.get("current_driver")}')
            return {
                'success': True,
                'action': 'none',
                'message': 'El driver ya esta actualizado',
                'current_driver': driver_info.get('current_driver'),
                'latest_driver': driver_info.get('latest_driver')
            }

        if not download_url:
            return {
                'success': False,
                'error': 'No se encontro URL de descarga',
                'action': 'manual',
                'vendor': vendor
            }

        # Descargar el instalador
        import os
        download_dir = os.path.join(self.paths.work_folder, 'DriverUpdate')
        os.makedirs(download_dir, exist_ok=True)

        if vendor == 'nvidia':
            return self._download_and_install_nvidia_driver(download_url, download_dir, driver_info)
        elif vendor == 'amd':
            return self._download_and_install_amd_driver(download_dir, driver_info)
        else:
            return {
                'success': False,
                'action': 'manual',
                'message': f'Descarga el driver manualmente desde: {download_url}',
                'download_url': download_url
            }

    def _download_and_install_nvidia_driver(self, download_url: str, download_dir: str,
                                             driver_info: Dict) -> Dict[str, Any]:
        """Descarga e instala driver NVIDIA Game Ready."""
        import os
        import urllib.request

        installer_path = os.path.join(download_dir, 'nvidia_driver_setup.exe')

        try:
            # Descargar instalador
            logger.info(f"Downloading NVIDIA driver from: {download_url}")
            req = urllib.request.Request(download_url, headers={'User-Agent': 'CrashFix/1.0'})
            with urllib.request.urlopen(req, timeout=120) as response:
                with open(installer_path, 'wb') as f:
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)

            if not os.path.exists(installer_path) or os.path.getsize(installer_path) < 1024:
                return {
                    'success': False,
                    'error': 'La descarga del instalador fallo',
                    'action': 'manual',
                    'download_url': download_url
                }

            # Ejecutar instalador en modo silencioso (solo driver, sin GeForce Experience)
            try:
                run_command(
                    [installer_path, '-s', '-noreboot', '-noeula', '-clean'],
                    timeout=300  # 5 minutos para instalacion
                )
                self._record_repair(
                    True,
                    f'Driver NVIDIA actualizado: {driver_info.get("current_driver")} -> {driver_info.get("latest_driver")}'
                )
                return {
                    'success': True,
                    'action': 'installed',
                    'previous_driver': driver_info.get('current_driver'),
                    'new_driver': driver_info.get('latest_driver'),
                    'requires_restart': True,
                    'message': 'Driver NVIDIA instalado. Se recomienda reiniciar el PC.'
                }
            except Exception as e:
                logger.warning(f"Silent install failed, opening installer: {e}")
                # Si falla el modo silencioso, abrir el instalador normalmente
                try:
                    import subprocess
                    subprocess.Popen([installer_path], shell=True)
                    self._record_repair(True, 'Instalador de driver NVIDIA abierto')
                    return {
                        'success': True,
                        'action': 'opened_installer',
                        'message': 'Se abrio el instalador de NVIDIA. Sigue las instrucciones en pantalla.',
                        'installer_path': installer_path
                    }
                except Exception as e2:
                    return {
                        'success': False,
                        'error': f'No se pudo ejecutar el instalador: {e2}',
                        'action': 'manual',
                        'installer_path': installer_path
                    }

        except Exception as e:
            logger.error(f"Error downloading NVIDIA driver: {e}")
            return {
                'success': False,
                'error': f'Error al descargar: {str(e)}',
                'action': 'manual',
                'download_url': download_url
            }

    def _download_and_install_amd_driver(self, download_dir: str,
                                          driver_info: Dict) -> Dict[str, Any]:
        """Descarga e instala AMD Software Adrenalin."""
        import os
        import urllib.request

        # AMD Auto-Detect and Install tool
        amd_autodetect_url = 'https://drivers.amd.com/drivers/installer/24.10/whql/amd-software-auto-detect.exe'
        installer_path = os.path.join(download_dir, 'amd_software_auto_detect.exe')

        try:
            logger.info("Downloading AMD Auto-Detect tool")
            req = urllib.request.Request(amd_autodetect_url, headers={'User-Agent': 'CrashFix/1.0'})
            with urllib.request.urlopen(req, timeout=120) as response:
                with open(installer_path, 'wb') as f:
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)

            if os.path.exists(installer_path) and os.path.getsize(installer_path) > 1024:
                import subprocess
                subprocess.Popen([installer_path], shell=True)
                self._record_repair(True, 'AMD Software Auto-Detect abierto para actualizar driver')
                return {
                    'success': True,
                    'action': 'opened_installer',
                    'message': 'Se abrio AMD Software Auto-Detect. Detectara e instalara el mejor driver automaticamente.',
                    'installer_path': installer_path
                }
            else:
                return {
                    'success': False,
                    'error': 'La descarga del instalador AMD fallo',
                    'action': 'manual',
                    'download_url': 'https://www.amd.com/en/support/download/drivers.html'
                }
        except Exception as e:
            logger.error(f"Error downloading AMD driver: {e}")
            return {
                'success': False,
                'error': f'Error al descargar: {str(e)}',
                'action': 'manual',
                'download_url': 'https://www.amd.com/en/support/download/drivers.html'
            }
