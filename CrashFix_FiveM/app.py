# -*- coding: utf-8 -*-
"""
FiveM Diagnostic & AUTO-REPAIR Tool v6.1 PRO - Web Version
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template, jsonify, request, send_file, session
from functools import wraps
import logging

import config as cfg
from config import (
    server_config,
    system_paths,
    diagnostic_config,
    error_patterns,
    texture_budget_config,
    timeout_config,
    network_config,
    SCRIPT_VERSION,
    get_timestamp,
    get_formatted_datetime,
    BACKUP_CATEGORIES
)

from src.services.session_manager import (
    SessionManager,
    get_session_manager,
    DiagnosticSession
)
from src.services.diagnostic_service import DiagnosticService
from src.services.repair_service import RepairService
from src.services.hardware_service import HardwareService
from src.services.network_service import NetworkService

from src.utils.logging_utils import setup_logging, get_logger
from src.utils.validation import validate_backup_path, validate_repair_ids
from src.utils.file_utils import ensure_directory_exists, get_folder_size

logger = setup_logging(system_paths.work_folder)

app = Flask(__name__)
app.secret_key = server_config.secret_key


# ============= MIDDLEWARE =============

@app.after_request
def add_security_headers(response):
    """Agrega cabeceras de seguridad a todas las respuestas."""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response


def get_current_session() -> DiagnosticSession:
    """Obtiene o crea la sesión de diagnóstico actual."""
    session_id = session.get('diagnostic_session_id')
    sm = get_session_manager()
    if session_id:
        diag_session = sm.get_session(session_id)
        if diag_session:
            return diag_session
    diag_session = sm.create_session()
    session['diagnostic_session_id'] = diag_session.session_id
    return diag_session


def api_error_handler(f):
    """Decorador para manejar errores en endpoints de la API."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValueError as e:
            logger.warning(f"Validation error in {f.__name__}: {e}")
            return jsonify({'error': 'Datos invalidos', 'details': str(e)}), 400
        except PermissionError as e:
            logger.error(f"Permission error in {f.__name__}: {e}")
            return jsonify({'error': 'Permisos insuficientes', 'details': str(e)}), 403
        except FileNotFoundError as e:
            logger.warning(f"File not found in {f.__name__}: {e}")
            return jsonify({'error': 'Recurso no encontrado', 'details': str(e)}), 404
        except Exception as e:
            logger.exception(f"Unexpected error in {f.__name__}: {e}")
            return jsonify({'error': 'Error interno', 'details': str(e)}), 500
    return decorated_function


# ============= CONTENEDOR DE CONFIG PARA SERVICIOS =============

class ServiceConfigContainer:
    """Contenedor de configuracion para servicios — evita colision con server_config."""
    def __init__(self):
        self.system_paths = system_paths
        self.diagnostic_config = diagnostic_config
        self.error_patterns = error_patterns
        self.texture_budget_config = texture_budget_config
        self.timeout_config = timeout_config
        self.network_config = network_config


svc_cfg = ServiceConfigContainer()


# ============= HELPERS DE DIAGNOSTICO =============

def _count_issues_from_diagnostics(report, errors_info, hardware_info, network_info,
                                   mods_info=None, conflicts_info=None):
    """
    Analiza los resultados de diagnostico y actualiza los contadores
    de problemas criticos y advertencias del reporte.
    """
    # Contar errores criticos y advertencias desde los errores de FiveM
    for err in errors_info.get('Errors', []):
        severity = err.get('Severity', 'medium')
        if severity == 'critical':
            report.increment_critical()
        elif severity in ('high', 'medium'):
            report.increment_warnings()

    # Verificar hardware
    gpu_data = hardware_info.get('GPU', hardware_info.get('gpu', []))
    if isinstance(gpu_data, list) and gpu_data:
        vram = gpu_data[0].get('VRAM_GB', 0)
        if vram > 0 and vram < 2:
            report.increment_critical()
            report.add_recommendation('VRAM insuficiente: se recomienda al menos 2 GB')
        elif vram > 0 and vram < 4:
            report.increment_warnings()
            report.add_recommendation('Se recomienda una GPU con al menos 4 GB de VRAM')

    ram_data = hardware_info.get('RAM', hardware_info.get('ram', {}))
    if isinstance(ram_data, dict):
        total_gb = ram_data.get('TotalGB', 0)
        if total_gb > 0 and total_gb < 8:
            report.increment_critical()
            report.add_recommendation('RAM insuficiente: se requieren al menos 8 GB')
        elif total_gb > 0 and total_gb < 16:
            report.increment_warnings()
            report.add_recommendation('Se recomienda 16 GB de RAM para FiveM')

    # Verificar red
    if isinstance(network_info, dict):
        ping = network_info.get('Ping', 0)
        status = network_info.get('Status', '')
        if status == 'Error':
            report.increment_critical()
            report.add_recommendation('No se pudo establecer conexion de red')
        elif ping > 100:
            report.increment_warnings()
            report.add_recommendation(f'Latencia alta ({ping}ms). Verifica tu conexion')

    # Verificar mods
    if mods_info and isinstance(mods_info, dict):
        mod_count = mods_info.get('Count', 0)
        if mod_count > 0:
            report.increment_warnings()
            report.add_recommendation('Desactiva los mods antes de jugar FiveM')

    # Verificar software conflictivo
    if conflicts_info and isinstance(conflicts_info, dict):
        conflict_count = conflicts_info.get('Count', len(conflicts_info.get('ConflictsFound', [])))
        if conflict_count > 0:
            report.increment_warnings()
            report.add_recommendation('Cierra el software conflictivo antes de jugar')


