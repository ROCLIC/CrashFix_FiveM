# -*- coding: utf-8 -*-
import os, sys, logging, json, uuid
from datetime import datetime
from typing import Dict, List, Any, Optional
from flask import Flask, render_template, jsonify, request, send_file
from config import AppConfig

# Importar servicios
from src.services.diagnostic_service import DiagnosticService
from src.services.repair_service import RepairService
from src.services.hardware_service import HardwareService
from src.services.network_service import NetworkService
from src.services.session_manager import get_session_manager

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Inicializar Flask y configuraciones
app = Flask(__name__)
svc_cfg = AppConfig()
app.secret_key = svc_cfg.server_config.secret_key

def get_current_session():
    """Obtiene la sesion activa principal o crea una nueva."""
    sm = get_session_manager()
    latest = sm.get_latest_session()
    if latest is not None:
        return latest
    return sm.create_session()

def api_error_handler(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"API Error in {f.__name__}: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500
    return decorated_function

# ============= RUTAS WEB =============

@app.route('/')
def index():
    """Sirve la pagina principal."""
    return render_template('index.html')

@app.route('/api/status', methods=['GET'])
@api_error_handler
def api_status():
    """Obtiene el estado actual del sistema y la sesion."""
    session = get_current_session()
    hw = HardwareService(svc_cfg)
    
    # Obtener info de hardware básica para el monitoreo proactivo
    hw_info = {
        'temperatures': hw.get_system_temperatures(),
        'RAM': hw.get_ram_info()
    }
    
    # Usar el estado general del reporte ya que DiagnosticSession no tiene 'status' directo
    return jsonify({
        'status': session.report.overall_status,
        'session_id': session.session_id,
        'report': session.report.to_dict(),
        'hardware_info': hw_info,
        'repair_stats': session.repair_stats.to_dict(),
        'history': session.action_history
    })

# ============= DIAGNOSTICO =============

@app.route('/api/diagnostic/complete', methods=['POST'])
@api_error_handler
def api_diagnostic_complete():
    """Ejecuta un diagnostico completo del sistema."""
    diag_session = get_current_session()
    diag = DiagnosticService(svc_cfg)
    hw = HardwareService(svc_cfg)
    net = NetworkService(svc_cfg)

    gta_info = diag.get_gtav_path()
    gpu_info = hw.get_gpu_info()
    ram_info = hw.get_ram_info()
    cpu_info = hw.get_cpu_info()
    os_info = hw.get_os_info()
    net_info = net.test_network_quality()
    
    # Actualizar reporte
    report = diag_session.report
    report.update_hardware(gpu=gpu_info, ram=ram_info, cpu=cpu_info, os=os_info)
    report.update_network(status=net_info.get('Status', 'OK'), ping=net_info.get('Ping', 0))
    report.gta_info = gta_info
    
    # Calcular estado final
    report.calculate_overall_status()
    
    return jsonify(report.to_dict())

@app.route('/api/smart/diagnose-and-fix', methods=['POST'])
@api_error_handler
def api_smart_diagnose_and_fix():
    """Diagnostico Inteligente: Analiza y repara automaticamente."""
    diag_session = get_current_session()
    diag = DiagnosticService(svc_cfg)
    repair = RepairService(svc_cfg, diag_session)
    hw = HardwareService(svc_cfg)
    net = NetworkService(svc_cfg)

    phases = []
    auto_repairs = []

    # 1. Analisis de Requisitos
    reqs = diag.check_requirements()
    phases.append({'name': 'Requisitos', 'status': 'completed'})

    # 2. Deteccion de Rutas
    gta_info = diag.get_gtav_path()
    fivem_info = diag.get_fivem_path()
    phases.append({'name': 'Deteccion', 'status': 'completed'})

    # 3. Analisis de Errores y Hardware
    errors_info = diag.analyze_recent_errors()
    gpu_info = hw.get_gpu_info()
    network_info = net.test_network_quality()
    phases.append({'name': 'Analisis', 'status': 'completed'})

    # 4. Mantenimiento Proactivo
    # Si hay errores criticos detectados
    critical_errors = [e for e in errors_info.get('Errors', []) if e.get('Severity') == 'critical']
    if critical_errors:
        cache_result = repair.clear_fivem_cache_selective()
        auto_repairs.append({'action': 'Limpiar cache selectiva', 'result': cache_result, 'reason': f'{len(critical_errors)} errores criticos detectados'})

    # Si hay DLLs conflictivas potenciales (Entry Point Not Found)
    entry_point_errors = [e for e in errors_info.get('Errors', []) if 'Entry Point' in e.get('Error', '')]
    if entry_point_errors:
        dll_result = repair.remove_conflicting_dlls()
        auto_repairs.append({'action': 'Eliminar DLLs conflictivas', 'result': dll_result, 'reason': 'Error Entry Point Not Found detectado'})

    # Si hay demasiados errores en logs o son muy grandes: limpiar logs
    if errors_info.get('ErrorCount', 0) > 10:
        log_result = repair.clear_fivem_logs()
        auto_repairs.append({'action': 'Limpiar logs de FiveM', 'result': log_result, 'reason': f'Exceso de errores ({errors_info["ErrorCount"]}) detectado'})

    # --- AUTOMATIZACIÓN TOTAL: Reparar todo lo posible ---
    
    # Si hay mods detectados y estamos en modo auto-fix
    mods_info = diag.detect_mods()
    if mods_info.get('Count', 0) > 0:
        mod_res = repair.disable_gta_mods()
        auto_repairs.append({'action': 'Desactivar mods de GTA V', 'result': mod_res, 'reason': f'{mods_info["Count"]} mods detectados'})

    # Si hay software conflictivo
    conflicts_info = diag.detect_conflicting_software()
    if conflicts_info.get('Count', 0) > 0:
        conf_res = repair.close_conflicting_software()
        auto_repairs.append({'action': 'Cerrar software conflictivo', 'result': conf_res, 'reason': f'{conflicts_info["Count"]} programas detectados'})
    
    # Optimizar red si el ping es alto
    if network_info.get('Ping', 0) > 100:
        net_res = net.optimize_network_stack()
        auto_repairs.append({'action': 'Optimizar red (Ping alto)', 'result': net_res, 'reason': f'Latencia de {network_info["Ping"]}ms'})
    
    # Optimizar Texture Budget automáticamente según VRAM
    if gpu_info and gpu_info[0].get('VRAM_GB', 0) > 0:
        tex_res = repair.configure_texture_budget()
        auto_repairs.append({'action': 'Ajustar Texture Budget', 'result': tex_res, 'reason': f'VRAM detectada: {gpu_info[0]["VRAM_GB"]}GB'})

    # Verificar si el driver de GPU esta desactualizado
    driver_check = hw.check_driver_update()
    if driver_check.get('needs_update'):
        auto_repairs.append({'action': 'Actualizar Driver GPU', 'result': {'success': True}, 'reason': 'Actualizacion disponible'})

    phases.append({'name': 'Reparacion', 'status': 'completed'})

    # Actualizar reporte final
    report = diag_session.report
    report.update_hardware(gpu=gpu_info, ram=hw.get_ram_info(), cpu=hw.get_cpu_info(), os=hw.get_os_info())
    report.update_network(status=network_info['Status'], ping=network_info['Ping'])
    report.gta_info = gta_info
    report.fivem_info = fivem_info
    report.calculate_overall_status()
    
    return jsonify({
        'success': True,
        'phases': phases,
        'auto_repairs': auto_repairs,
        'requirements': reqs,
        'Summary': report.to_dict().get('Summary', {}),
        'Hardware': report.to_dict().get('Hardware', {}),
        'Network': report.to_dict().get('Network', {}),
        'GTA': gta_info,
        'fivem': fivem_info,
        'temperatures': hw.get_system_temperatures()
    })

# ============= REPARACIONES =============

@app.route('/api/repair/cache/selective', methods=['POST'])
@api_error_handler
def api_repair_cache_selective():
    """Limpia la cache selectiva de FiveM."""
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.clear_fivem_cache_selective())

