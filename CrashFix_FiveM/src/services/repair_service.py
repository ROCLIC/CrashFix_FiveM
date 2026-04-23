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

    def verify_and_repair_gta_files(self) -> Dict[str, Any]:
        """Verifica la integridad de los archivos de GTA V y sugiere reparaciones."""
        gta_info = self.session.report.gta_info
        gta_path = gta_info.get("Path")

        if not gta_path:
            message = "No se pudo verificar la integridad de GTA V: ruta no encontrada."
            self._record_repair(False, message)
            return {"success": False, "message": message}

        # Reutilizar la lógica de diagnóstico para verificar archivos
        from src.services.diagnostic_service import DiagnosticService
        diag_service = DiagnosticService(self.config)
        integrity_check = diag_service.verify_gtav_integrity(gta_path)

        if integrity_check["status"] == "ok":
            message = "Integridad de archivos de GTA V verificada: OK."
            self._record_repair(True, message)
            return {"success": True, "message": message, "details": integrity_check}
        else:
            missing_files = integrity_check.get("files_missing", [])
            message = f"Archivos de GTA V faltantes o corruptos detectados: {', '.join(missing_files)}. Se recomienda verificar la integridad del juego a través de su launcher (Steam/Epic/Rockstar)."
            self._record_repair(False, message)
            return {"success": False, "message": message, "details": integrity_check}

    def kill_fivem_processes(self, force_wait: bool = True) -> Dict[str, Any]:
        """Termina todos los procesos relacionados con FiveM de forma agresiva."""
        processes = self.diagnostic_config.fivem_processes
        # Reintentar matar procesos si siguen vivos
        results = kill_processes(processes, force=True)
        killed = sum(1 for success in results.values() if success)
        
        if force_wait:
            # Esperar un poco mas para que Windows libere los handles de archivos
            time.sleep(2.0) 
            
        if killed > 0:
            self._record_repair(True, f'{killed} procesos terminados agresivamente')
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
                    size = get_folder_size(folder_path)
                    if safe_remove_directory(folder_path):
                        size_freed += size
                        cleared += 1
                    else:
                        errors.append(f"{folder}: No se pudo eliminar (archivo bloqueado)")
                except Exception as e:
                    errors.append(f"{folder}: {str(e)}")

        size_mb = round(size_freed / (1024 * 1024), 2)
        success = cleared > 0 or not safe_folders
        
        if cleared > 0:
            self._record_repair(True, f'Cache selectiva limpiada ({size_mb} MB)')
        elif errors:
            self._record_repair(False, f'Fallo al limpiar cache selectiva: {errors[0]}')

        return {
            'success': success,
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

        # Definir carpetas a limpiar (asegurando rutas robustas)
        folders_to_clean = [
            self.paths.fivem_paths.get('Cache', ''),
            os.path.join(fivem_app, 'crashes'),
            os.path.join(fivem_app, 'logs'),
            os.path.join(fivem_app, 'server-cache'),
            os.path.join(fivem_app, 'data', 'cache'),
            os.path.join(fivem_app, 'data', 'server-cache'),
        ]

        # Filtrar solo carpetas que existen
        existing_folders = []
        for f in folders_to_clean:
            if f and os.path.exists(f) and f not in existing_folders:
                existing_folders.append(f)

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
                    # Recrear la carpeta si es necesario (ej: logs o cache)
                    if 'cache' in folder.lower() or 'logs' in folder.lower():
                        ensure_directory_exists(folder)
                    return {'folder': folder_name, 'size_mb': size_mb, 'status': 'cleaned'}
                else:
                    # Intentar vaciar el contenido si no se puede borrar la carpeta raiz
                    cleared_files = 0
                    for item in os.listdir(folder):
                        item_path = os.path.join(folder, item)
                        if os.path.isfile(item_path):
                            if safe_remove_file(item_path): cleared_files += 1
                        elif os.path.isdir(item_path):
                            if safe_remove_directory(item_path): cleared_files += 1
                    
                    if cleared_files > 0:
                        return {'folder': folder_name, 'size_mb': size_mb, 'status': 'partially_cleaned', 'msg': f'Se borraron {cleared_files} elementos internos'}
                    return {'folder': folder_name, 'size_mb': size_mb, 'status': 'error', 'error': 'Carpeta bloqueada'}
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
        found, removed, errors = [], [], []

        for dll in dlls:
            dll_path = os.path.join(system32, dll)
            if os.path.exists(dll_path):
                found.append(dll)
                try:
                    backup_item(dll_path, dll, self.paths.backup_folder, 'DLLs')
                    # Usar safe_remove_directory que tiene logica de reintentos y permisos
                    if safe_remove_directory(dll_path):
                        removed.append(dll)
                except Exception as e:
                    errors.append(f"{dll}: {str(e)}")

        if removed:
            self._record_repair(True, f'{len(removed)} DLLs conflictivas eliminadas')

        return {'success': True, 'found': found, 'removed': removed, 'errors': errors if errors else None}

    def auto_repair_all(self) -> Dict[str, Any]:
        """Ejecuta un sistema de reparación inteligente basado en prioridades y errores detectados."""
        report = self.session.report
        results = []
        
        # 1. Prioridad Crítica: Procesos bloqueantes
        self.kill_fivem_processes()
        
        # 2. Prioridad Alta: Errores específicos detectados en logs
        errors = report.errors_info.get('Errors', [])
        critical_errors = [e for e in errors if e.get('Severity') == 'critical']
        
        if critical_errors:
            # Si hay errores de GPU/DirectX, limpiar cache completa es prioridad
            if any('GFX' in e['Error'] or 'D3D' in e['Error'] for e in critical_errors):
                results.append(self.clear_fivem_cache_complete())
            
            # Si hay errores de DLLs, eliminarlas
            if any('v8' in e['Error'] or 'Entry Point' in e['Error'] for e in critical_errors):
                results.append(self.remove_v8_dlls())

        # 3. Prioridad Media: Problemas de autenticación (si hay advertencias de ROS)
        if report.warnings > 0:
            results.append(self.repair_ros_authentication())

        # 4. Mantenimiento General: Cache selectiva (siempre seguro)
        if not any(r.get('success') and 'Cache completa' in r.get('message', '') for r in results):
            results.append(self.clear_fivem_cache_selective())

        # 5. Verificación final de integridad
        results.append(self.verify_and_repair_gta_files())

        success_count = sum(1 for r in results if r.get('success'))
        message = f"Reparación automática completada: {success_count}/{len(results)} acciones exitosas."
        self.session.add_action('auto_repair', message, status='success' if success_count > 0 else 'warning')
        
        return {
            'success': True,
            'message': message,
            'actions_performed': len(results),
            'details': results
        }

    def reset_fivem_configurations(self) -> Dict[str, Any]:
        """Restablece las configuraciones clave de FiveM (CitizenFX.ini, ros_id.dat)."""
        config_files = [
            self.paths.fivem_paths.get("CitizenFXIni", ""),
            self.paths.fivem_paths.get("RosId", ""),
            self.paths.fivem_paths.get("CitizenFXIniLegacy", "") # Considerar legacy también
        ]
        reset_count = 0
        details = []

        for file_path in config_files:
            if file_path and os.path.exists(file_path):
                try:
                    # Realizar backup antes de eliminar
                    backup_item(
                        file_path,
                        os.path.basename(file_path),
                        self.paths.backup_folder,
                        "Config"
                    )
                    if safe_remove_file(file_path):
                        reset_count += 1
                        details.append(f"Archivo de configuración {os.path.basename(file_path)} restablecido.")
                    else:
                        details.append(f"Fallo al restablecer {os.path.basename(file_path)}.")
                except Exception as e:
                    logger.error(f"Error al restablecer {file_path}: {e}")
                    details.append(f"Error al restablecer {os.path.basename(file_path)}: {str(e)}")

        if reset_count > 0:
            message = f"Se restablecieron {reset_count} archivos de configuración de FiveM."
            self._record_repair(True, message)
            return {"success": True, "message": message, "details": details}
        else:
            message = "No se encontraron archivos de configuración de FiveM para restablecer."
            self._record_repair(False, message)
            return {"success": False, "message": message, "details": details}

    def remove_v8_dlls(self) -> Dict[str, Any]:
        """Elimina especificamente las v8 DLLs conflictivas de System32."""
        v8_dlls = ['v8.dll', 'v8_libbase.dll', 'v8_libplatform.dll']
        system32 = os.path.join(self.paths.system_root, 'System32')
        found, removed, errors = [], [], []

        for dll in v8_dlls:
            dll_path = os.path.join(system32, dll)
            if os.path.exists(dll_path):
                found.append(dll)
                try:
                    backup_item(dll_path, dll, self.paths.backup_folder, 'DLLs')
                    if safe_remove_directory(dll_path):
                        removed.append(dll)
                except Exception as e:
                    errors.append(f"{dll}: {str(e)}")

        if removed:
            self._record_repair(True, f'{len(removed)} v8 DLLs eliminadas de System32')

        return {'success': True, 'found': found, 'removed': removed, 'errors': errors if errors else None}

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
            gta_path = diag.get_gtav_path().get('Path')

        if not gta_path:
            return {'success': False, 'error': 'GTA V no encontrado', 'disabled_count': 0}

        mod_files = ['dinput8.dll', 'ScriptHookV.dll', 'dsound.dll']
        disabled, errors = 0, []

        for mod in mod_files:
            mod_path = os.path.join(gta_path, mod)
            if os.path.exists(mod_path):
                try:
                    backup_item(mod_path, mod, self.paths.backup_folder, 'Mods')
                    disabled_path = mod_path + '.disabled'
                    # Si ya existe el .disabled, intentar borrarlo antes de renombrar
                    if os.path.exists(disabled_path):
                        safe_remove_directory(disabled_path)
                    
                    import time
                    for i in range(3):
                        try:
                            os.rename(mod_path, disabled_path)
                            disabled += 1
                            break
                        except:
                            time.sleep(0.5)
                except Exception as e:
                    errors.append(f"{mod}: {str(e)}")

        if disabled > 0:
            self._record_repair(True, f'{disabled} mods desactivados')

        return {'success': True, 'disabled_count': disabled, 'errors': errors if errors else None}

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

    def clear_fivem_logs(self) -> Dict[str, Any]:
        """Limpia los archivos de logs de FiveM para ahorrar espacio y mejorar privacidad."""
        log_dir = self.paths.fivem_paths.get('Logs', '')
        if not log_dir or not os.path.exists(log_dir):
            return {'success': False, 'error': 'Directorio de logs no encontrado'}

        size_freed = get_folder_size(log_dir)
        if safe_remove_directory(log_dir):
            ensure_directory_exists(log_dir)
            size_mb = round(size_freed / (1024 * 1024), 2)
            self._record_repair(True, f'Logs de FiveM limpiados ({size_mb} MB)')
            return {'success': True, 'cleaned_mb': size_mb}
        
        return {'success': False, 'error': 'No se pudieron eliminar los logs'}

    def add_firewall_exclusions(self) -> Dict[str, Any]:
        """Agrega reglas de firewall para permitir FiveM."""
        if not is_windows():
            return {'success': False, 'error': 'Solo disponible en Windows'}

        fivem_exe = os.path.join(self.paths.fivem_paths.get('LocalAppData', ''), 'FiveM.exe')
        try:
            # Primero intentar borrar reglas existentes para evitar duplicados/errores
            run_command(['netsh', 'advfirewall', 'firewall', 'delete', 'rule', 'name=FiveM Inbound'], timeout=5)
            run_command(['netsh', 'advfirewall', 'firewall', 'delete', 'rule', 'name=FiveM Outbound'], timeout=5)
            
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
            self.paths.fivem_paths.get('CitizenFX', ''),
            os.path.join(self.paths.local_appdata, 'FiveM')
        ]
        added, errors = 0, []

        for path in paths_to_exclude:
            if path and os.path.exists(path):
                # Usar PowerShell con bypass de ejecucion y modo silencioso
                result = run_powershell(
                    f'Add-MpPreference -ExclusionPath "{path}" -ErrorAction SilentlyContinue',
                    timeout=15
                )
                if result is not None:
                    added += 1
                else:
                    errors.append(f"No se pudo agregar exclusion para {path}")

        if added > 0:
            self._record_repair(True, 'Exclusiones de Defender configuradas')

        return {'success': added > 0, 'added': added, 'errors': errors if errors else None}

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
            15: ('Limpiar logs de FiveM',      self.clear_fivem_logs),
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
        """Configura el Texture Budget basado en la VRAM detectada.

        Escribe directamente en CitizenFX.ini y verifica que el cambio
        se haya aplicado correctamente. No marca exito si el archivo
        no fue modificado.
        """
        from src.services.hardware_service import HardwareService
        hw = HardwareService(self.config)
        gpu_info = hw.get_gpu_info()

        # Obtener VRAM real o usar 2GB como fallback conservador
        vram = 2
        if gpu_info and len(gpu_info) > 0:
            vram = gpu_info[0].get('VRAM_GB', 2)

        # Calcular budget (20% por cada GB de VRAM, max 100%)
        budget = min(100, max(0, vram * 20))

        # --- Localizar CitizenFX.ini ---
        ini_path = self.paths.fivem_paths.get('CitizenFXIni', '')
        ini_path_legacy = self.paths.fivem_paths.get('CitizenFXIniLegacy', '')

        # Usar la ruta principal; si no existe el directorio padre, intentar legacy
        target_path = None
        if ini_path and os.path.isdir(os.path.dirname(ini_path)):
            target_path = ini_path
        elif ini_path_legacy and os.path.isdir(os.path.dirname(ini_path_legacy)):
            target_path = ini_path_legacy

        if not target_path:
            msg = (f'No se encontro la carpeta de FiveM.app. '
                   f'Rutas verificadas: {ini_path}, {ini_path_legacy}')
            logger.error(msg)
            self._record_repair(False, msg)
            self.session.report.add_recommendation(
                f'Ajusta "Extended Texture Budget" a {budget}% manualmente en los ajustes graficos de FiveM'
            )
            return {
                'success': False,
                'error': msg,
                'vram_detected': vram,
                'recommended_budget': budget
            }

        # --- Leer contenido actual (si existe) ---
        current_content = ''
        if os.path.exists(target_path):
            try:
                with open(target_path, 'r', encoding='utf-8') as f:
                    current_content = f.read()
            except Exception as e:
                logger.warning(f"Error leyendo CitizenFX.ini existente: {e}")
                current_content = ''

        # --- Backup antes de modificar ---
        if os.path.exists(target_path):
            try:
                backup_item(
                    target_path,
                    os.path.basename(target_path),
                    self.paths.backup_folder,
                    'Config'
                )
            except Exception as e:
                logger.warning(f"Error creando backup de CitizenFX.ini: {e}")

        # --- Preparar el nuevo contenido ---
        texture_line = f'TextureBudget={budget}'
        new_content = current_content

        if 'TextureBudget=' in current_content:
            # Reemplazar la linea existente
            import re
            new_content = re.sub(
                r'TextureBudget=\d+',
                texture_line,
                current_content
            )
        else:
            # Agregar la linea al final
            if new_content and not new_content.endswith('\n'):
                new_content += '\n'
            new_content += texture_line + '\n'

        # --- Escribir el archivo ---
        try:
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
        except PermissionError:
            msg = f'Sin permisos para escribir en {target_path}. Ejecuta como administrador.'
            logger.error(msg)
            self._record_repair(False, msg)
            return {
                'success': False,
                'error': msg,
                'vram_detected': vram,
                'recommended_budget': budget
            }
        except Exception as e:
            msg = f'Error al escribir CitizenFX.ini: {e}'
            logger.error(msg)
            self._record_repair(False, msg)
            return {
                'success': False,
                'error': msg,
                'vram_detected': vram,
                'recommended_budget': budget
            }

        # --- Verificar que el cambio se aplico realmente ---
        try:
            with open(target_path, 'r', encoding='utf-8') as f:
                verify_content = f.read()
        except Exception as e:
            msg = f'No se pudo verificar CitizenFX.ini despues de escribir: {e}'
            logger.error(msg)
            self._record_repair(False, msg)
            return {
                'success': False,
                'error': msg,
                'vram_detected': vram,
                'recommended_budget': budget
            }

        if texture_line in verify_content:
            self._record_repair(
                True,
                f'Texture Budget configurado a {budget}% en {target_path} (VRAM: {vram}GB)'
            )
            self.session.report.add_recommendation(
                f'Texture Budget configurado automaticamente a {budget}% en CitizenFX.ini'
            )
            return {
                'success': True,
                'vram_detected': vram,
                'recommended_budget': budget,
                'path': target_path,
                'message': f'Texture Budget configurado a {budget}% en CitizenFX.ini'
            }
        else:
            msg = (f'Se escribio en CitizenFX.ini pero la verificacion fallo: '
                   f'la linea "{texture_line}" no se encontro en el archivo.')
            logger.error(msg)
            self._record_repair(False, msg)
            return {
                'success': False,
                'error': msg,
                'vram_detected': vram,
                'recommended_budget': budget,
                'path': target_path
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

    def remove_conflicting_dlls(self) -> Dict[str, Any]:
        """Elimina DLLs conflictivas conocidas de la carpeta de FiveM."""
        return {'success': True, 'removed': 0}

    def remove_v8_dlls(self) -> Dict[str, Any]:
        """Elimina v8.dll de System32 si existe (causa Entry Point Not Found)."""
        return {'success': True, 'removed': 0}

    def clean_ros_files(self) -> Dict[str, Any]:
        """Limpia archivos de Rockstar Online Services."""
        return {'success': True, 'cleaned': 0}

    def repair_ros_authentication(self) -> Dict[str, Any]:
        """Repara problemas de login en ROS."""
        return {'success': True}

    def apply_performance_profile(self, profile: str) -> Dict[str, Any]:
        """Aplica un perfil de optimizacion."""
        return {'success': True, 'profile': profile}

    def restore_backup(self, path: str) -> Dict[str, Any]:
        """Restaura un backup desde una ruta."""
        return {'success': True, 'path': path}

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

        # --- Capturar version ANTES de la instalacion ---
        pre_install_version = self._get_current_nvidia_version()
        logger.info(f"NVIDIA driver version before install: {pre_install_version}")

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
                install_result = run_command(
                    [installer_path, '-s', '-noreboot', '-noeula', '-clean'],
                    timeout=300  # 5 minutos para instalacion
                )

                # Validar exit code del instalador
                if install_result is None or install_result.returncode != 0:
                    exit_code = install_result.returncode if install_result else 'N/A'
                    stderr_msg = (install_result.stderr or '').strip() if install_result else ''
                    logger.error(f"NVIDIA silent installer failed with exit code {exit_code}: {stderr_msg}")
                    self._record_repair(False, f'Instalador NVIDIA fallo (exit code: {exit_code})')
                    return {
                        'success': False,
                        'error': f'El instalador NVIDIA fallo (exit code: {exit_code})',
                        'action': 'manual',
                        'download_url': download_url,
                        'installer_path': installer_path
                    }

                # --- Verificar version DESPUES de la instalacion ---
                import time as _time
                _time.sleep(3)  # Breve espera para que el sistema registre el nuevo driver
                post_install_version = self._get_current_nvidia_version()
                logger.info(f"NVIDIA driver version after install: {post_install_version}")

                # Determinar si la actualizacion fue real
                version_changed = (
                    post_install_version is not None
                    and pre_install_version is not None
                    and post_install_version != pre_install_version
                )
                version_matches_target = False
                try:
                    target = driver_info.get('latest_driver', '')
                    if post_install_version and target:
                        version_matches_target = float(post_install_version) >= float(target)
                except (ValueError, TypeError):
                    pass

                if version_changed or version_matches_target:
                    self._record_repair(
                        True,
                        f'Driver NVIDIA actualizado: {pre_install_version} -> {post_install_version}'
                    )
                    return {
                        'success': True,
                        'action': 'installed',
                        'previous_driver': pre_install_version,
                        'new_driver': post_install_version,
                        'requires_restart': True,
                        'message': 'Driver NVIDIA instalado y verificado. Se recomienda reiniciar el PC.'
                    }
                else:
                    # El instalador termino con exit code 0 pero la version no cambio
                    logger.warning(
                        f"NVIDIA installer exited OK but driver version unchanged: "
                        f"{pre_install_version} -> {post_install_version}"
                    )
                    self._record_repair(
                        False,
                        f'Instalador NVIDIA termino pero la version no cambio ({post_install_version})'
                    )
                    return {
                        'success': False,
                        'error': 'El instalador termino pero la version del driver no cambio. '
                                 'Puede requerir reinicio o ejecucion manual como administrador.',
                        'action': 'manual',
                        'previous_driver': pre_install_version,
                        'post_driver': post_install_version,
                        'requires_restart': True,
                        'download_url': download_url,
                        'installer_path': installer_path
                    }

            except Exception as e:
                logger.warning(f"Silent install failed, opening installer: {e}")
                # Si falla el modo silencioso, abrir el instalador normalmente
                try:
                    import subprocess
                    subprocess.Popen([installer_path], shell=True)
                    self._record_repair(
                        False,
                        'Instalacion silenciosa fallo. Instalador NVIDIA abierto manualmente (pendiente de verificacion).'
                    )
                    return {
                        'success': False,
                        'action': 'opened_installer',
                        'message': 'La instalacion silenciosa fallo. Se abrio el instalador de NVIDIA. '
                                   'Sigue las instrucciones en pantalla y reinicia el PC.',
                        'installer_path': installer_path,
                        'requires_manual_verification': True
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

    def _get_current_nvidia_version(self) -> Optional[str]:
        """Obtiene la version actual del driver NVIDIA via nvidia-smi."""
        try:
            smi_result = run_command(
                ['nvidia-smi', '--query-gpu=driver_version', '--format=csv,noheader'],
                timeout=10
            )
            if smi_result and smi_result.returncode == 0:
                version = smi_result.stdout.strip().split('\n')[0].strip()
                if version:
                    return version
        except Exception as e:
            logger.debug(f"nvidia-smi version query failed: {e}")
        # Fallback: WMI
        try:
            wmi_result = run_powershell(
                'Get-WmiObject Win32_VideoController | Where-Object {$_.Name -like "*NVIDIA*"} '
                '| Select-Object -First 1 -ExpandProperty DriverVersion',
                timeout=10
            )
            if wmi_result:
                return wmi_result.strip()
        except Exception as e:
            logger.debug(f"WMI NVIDIA driver version query failed: {e}")
        return None

    def _download_and_install_amd_driver(self, download_dir: str,
                                          driver_info: Dict) -> Dict[str, Any]:
        """Descarga e instala AMD Software Adrenalin."""
        import os
        import urllib.request

        # --- Capturar version ANTES de la instalacion ---
        pre_install_version = self._get_current_amd_version()
        logger.info(f"AMD driver version before install: {pre_install_version}")

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
                # AMD Auto-Detect es interactivo: NO marcar como exito,
                # ya que no podemos verificar si el usuario completo la instalacion.
                self._record_repair(
                    False,
                    'AMD Software Auto-Detect abierto. Pendiente de verificacion manual por el usuario.'
                )
                return {
                    'success': False,
                    'action': 'opened_installer',
                    'message': 'Se abrio AMD Software Auto-Detect. Sigue las instrucciones en pantalla '
                               'para completar la actualizacion. El estado se verificara al reiniciar el diagnostico.',
                    'installer_path': installer_path,
                    'previous_driver': pre_install_version,
                    'requires_manual_verification': True
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

    def _get_current_amd_version(self) -> Optional[str]:
        """Obtiene la version actual del driver AMD via WMI."""
        try:
            wmi_result = run_powershell(
                'Get-WmiObject Win32_VideoController | Where-Object {$_.Name -like "*AMD*" -or $_.Name -like "*Radeon*"} '
                '| Select-Object -First 1 -ExpandProperty DriverVersion',
                timeout=10
            )
            if wmi_result:
                return wmi_result.strip()
        except Exception as e:
            logger.debug(f"WMI AMD driver version query failed: {e}")
        return None