# ============= INICIALIZACION =============

def initialize_app():
    """Crea las carpetas de trabajo necesarias al iniciar la aplicacion."""
    folders = [system_paths.work_folder, system_paths.backup_folder]
    for category in BACKUP_CATEGORIES:
        folders.append(os.path.join(system_paths.backup_folder, category))
    for folder in folders:
        ensure_directory_exists(folder)
    logger.info(f"FiveM Diagnostic Tool v{SCRIPT_VERSION} inicializado")


# ============= RUTAS PRINCIPALES =============

@app.route('/')
def index():
    """Sirve la pagina principal."""
    return render_template('index.html')


@app.route('/api/status', methods=['GET'])
@api_error_handler
def api_status():
    """Devuelve el estado actual de la sesion."""
    diag_session = get_current_session()
    return jsonify({
        'status': 'Listo',
        'version': SCRIPT_VERSION,
        'session_id': diag_session.session_id,
        'report': diag_session.get_report_dict(),
        'repair_stats': diag_session.get_stats_dict()
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
    network_info = net.test_network_quality()
    errors_info = diag.analyze_fivem_errors()
    mods_info = diag.detect_gta_mods()
    conflicts_info = diag.detect_conflicting_software()
    antivirus_info = hw.get_antivirus_info()

    report = diag_session.report
    report.gta_info = gta_info
    report.hardware_info = {'GPU': gpu_info, 'RAM': ram_info, 'CPU': cpu_info}
    report.network_info = network_info
    report.errors_info = errors_info
    report.software_info = {
        'Mods': mods_info,
        'Conflicts': conflicts_info.get('ConflictsFound', []),
        'Antivirus': antivirus_info.get('Installed', [])
    }

    # Agregar recomendaciones de antivirus y errores
    for rec in antivirus_info.get('Recommendations', []):
        report.add_recommendation(rec)
    for rec in errors_info.get('Recommendations', []):
        report.add_recommendation(rec)

    # Contar problemas criticos y advertencias
    _count_issues_from_diagnostics(
        report, errors_info,
        {'GPU': gpu_info, 'RAM': ram_info},
        network_info, mods_info, conflicts_info
    )

    # GTA V no encontrado es critico
    if not gta_info.get('Path'):
        report.increment_critical()
        report.add_recommendation('GTA V no encontrado. Verifica la instalacion')

    report.calculate_overall_status()

    result = report.to_dict()
    result['gpu'] = gpu_info
    result['ram'] = ram_info
    result['cpu'] = cpu_info
    result['os'] = hw.get_os_info()
    result['gta'] = gta_info
    result['fivem'] = diag.get_fivem_status()
    result['network'] = network_info
    result['summary'] = result.get('Summary', {})
    return jsonify(result)


@app.route('/api/diagnostic/full/v2', methods=['POST'])
@api_error_handler
def api_diagnostic_full_v2():
    """Ejecuta el diagnostico PRO v2 con todas las fases."""
    diag_session = get_current_session()
    diag = DiagnosticService(svc_cfg)
    hw = HardwareService(svc_cfg)
    net = NetworkService(svc_cfg)

    phases = []

    phases.append({'name': 'Requisitos', 'status': 'completed'})
    hardware_info = hw.get_all_hardware_info()
    requirements = diag.check_system_requirements(hardware_info)

    phases.append({'name': 'GTA V', 'status': 'completed'})
    gta_info = diag.get_gtav_path()

    phases.append({'name': 'Hardware', 'status': 'completed'})

    phases.append({'name': 'Red', 'status': 'completed'})
    network_info = net.test_network_quality()

    phases.append({'name': 'Errores', 'status': 'completed'})
    errors_info = diag.analyze_fivem_errors()

    phases.append({'name': 'Mods', 'status': 'completed'})
    mods_info = diag.detect_gta_mods()

    phases.append({'name': 'Software', 'status': 'completed'})
    conflicts_info = diag.detect_conflicting_software()

    phases.append({'name': 'Antivirus', 'status': 'completed'})

    phases.append({'name': 'Verificaciones', 'status': 'completed'})
    directx_info = diag.check_directx()
    vcredist_info = diag.check_vcredist()

    phases.append({'name': 'Benchmark', 'status': 'completed'})
    benchmark = hw.run_benchmark()

    report = diag_session.report
    report.gta_info = gta_info
    report.hardware_info = hardware_info
    report.network_info = network_info
    report.errors_info = errors_info

    # Contar problemas criticos y advertencias
    _count_issues_from_diagnostics(
        report, errors_info, hardware_info,
        network_info, mods_info, conflicts_info
    )

    # GTA V no encontrado es critico
    if not gta_info.get('Path'):
        report.increment_critical()
        report.add_recommendation('GTA V no encontrado. Verifica la instalacion')

    # Agregar recomendaciones de requisitos
    for rec in requirements.get('recommendations', []):
        report.add_recommendation(rec)

    # Agregar recomendaciones de VC++ Redist
    for rec in vcredist_info.get('recommendations', []):
        report.add_recommendation(rec)

    report.calculate_overall_status()

    result = report.to_dict()
    result['gpu'] = hardware_info.get('gpu', [])
    result['ram'] = hardware_info.get('ram', {})
    result['cpu'] = hardware_info.get('cpu', {})
    result['os'] = hardware_info.get('os', {})
    result['gta'] = gta_info
    result['fivem'] = diag.get_fivem_status()
    result['network'] = network_info
    result['summary'] = result.get('Summary', {})

    return jsonify({
        **result,
        'phases': phases,
        'benchmark': benchmark,
        'requirements': requirements
    })


@app.route('/api/detect/gtav', methods=['POST'])
@api_error_handler
def api_detect_gtav():
    """Detecta la instalacion de GTA V."""
    diag = DiagnosticService(svc_cfg)
    return jsonify(diag.get_gtav_path())


@app.route('/api/detect/fivem', methods=['POST'])
@api_error_handler
def api_detect_fivem():
    """Detecta la instalacion de FiveM."""
    diag = DiagnosticService(svc_cfg)
    return jsonify(diag.get_fivem_status())


@app.route('/api/detect/gpu', methods=['POST'])
@api_error_handler
def api_detect_gpu():
    """Detecta informacion de la GPU."""
    hw = HardwareService(svc_cfg)
    return jsonify(hw.get_gpu_info())


@app.route('/api/detect/ram', methods=['POST'])
@api_error_handler
def api_detect_ram():
    """Detecta informacion de la RAM."""
    hw = HardwareService(svc_cfg)
    return jsonify(hw.get_ram_info())


@app.route('/api/detect/cpu', methods=['POST'])
@api_error_handler
def api_detect_cpu():
    """Detecta informacion de la CPU."""
    hw = HardwareService(svc_cfg)
    return jsonify(hw.get_cpu_info())


@app.route('/api/detect/network', methods=['POST'])
@api_error_handler
def api_detect_network():
    """Prueba la calidad de la conexion de red."""
    net = NetworkService(svc_cfg)
    return jsonify(net.test_network_quality())


@app.route('/api/detect/mods', methods=['POST'])
@api_error_handler
def api_detect_mods():
    """Detecta mods instalados en GTA V."""
    diag = DiagnosticService(svc_cfg)
    return jsonify(diag.detect_gta_mods())


@app.route('/api/detect/conflicts', methods=['POST'])
@api_error_handler
def api_detect_conflicts():
    """Detecta software conflictivo en ejecucion."""
    diag = DiagnosticService(svc_cfg)
    return jsonify(diag.detect_conflicting_software())


@app.route('/api/detect/overlays', methods=['POST'])
@api_error_handler
def api_detect_overlays():
    """Detecta overlays conflictivos en ejecucion."""
    diag = DiagnosticService(svc_cfg)
    return jsonify(diag.detect_conflicting_overlays())


@app.route('/api/detect/antivirus', methods=['POST'])
@api_error_handler
def api_detect_antivirus():
    """Detecta antivirus instalado."""
    hw = HardwareService(svc_cfg)
    return jsonify(hw.get_antivirus_info())


@app.route('/api/detect/requirements', methods=['POST'])
@api_error_handler
def api_detect_requirements():
    """Verifica los requisitos del sistema para FiveM."""
    diag = DiagnosticService(svc_cfg)
    hw = HardwareService(svc_cfg)
    hardware_info = hw.get_all_hardware_info()
    return jsonify(diag.check_system_requirements(hardware_info))


@app.route('/api/detect/temperatures', methods=['POST'])
@api_error_handler
def api_detect_temperatures():
    """Obtiene las temperaturas del sistema."""
    hw = HardwareService(svc_cfg)
    return jsonify(hw.get_system_temperatures())


@app.route('/api/detect/packetloss', methods=['POST'])
@api_error_handler
def api_detect_packetloss():
    """Prueba la perdida de paquetes de red."""
    net = NetworkService(svc_cfg)
    return jsonify(net.test_packet_loss())


@app.route('/api/detect/directx', methods=['POST'])
@api_error_handler
def api_detect_directx():
    """Verifica la version de DirectX."""
    diag = DiagnosticService(svc_cfg)
    return jsonify(diag.check_directx())


@app.route('/api/detect/vcredist', methods=['POST'])
@api_error_handler
def api_detect_vcredist():
    """Verifica las Visual C++ Redistributables instaladas."""
    diag = DiagnosticService(svc_cfg)
    return jsonify(diag.check_vcredist())


@app.route('/api/analyze/logs', methods=['POST'])
@api_error_handler
def api_analyze_logs():
    """Analiza los logs de FiveM."""
    diag = DiagnosticService(svc_cfg)
    return jsonify(diag.analyze_fivem_errors())


@app.route('/api/analyze/errors/advanced', methods=['POST'])
@api_error_handler
def api_analyze_errors_advanced():
    """Realiza un analisis avanzado de errores de FiveM."""
    diag = DiagnosticService(svc_cfg)
    errors = diag.analyze_fivem_errors()
    detailed_errors = []
    for err in errors.get('Errors', []):
        detailed_errors.append({
            'pattern': err['Error'],
            'description': err.get('Description', err['Error']),
            'severity': err['Severity'],
            'solutions': [err['Solution']]
        })
    return jsonify({
        'total_errors': len(detailed_errors),
        'critical': sum(1 for e in detailed_errors if e['severity'] == 'critical'),
        'high': sum(1 for e in detailed_errors if e['severity'] == 'high'),
        'medium': sum(1 for e in detailed_errors if e['severity'] == 'medium'),
        'errors_found': detailed_errors
    })


@app.route('/api/analyze/crashdumps', methods=['POST'])
@api_error_handler
def api_analyze_crashdumps():
    """Analiza los crash dumps de FiveM."""
    diag = DiagnosticService(svc_cfg)
    return jsonify(diag.analyze_crash_dumps())


@app.route('/api/verify/gtav', methods=['POST'])
@api_error_handler
def api_verify_gtav():
    """Verifica la integridad de los archivos de GTA V."""
    diag = DiagnosticService(svc_cfg)
    return jsonify(diag.verify_gtav_integrity())


# ============= DIAGNOSTICO INTELIGENTE =============

@app.route('/api/smart/diagnose-and-fix', methods=['POST'])
@api_error_handler
def api_smart_diagnose_and_fix():
    """
    Diagnostico inteligente unificado: analiza el estado del sistema y
    decide automaticamente que reparaciones aplicar.

    Combina la logica de diagnostico completo + reparacion rapida +
    diagnostico PRO v2 en un solo flujo inteligente, evitando procesos
    duplicados o innecesarios.

    Mantiene compatibilidad total: internamente reutiliza los mismos
    servicios y metodos que las acciones individuales.
    """
    diag_session = get_current_session()
    diag = DiagnosticService(svc_cfg)
    hw = HardwareService(svc_cfg)
    net = NetworkService(svc_cfg)
    repair = RepairService(svc_cfg, diag_session)

    phases = []
    auto_repairs = []

    # --- Fase 1: Hardware ---
    phases.append({'name': 'Hardware', 'status': 'running'})
    hardware_info = hw.get_all_hardware_info()
    gpu_info = hardware_info.get('gpu', [])
    ram_info = hardware_info.get('ram', {})
    cpu_info = hardware_info.get('cpu', {})
    os_info = hardware_info.get('os', {})
    phases[-1]['status'] = 'completed'

    # --- Fase 2: Requisitos ---
    phases.append({'name': 'Requisitos', 'status': 'running'})
    requirements = diag.check_system_requirements(hardware_info)
    phases[-1]['status'] = 'completed'

    # --- Fase 3: GTA V y FiveM ---
    phases.append({'name': 'GTA V / FiveM', 'status': 'running'})
    gta_info = diag.get_gtav_path()
    fivem_info = diag.get_fivem_status()
    phases[-1]['status'] = 'completed'

    # --- Fase 4: Red ---
    phases.append({'name': 'Red', 'status': 'running'})
    network_info = net.test_network_quality()
    phases[-1]['status'] = 'completed'

    # --- Fase 5: Errores y Logs ---
    phases.append({'name': 'Errores', 'status': 'running'})
    errors_info = diag.analyze_fivem_errors()
    phases[-1]['status'] = 'completed'

    # --- Fase 6: Mods y Software ---
    phases.append({'name': 'Mods y Software', 'status': 'running'})
    mods_info = diag.detect_gta_mods()
    conflicts_info = diag.detect_conflicting_software()
    phases[-1]['status'] = 'completed'

    # --- Fase 7: Verificaciones ---
    phases.append({'name': 'Verificaciones', 'status': 'running'})
    directx_info = diag.check_directx()
    vcredist_info = diag.check_vcredist()
    antivirus_info = hardware_info.get('antivirus', hw.get_antivirus_info())
    phases[-1]['status'] = 'completed'

    # --- Construir reporte ---
    report = diag_session.report
    report.reset_counters()
    report.gta_info = gta_info
    report.fivem_info = fivem_info
    report.hardware_info = hardware_info
    report.network_info = network_info
    report.errors_info = errors_info
    report.software_info = {
        'Mods': mods_info,
        'Conflicts': conflicts_info.get('ConflictsFound', []),
        'Antivirus': antivirus_info.get('Installed', []) if isinstance(antivirus_info, dict) else []
    }

    # Contar problemas
    _count_issues_from_diagnostics(
        report, errors_info, hardware_info,
        network_info, mods_info, conflicts_info
    )

    if not gta_info.get('Path'):
        report.increment_critical()
        report.add_recommendation('GTA V no encontrado. Verifica la instalacion')

    for rec in requirements.get('recommendations', []):
        report.add_recommendation(rec)
    for rec in vcredist_info.get('recommendations', []):
        report.add_recommendation(rec)
    for rec in errors_info.get('Recommendations', []):
        report.add_recommendation(rec)
    if isinstance(antivirus_info, dict):
        for rec in antivirus_info.get('Recommendations', []):
            report.add_recommendation(rec)

    # --- Fase 8: Reparaciones automaticas inteligentes ---
    phases.append({'name': 'Reparacion Automatica', 'status': 'running'})

    # Siempre: terminar procesos de FiveM para evitar conflictos
    kill_result = repair.kill_fivem_processes()
    auto_repairs.append({'action': 'Terminar procesos FiveM', 'result': kill_result, 'reason': 'Prevencion de conflictos'})

    # Si hay errores criticos en logs: limpiar cache selectiva
    critical_errors = [e for e in errors_info.get('Errors', []) if e.get('Severity') == 'critical']
    if critical_errors:
        cache_result = repair.clear_fivem_cache_selective()
        auto_repairs.append({'action': 'Limpiar cache selectiva', 'result': cache_result, 'reason': f'{len(critical_errors)} errores criticos detectados'})

    # Si hay DLLs conflictivas potenciales (Entry Point Not Found)
    entry_point_errors = [e for e in errors_info.get('Errors', []) if 'Entry Point' in e.get('Error', '')]
    if entry_point_errors:
        dll_result = repair.remove_conflicting_dlls()
        auto_repairs.append({'action': 'Eliminar DLLs conflictivas', 'result': dll_result, 'reason': 'Error Entry Point Not Found detectado'})

    # Si hay mods detectados
    if mods_info.get('Count', 0) > 0:
        report.add_recommendation(f'Se detectaron {mods_info["Count"]} mods. Considera desactivarlos si tienes problemas.')

    # Si hay software conflictivo
    if conflicts_info.get('Count', 0) > 0:
        report.add_recommendation(f'Software conflictivo detectado: {", ".join(conflicts_info.get("ConflictsFound", []))}')

    # Verificar si el driver de GPU esta desactualizado
    driver_check = hw.check_driver_update()
    if driver_check.get('needs_update'):
        vendor = driver_check.get('vendor', '').upper()
        current = driver_check.get('current_driver', 'N/A')
        latest = driver_check.get('latest_driver', 'N/A')
        if latest and latest != 'None':
            report.add_recommendation(f'Driver {vendor} desactualizado: {current} -> Actualizar a {latest}')
        else:
            age = driver_check.get('driver_age_months', '')
            age_text = f' ({age} meses de antiguedad)' if age else ''
            report.add_recommendation(f'Driver {vendor} desactualizado{age_text}. Actualiza desde el panel de reparacion.')

    phases[-1]['status'] = 'completed'

    report.calculate_overall_status()

    result = report.to_dict()
    result['gpu'] = gpu_info
    result['ram'] = ram_info
    result['cpu'] = cpu_info
    result['os'] = os_info
    result['gta'] = gta_info
    result['fivem'] = fivem_info
    result['summary'] = result.get('Summary', {})

    return jsonify({
        **result,
        'phases': phases,
        'auto_repairs': auto_repairs,
        'requirements': requirements,
        'directx': directx_info,
        'vcredist': vcredist_info,
        'network': network_info,
        'mods': mods_info,
        'conflicts': conflicts_info,
        'driver_status': driver_check
    })


# ============= REPARACION =============

@app.route('/api/repair/quick', methods=['POST'])
@api_error_handler
def api_repair_quick():
    """Ejecuta una reparacion rapida (terminar procesos + limpiar cache + eliminar DLLs)."""
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    repairs_applied = []

    repair.kill_fivem_processes()
    repairs_applied.append('Procesos terminados')

    cache_result = repair.clear_fivem_cache_selective()
    if cache_result.get('cleaned_mb', 0) > 0:
        repairs_applied.append(f"Cache limpiada ({cache_result['cleaned_mb']} MB)")

    dll_result = repair.remove_conflicting_dlls()
    if dll_result.get('removed'):
        repairs_applied.append('DLLs eliminadas')

    return jsonify({
        'success': True,
        'repairs_applied': repairs_applied,
        'stats': diag_session.get_stats_dict(),
        'recommendations': diag_session.report.recommendations
    })


@app.route('/api/repair/kill', methods=['POST'])
@api_error_handler
def api_repair_kill():
    """Termina todos los procesos de FiveM."""
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.kill_fivem_processes())


@app.route('/api/repair/cache/selective', methods=['POST'])
@api_error_handler
def api_repair_cache_selective():
    """Limpia la cache de FiveM de forma selectiva."""
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


@app.route('/api/repair/dlls', methods=['POST'])
@api_error_handler
def api_repair_dlls():
    """Elimina DLLs conflictivas del sistema."""
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.remove_conflicting_dlls())