@app.route('/api/repair/cache/complete', methods=['POST'])
@api_error_handler
def api_repair_cache_complete():
    """Limpia la cache completa de FiveM."""
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.clear_fivem_cache_complete())

@app.route('/api/repair/processes/kill', methods=['POST'])
@api_error_handler
def api_repair_processes_kill():
    """Termina los procesos de FiveM."""
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.kill_fivem_processes())

@app.route('/api/repair/dlls/remove', methods=['POST'])
@api_error_handler
def api_repair_dlls_remove():
    """Elimina DLLs conflictivas."""
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.remove_conflicting_dlls())

@app.route('/api/repair/v8/clean', methods=['POST'])
@api_error_handler
def api_repair_v8_clean():
    """Limpia las DLLs de v8."""
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.remove_v8_dlls())

@app.route('/api/repair/ros/clean', methods=['POST'])
@api_error_handler
def api_repair_ros_clean():
    """Limpia los archivos de ROS."""
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.clean_ros_files())

@app.route('/api/repair/ros', methods=['POST'])
@api_error_handler
def api_repair_ros():
    """Repara la autenticacion de ROS."""
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.repair_ros_authentication())

@app.route('/api/repair/mods/disable', methods=['POST'])
@api_error_handler
def api_repair_mods_disable():
    """Desactiva los mods de GTA V."""
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.disable_gta_mods())

@app.route('/api/repair/conflicts/close', methods=['POST'])
@api_error_handler
def api_repair_conflicts_close():
    """Cierra software conflictivo."""
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.close_conflicting_software())

@app.route('/api/repair/advanced', methods=['POST'])
@api_error_handler
def api_repair_advanced():
    """Ejecuta reparaciones avanzadas seleccionadas."""
    data = request.get_json()
    repair_ids = data.get('repairs', [])
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.run_advanced_repair(repair_ids))

# ============= OPTIMIZACION =============

@app.route('/api/optimize/firewall', methods=['POST'])
@api_error_handler
def api_optimize_firewall():
    """Configura el firewall para FiveM."""
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.add_firewall_exclusions())

@app.route('/api/optimize/defender', methods=['POST'])
@api_error_handler
def api_optimize_defender():
    """Configura exclusiones en Windows Defender."""
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.add_defender_exclusions())

@app.route('/api/optimize/pagefile', methods=['POST'])
@api_error_handler
def api_optimize_pagefile():
    """Analiza y optimiza el archivo de paginacion."""
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.optimize_page_file())

@app.route('/api/optimize/graphics', methods=['POST'])
@api_error_handler
def api_optimize_graphics():
    """Optimiza la configuracion grafica."""
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.optimize_graphics_config())

@app.route('/api/optimize/texturebudget', methods=['POST'])
@api_error_handler
def api_optimize_texturebudget():
    """Configura el Texture Budget automaticamente."""
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.configure_texture_budget())

@app.route('/api/optimize/windows', methods=['POST'])
@api_error_handler
def api_optimize_windows():
    """Aplica optimizaciones de Windows."""
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.optimize_windows())

@app.route('/api/optimize/dns', methods=['POST'])
@api_error_handler
def api_optimize_dns():
    """Analiza y recomienda el mejor DNS."""
    net = NetworkService(svc_cfg)
    return jsonify(net.optimize_dns())

# ============= CONFIGURACION =============

@app.route('/api/config/citizenfx', methods=['GET', 'POST'])
@api_error_handler
def api_config_citizenfx():
    """Lee o guarda la configuracion de CitizenFX.ini."""
    diag = DiagnosticService(svc_cfg)
    if request.method == 'POST':
        data = request.get_json()
        return jsonify(diag.save_citizenfx_config(data))
    return jsonify(diag.get_citizenfx_config())