@app.route('/api/repair/v8dlls', methods=['POST'])
@api_error_handler
def api_repair_v8dlls():
    """Elimina especificamente las v8 DLLs conflictivas de System32."""
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.remove_v8_dlls())


@app.route('/api/repair/ros', methods=['POST'])
@api_error_handler
def api_repair_ros():
    """Repara la autenticacion de Rockstar Online Services."""
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.repair_ros_authentication())


@app.route('/api/repair/rosfiles', methods=['POST'])
@api_error_handler
def api_repair_rosfiles():
    """Limpia los archivos de Rockstar Online Services."""
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.clean_ros_files())


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
    """Cierra el software conflictivo detectado."""
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.close_conflicting_software())


@app.route('/api/repair/advanced', methods=['POST'])
@api_error_handler
def api_repair_advanced():
    """Ejecuta reparaciones avanzadas seleccionadas por el usuario."""
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)

    data = request.get_json() or {}
    repairs = data.get('repairs', [])
    valid_repairs = validate_repair_ids(repairs)

    if not valid_repairs:
        return jsonify({
            'success': False,
            'error': 'No se seleccionaron reparaciones validas',
            'results': []
        })

    return jsonify(repair.run_advanced_repair(valid_repairs))


# ============= OPTIMIZACION =============

@app.route('/api/optimize/firewall', methods=['POST'])
@api_error_handler
def api_optimize_firewall():
    """Configura reglas de firewall para FiveM."""
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.add_firewall_exclusions())