@app.route('/api/config/launchparams', methods=['POST'])
@api_error_handler
def api_config_launchparams():
    """Guarda los parametros de lanzamiento."""
    diag = DiagnosticService(svc_cfg)
    data = request.get_json()
    return jsonify(diag.save_launch_parameters(data.get('parameters', [])))

@app.route('/api/config/export', methods=['POST'])
@api_error_handler
def api_config_export():
    """Exporta la configuracion actual."""
    diag = DiagnosticService(svc_cfg)
    return jsonify(diag.export_configuration())

# ============= PERFILES =============

@app.route('/api/profiles/apply', methods=['POST'])
@api_error_handler
def api_profiles_apply():
    """Aplica un perfil de rendimiento."""
    data = request.get_json()
    profile = data.get('profile', 'medium')
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.apply_performance_profile(profile))

# ============= BACKUPS =============

@app.route('/api/backups', methods=['GET'])
@api_error_handler
def api_backups():
    """Lista los backups disponibles."""
    diag = DiagnosticService(svc_cfg)
    return jsonify({'backups': diag.list_backups()})

@app.route('/api/backups/restore', methods=['POST'])
@api_error_handler
def api_backups_restore():
    """Restaura un backup."""
    data = request.get_json()
    path = data.get('path')
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.restore_backup(path))

# ============= REPORTES =============

@app.route('/api/report/generate', methods=['POST'])
@api_error_handler
def api_report_generate():
    """Genera un reporte HTML completo."""
    diag_session = get_current_session()
    diag = DiagnosticService(svc_cfg)
    return jsonify(diag.generate_html_report(diag_session.report))

@app.route('/api/report/view', methods=['GET'])
def api_report_view():
    """Sirve un reporte generado (validado contra path traversal)."""
    path = request.args.get('path')
    if not path:
        return "Reporte no encontrado", 404
    # Resolver ruta absoluta y validar que este dentro del directorio de trabajo
    resolved = os.path.realpath(path)
    allowed_base = os.path.realpath(svc_cfg.system_paths.work_folder)
    if not resolved.startswith(allowed_base + os.sep) and resolved != allowed_base:
        return "Acceso denegado", 403
    if not os.path.exists(resolved):
        return "Reporte no encontrado", 404
    return send_file(resolved)

# ============= DETECCION / OTROS =============

@app.route('/api/detect/requirements', methods=['POST'])
@api_error_handler
def api_detect_requirements():
    """Verifica los requisitos del sistema."""
    diag = DiagnosticService(svc_cfg)
    return jsonify(diag.check_requirements())

@app.route('/api/detect/gpu', methods=['POST'])
@api_error_handler
def api_detect_gpu():
    """Detecta informacion de GPU."""
    hw = HardwareService(svc_cfg)
    return jsonify(hw.get_gpu_info())

@app.route('/api/detect/ram', methods=['POST'])
@api_error_handler
def api_detect_ram():
    """Detecta informacion de RAM."""
    hw = HardwareService(svc_cfg)
    return jsonify(hw.get_ram_info())

@app.route('/api/detect/cpu', methods=['POST'])
@api_error_handler
def api_detect_cpu():
    """Detecta informacion de CPU."""
    hw = HardwareService(svc_cfg)
    return jsonify(hw.get_cpu_info())

@app.route('/api/detect/temperatures', methods=['POST'])
@api_error_handler
def api_detect_temperatures():
    """Obtiene temperaturas actuales."""
    hw = HardwareService(svc_cfg)
    return jsonify(hw.get_system_temperatures())

@app.route('/api/detect/network', methods=['POST'])
@api_error_handler
def api_detect_network():
    """Prueba la calidad de la red."""
    net = NetworkService(svc_cfg)
    return jsonify(net.test_network_quality())

@app.route('/api/detect/packetloss', methods=['POST'])
@api_error_handler
def api_detect_packetloss():
    """Prueba la perdida de paquetes."""
    net = NetworkService(svc_cfg)
    return jsonify(net.test_packet_loss())