@app.route('/api/optimize/defender', methods=['POST'])
@api_error_handler
def api_optimize_defender():
    """Configura exclusiones de Windows Defender para FiveM."""
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.add_defender_exclusions())


@app.route('/api/optimize/pagefile', methods=['POST'])
@api_error_handler
def api_optimize_pagefile():
    """Optimiza la configuracion del archivo de paginacion."""
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.optimize_page_file())


@app.route('/api/optimize/graphics', methods=['POST'])
@api_error_handler
def api_optimize_graphics():
    """Optimiza la configuracion grafica de GTA V."""
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.optimize_graphics_config())


@app.route('/api/optimize/texturebudget', methods=['POST'])
@api_error_handler
def api_optimize_texturebudget():
    """Configura el Texture Budget basado en la VRAM detectada."""
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.configure_texture_budget())


@app.route('/api/optimize/windows', methods=['POST'])
@api_error_handler
def api_optimize_windows():
    """Aplica optimizaciones de Windows para gaming."""
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.optimize_windows())


@app.route('/api/detect/driver-update', methods=['POST'])
@api_error_handler
def api_detect_driver_update():
    """Verifica si el driver de GPU esta desactualizado."""
    hw = HardwareService(svc_cfg)
    return jsonify(hw.check_driver_update())