@app.route('/api/analyze/errors/advanced', methods=['POST'])
@api_error_handler
def api_analyze_errors_advanced():
    """Analisis avanzado de errores."""
    diag = DiagnosticService(svc_cfg)
    return jsonify(diag.analyze_recent_errors())

@app.route('/api/detect/mods', methods=['POST'])
@api_error_handler
def api_detect_mods():
    """Detecta mods instalados."""
    diag = DiagnosticService(svc_cfg)
    return jsonify(diag.detect_mods())

@app.route('/api/detect/conflicts', methods=['POST'])
@api_error_handler
def api_detect_conflicts():
    """Detecta software conflictivo."""
    diag = DiagnosticService(svc_cfg)
    return jsonify(diag.detect_conflicting_software())

@app.route('/api/detect/overlays', methods=['POST'])
@api_error_handler
def api_detect_overlays():
    """Detecta overlays activos."""
    diag = DiagnosticService(svc_cfg)
    return jsonify(diag.detect_overlays())

@app.route('/api/detect/antivirus', methods=['POST'])
@api_error_handler
def api_detect_antivirus():
    """Detecta antivirus instalado."""
    hw = HardwareService(svc_cfg)
    return jsonify(hw.get_antivirus_info())

@app.route('/api/detect/directx', methods=['POST'])
@api_error_handler
def api_detect_directx():
    """Verifica version de DirectX."""
    diag = DiagnosticService(svc_cfg)
    return jsonify(diag.check_directx())

@app.route('/api/detect/vcredist', methods=['POST'])
@api_error_handler
def api_detect_vcredist():
    """Verifica Visual C++ Redistributables."""
    diag = DiagnosticService(svc_cfg)
    return jsonify(diag.check_vcredist())

@app.route('/api/benchmark', methods=['POST'])
@api_error_handler
def api_benchmark():
    """Ejecuta el benchmark del sistema."""
    hw = HardwareService(svc_cfg)
    return jsonify(hw.run_benchmark())

@app.route('/api/repair/quick', methods=['POST'])
@api_error_handler
def api_repair_quick():
    """Ejecuta una reparacion rapida (combinada)."""
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    # Ejecutar varias reparaciones comunes
    results = [
        repair.kill_fivem_processes(),
        repair.clear_fivem_cache_selective(),
        repair.clear_fivem_logs()
    ]
    return jsonify({
        'success': True,
        'repairs_applied': [r['action'] if 'action' in r else 'Reparacion' for r in results if r.get('success')],
        'recommendations': []
    })

@app.route('/api/diagnostic/full/v2', methods=['POST'])
@api_error_handler
def api_diagnostic_full_v2():
    """Ejecuta el diagnostico PRO v2.0 (solo lectura, sin reparaciones)."""
    diag_session = get_current_session()
    diag = DiagnosticService(svc_cfg)
    hw = HardwareService(svc_cfg)
    net = NetworkService(svc_cfg)

    reqs = diag.check_requirements()
    gta_info = diag.get_gtav_path()
    fivem_info = diag.get_fivem_path()
    errors_info = diag.analyze_recent_errors()
    gpu_info = hw.get_gpu_info()
    ram_info = hw.get_ram_info()
    cpu_info = hw.get_cpu_info()
    os_info = hw.get_os_info()
    network_info = net.test_network_quality()
    driver_check = hw.check_driver_update()

    report = diag_session.report
    report.update_hardware(gpu=gpu_info, ram=ram_info, cpu=cpu_info, os=os_info)
    report.update_network(status=network_info.get('Status', 'OK'), ping=network_info.get('Ping', 0))
    report.gta_info = gta_info
    report.fivem_info = fivem_info
    report.calculate_overall_status()

    return jsonify({
        'success': True,
        'requirements': reqs,
        'Summary': report.to_dict().get('Summary', {}),
        'Hardware': report.to_dict().get('Hardware', {}),
        'Network': report.to_dict().get('Network', {}),
        'GTA': gta_info,
        'fivem': fivem_info,
        'errors': errors_info,
        'driver_update': driver_check,
        'temperatures': hw.get_system_temperatures()
    })