@app.route('/api/repair/update-driver', methods=['POST'])
@api_error_handler
def api_repair_update_driver():
    """Descarga e instala el driver mas reciente de GPU."""
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.update_gpu_driver())


@app.route('/api/optimize/dns', methods=['POST'])
@api_error_handler
def api_optimize_dns():
    """Analiza y recomienda el mejor DNS."""
    net = NetworkService(svc_cfg)
    return jsonify(net.optimize_dns())


@app.route('/api/benchmark', methods=['POST'])
@api_error_handler
def api_benchmark():
    """Ejecuta un benchmark del sistema."""
    hw = HardwareService(svc_cfg)
    return jsonify(hw.run_benchmark())


# ============= CONFIGURACION =============

@app.route('/api/config/citizenfx', methods=['GET'])
@api_error_handler
def api_config_citizenfx_get():
    """Obtiene la configuracion actual de CitizenFX.ini."""
    diag = DiagnosticService(svc_cfg)
    return jsonify(diag.get_citizenfx_config())


@app.route('/api/config/citizenfx', methods=['POST'])
@api_error_handler
def api_config_citizenfx_post():
    """Guarda la configuracion de CitizenFX.ini.

    Formato correcto segun docs.fivem.net:
        [Game]
        IVPath=...
        SavedBuildNumber=...
        UpdateChannel=...
    
    Preserva IVPath existente y solo modifica las claves enviadas.
    """
    diag_session = get_current_session()
    data = request.get_json() or {}

    # Leer configuracion actual para preservar IVPath y otras claves
    diag = DiagnosticService(svc_cfg)
    current_config = diag.get_citizenfx_config()

    # Determinar ruta del archivo (usar la existente o la principal)
    ini_path = current_config.get('_path', '') or system_paths.fivem_paths.get('CitizenFXIni', '')

    if not ini_path:
        return jsonify({'success': False, 'error': 'Ruta de CitizenFX.ini no configurada'})

    # Mapear claves del frontend a claves reales de CitizenFX.ini
    key_mapping = {
        'GameBuild': 'SavedBuildNumber',       # Frontend usa GameBuild, archivo usa SavedBuildNumber
        'SavedBuildNumber': 'SavedBuildNumber',
        'UpdateChannel': 'UpdateChannel',
        'DisableNVSP': 'DisableNVSP',
        'EnableFullMemoryDump': 'EnableFullMemoryDump',
        'DisableOSVersionCheck': 'DisableOSVersionCheck',
        'DisableCrashUpload': 'DisableCrashUpload'
    }

    # Construir configuracion final: base actual + cambios del usuario
    final_config = {}

    # Preservar IVPath si existe
    if current_config.get('IVPath'):
        final_config['IVPath'] = current_config['IVPath']

    # Aplicar valores actuales como base
    for key in ['SavedBuildNumber', 'UpdateChannel', 'DisableNVSP',
                 'EnableFullMemoryDump', 'DisableOSVersionCheck', 'DisableCrashUpload']:
        if current_config.get(key):
            final_config[key] = current_config[key]

    # Aplicar cambios del usuario (con mapeo de claves)
    for frontend_key, value in data.items():
        if frontend_key.startswith('_'):
            continue  # Ignorar claves internas
        real_key = key_mapping.get(frontend_key, frontend_key)
        final_config[real_key] = str(value)

    # Hacer backup del archivo actual si existe
    if os.path.exists(ini_path):
        try:
            from src.utils.file_utils import backup_item
            backup_item(ini_path, 'CitizenFX.ini', system_paths.backup_folder, 'Config')
        except Exception as e:
            logger.warning(f"Error backing up CitizenFX.ini: {e}")

    ensure_directory_exists(os.path.dirname(ini_path))
    try:
        with open(ini_path, 'w', encoding='utf-8') as f:
            f.write('[Game]\n')
            for key, value in final_config.items():
                if value:  # No escribir claves vacias
                    f.write(f'{key}={value}\n')
        diag_session.report.add_repair_applied('CitizenFX.ini configurado')
        logger.info(f"CitizenFX.ini saved to {ini_path} with keys: {list(final_config.keys())}")
        return jsonify({'success': True, 'path': ini_path, 'config': final_config})
    except Exception as e:
        logger.error(f"Error writing CitizenFX.ini: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/config/launchparams', methods=['GET'])
@api_error_handler
def api_config_launchparams_get():
    """Obtiene los parametros de lanzamiento disponibles."""
    return jsonify({
        'parameters': [],
        'available': [
            {'param': '-novid', 'description': 'Omite video de introduccion'},
            {'param': '-threads 4', 'description': 'Usa 4 hilos de CPU'},
            {'param': '-memleakfix', 'description': 'Corrige fugas de memoria'},
            {'param': '-high', 'description': 'Prioridad alta de proceso'}
        ]
    })


@app.route('/api/config/launchparams', methods=['POST'])
@api_error_handler
def api_config_launchparams_post():
    """Guarda los parametros de lanzamiento seleccionados."""
    diag_session = get_current_session()
    data = request.get_json() or {}
    parameters = data.get('parameters', [])
    config_path = os.path.join(system_paths.work_folder, 'launch_params.txt')
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(' '.join(parameters))
        diag_session.report.add_repair_applied('Parametros de lanzamiento configurados')
        diag_session.report.add_recommendation(
            f'Agrega al acceso directo: {" ".join(parameters)}'
        )
        return jsonify({'success': True, 'parameters': parameters})
    except Exception as e:
        logger.error(f"Error writing launch params: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/config/export', methods=['POST'])
@api_error_handler
def api_config_export():
    """Exporta la configuracion actual a un archivo JSON."""
    import json
    diag_session = get_current_session()
    diag = DiagnosticService(svc_cfg)
    config = {
        'version': SCRIPT_VERSION,
        'timestamp': get_formatted_datetime(),
        'citizenfx': diag.get_citizenfx_config(),
        'report': diag_session.get_report_dict()
    }
    export_path = os.path.join(
        system_paths.work_folder, f'FiveM_Config_{get_timestamp()}.json'
    )
    try:
        with open(export_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return jsonify({'success': True, 'path': export_path})
    except Exception as e:
        logger.error(f"Error exporting config: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/profiles/apply', methods=['POST'])
@api_error_handler
def api_profiles_apply():
    """Aplica un perfil de rendimiento predefinido."""
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    data = request.get_json() or {}
    profile = data.get('profile', 'medium')
    valid_profiles = {'potato', 'low', 'medium', 'high', 'ultra'}
    if profile not in valid_profiles:
        return jsonify({'success': False, 'error': 'Perfil no valido'})
    repair.optimize_graphics_config()
    diag_session.report.add_repair_applied(f'Perfil {profile} aplicado')
    return jsonify({'success': True, 'profile': profile})


# ============= BACKUPS =============

@app.route('/api/backups', methods=['GET'])
@api_error_handler
def api_backups():
    """Lista todos los backups disponibles."""
    from datetime import datetime
    backups = []
    backup_folder = system_paths.backup_folder
    if not os.path.exists(backup_folder):
        return jsonify({'backups': []})
    for category in os.listdir(backup_folder):
        category_path = os.path.join(backup_folder, category)
        if os.path.isdir(category_path):
            for item in os.listdir(category_path):
                item_path = os.path.join(category_path, item)
                try:
                    size = (get_folder_size(item_path)
                            if os.path.isdir(item_path)
                            else os.path.getsize(item_path))
                    mtime = os.path.getmtime(item_path)
                    backups.append({
                        'name': item,
                        'category': category,
                        'path': item_path,
                        'size_mb': round(size / (1024 * 1024), 2),
                        'date': datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
                    })
                except (OSError, IOError):
                    pass
    backups.sort(key=lambda x: x['date'], reverse=True)
    return jsonify({'backups': backups})


@app.route('/api/backups/restore', methods=['POST'])
@api_error_handler
def api_backups_restore():
    """Restaura un backup seleccionado."""
    import shutil
    diag_session = get_current_session()
    data = request.get_json() or {}
    backup_path = data.get('path', '')

    if not validate_backup_path(backup_path, system_paths.backup_folder):
        logger.warning(f"Invalid restore path attempt: {backup_path}")
        return jsonify({'success': False, 'error': 'Ruta de backup no valida'}), 400

    if not os.path.exists(backup_path):
        return jsonify({'success': False, 'error': 'Backup no encontrado'}), 404

    backup_name = os.path.basename(backup_path)
    destination = None
    if 'Cache' in backup_name:
        destination = system_paths.fivem_paths.get('Cache', '')
    elif 'CitizenFX' in backup_name:
        destination = system_paths.fivem_paths.get('CitizenFXIni', '')
    else:
        return jsonify({
            'success': False,
            'error': 'No se puede determinar el destino del backup'
        })

    if not destination:
        return jsonify({'success': False, 'error': 'Ruta de destino no configurada'})

    try:
        if os.path.exists(destination):
            if os.path.isdir(destination):
                shutil.rmtree(destination)
            else:
                os.remove(destination)
        if os.path.isdir(backup_path):
            shutil.copytree(backup_path, destination)
        else:
            shutil.copy2(backup_path, destination)
        diag_session.report.add_repair_applied('Backup restaurado')
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error restoring backup: {e}")
        return jsonify({'success': False, 'error': str(e)})


# ============= REPORTES =============

@app.route('/api/report/generate', methods=['POST'])
@api_error_handler
def api_report_generate():
    """Genera un reporte HTML del diagnostico."""
    diag_session = get_current_session()
    report = diag_session.report

    html = f'''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>FiveM Diagnostic Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; background: #1a1a2e; color: #fff; padding: 20px; }}
        .section {{ background: #16213e; padding: 20px; margin: 10px 0; border-radius: 8px; }}
        .success {{ color: #10b981; }}
        .warning {{ color: #f59e0b; }}
        .error {{ color: #ef4444; }}
        h1 {{ color: #7c3aed; }}
        h2 {{ color: #3b82f6; border-bottom: 1px solid #2d3748; padding-bottom: 10px; }}
    </style>
</head>
<body>
    <h1>FiveM Diagnostic Report</h1>
    <p>Generado: {get_formatted_datetime()}</p>
    <p>Version: {SCRIPT_VERSION}</p>
    <div class="section">
        <h2>Estado General: {report.overall_status}</h2>
        <p>Problemas Criticos: <span class="error">{report.critical_issues}</span></p>
        <p>Advertencias: <span class="warning">{report.warnings}</span></p>
    </div>
    <div class="section">
        <h2>Reparaciones Aplicadas</h2>
        {''.join(f'<p class="success">&#10003; {r}</p>' for r in report.repairs_applied) or '<p>Ninguna</p>'}
    </div>
    <div class="section">
        <h2>Recomendaciones</h2>
        {''.join(f'<p>&rarr; {r}</p>' for r in report.recommendations) or '<p>Ninguna</p>'}
    </div>
</body>
</html>'''

    report_path = os.path.join(
        system_paths.work_folder, f'FiveM_Report_{get_timestamp()}.html'
    )
    try:
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html)
        return jsonify({'success': True, 'path': report_path})
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/report/view')
@api_error_handler
def api_report_view():
    """
    Sirve un reporte HTML generado previamente.
    Acepta un parametro ?path= opcional. Si no se proporciona,
    devuelve el reporte mas reciente.
    """
    import glob

    requested_path = request.args.get('path', '').strip()

    if requested_path:
        if not validate_backup_path(requested_path, system_paths.work_folder):
            return jsonify({'error': 'Ruta no permitida'}), 400
        if os.path.exists(requested_path) and requested_path.endswith('.html'):
            return send_file(requested_path)

    pattern = os.path.join(system_paths.work_folder, 'FiveM_Report_*.html')
    reports = glob.glob(pattern)
    if not reports:
        return jsonify({'error': 'No hay reportes disponibles'}), 404

    latest_report = max(reports, key=os.path.getmtime)
    return send_file(latest_report)


# ============= PUNTO DE ENTRADA =============

if __name__ == '__main__':
    initialize_app()
    print("=" * 50)
    print(f"  {SCRIPT_VERSION}")
    print("  FiveM Diagnostic & AUTO-REPAIR Tool")
    print("=" * 50)
    print(f"[INFO] Carpeta de trabajo: {system_paths.work_folder}")
    print(f"[INFO] Servidor: http://{server_config.host}:{server_config.port}")
    print(f"[INFO] Debug: {server_config.debug}")
    print()
    app.run(
        host=server_config.host,
        port=server_config.port,
        debug=server_config.debug
    )