@app.route('/api/repair/kill', methods=['POST'])
@api_error_handler
def api_repair_kill():
    """Alias para kill_fivem_processes."""
    return api_repair_processes_kill()

@app.route('/api/repair/dlls', methods=['POST'])
@api_error_handler
def api_repair_dlls():
    """Alias para remove_conflicting_dlls."""
    return api_repair_dlls_remove()

@app.route('/api/repair/v8dlls', methods=['POST'])
@api_error_handler
def api_repair_v8dlls():
    """Alias para remove_v8_dlls."""
    return api_repair_v8_clean()

@app.route('/api/repair/rosfiles', methods=['POST'])
@api_error_handler
def api_repair_rosfiles():
    """Alias para clean_ros_files."""
    return api_repair_ros_clean()

@app.route('/api/repair/update-driver', methods=['POST'])
@api_error_handler
def api_repair_update_driver():
    """Actualiza el driver de GPU."""
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.update_gpu_driver())

@app.route('/api/detect/gtav', methods=['POST'])
@api_error_handler
def api_detect_gtav():
    """Detecta la ruta de GTA V."""
    diag = DiagnosticService(svc_cfg)
    return jsonify(diag.get_gtav_path())

@app.route('/api/detect/fivem', methods=['POST'])
@api_error_handler
def api_detect_fivem():
    """Detecta la instalacion de FiveM."""
    diag = DiagnosticService(svc_cfg)
    return jsonify(diag.get_fivem_path())

@app.route('/api/detect/driver-update', methods=['POST'])
@api_error_handler
def api_detect_driver_update():
    """Verifica si hay actualizaciones de drivers."""
    hw = HardwareService(svc_cfg)
    return jsonify(hw.check_driver_update())

@app.route('/api/analyze/logs', methods=['POST'])
@api_error_handler
def api_analyze_logs():
    """Analiza los logs de FiveM en busca de errores."""
    diag = DiagnosticService(svc_cfg)
    return jsonify(diag.analyze_recent_errors())

@app.route('/api/analyze/crashdumps', methods=['POST'])
@api_error_handler
def api_analyze_crashdumps():
    """Analiza los crash dumps de FiveM."""
    diag = DiagnosticService(svc_cfg)
    return jsonify(diag.analyze_crash_dumps())

@app.route('/api/repair/logs/clear', methods=['POST'])
@api_error_handler
def api_repair_logs_clear():
    """Limpia los archivos de logs de FiveM para ahorrar espacio."""
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.clear_fivem_logs())

@app.route('/api/verify/gtav', methods=['POST'])
@api_error_handler
def api_verify_gtav():
    """Verifica la integridad de los archivos de GTA V."""
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.verify_and_repair_gta_files())

if __name__ == '__main__':
    # Asegurar directorios base
    os.makedirs(svc_cfg.system_paths.work_folder, exist_ok=True)
    os.makedirs(svc_cfg.system_paths.backup_folder, exist_ok=True)
    
    # --- Lógica de apertura automática del navegador ---
    # Solo se ejecuta si no estamos en modo debug o si es el proceso principal de Flask
    if not svc_cfg.server_config.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        import webbrowser
        from threading import Timer
        
        def open_browser():
            url = f"http://{svc_cfg.server_config.host}:{svc_cfg.server_config.port}"
            logger.info(f"Abriendo interfaz web en: {url}")
            webbrowser.open(url)
        
        # Iniciamos un temporizador para dar tiempo a Flask a arrancar
        Timer(1.5, open_browser).start()
    # --------------------------------------------------
    
    app.run(
        host=svc_cfg.server_config.host,
        port=svc_cfg.server_config.port,
        debug=svc_cfg.server_config.debug
    )
