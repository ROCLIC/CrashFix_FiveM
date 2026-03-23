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
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response


def get_current_session() -> DiagnosticSession:
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
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValueError as e:
            logger.warning(f"Validation error in {f.__name__}: {e}")
            return jsonify({'error': 'Datos inválidos', 'details': str(e)}), 400
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
# FIX: Renombrado de 'service_config' a 'svc_cfg' para evitar colisión con server_config

class ServiceConfigContainer:
    """Contenedor de configuración para servicios — evita colisión con server_config."""
    def __init__(self):
        self.system_paths = system_paths
        self.diagnostic_config = diagnostic_config
        self.error_patterns = error_patterns
        self.texture_budget_config = texture_budget_config
        self.timeout_config = timeout_config
        self.network_config = network_config


svc_cfg = ServiceConfigContainer()


# ============= INICIALIZACIÓN =============

def initialize_app():
    folders = [system_paths.work_folder, system_paths.backup_folder]
    for category in BACKUP_CATEGORIES:
        folders.append(os.path.join(system_paths.backup_folder, category))
    for folder in folders:
        ensure_directory_exists(folder)
    logger.info(f"FiveM Diagnostic Tool v{SCRIPT_VERSION} inicializado")


# ============= RUTAS PRINCIPALES =============

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/status', methods=['GET'])
@api_error_handler
def api_status():
    diag_session = get_current_session()
    return jsonify({
        'status': 'Listo',
        'version': SCRIPT_VERSION,
        'session_id': diag_session.session_id,
        'report': diag_session.get_report_dict(),
        'repair_stats': diag_session.get_stats_dict()
    })


# ============= DIAGNÓSTICO =============

@app.route('/api/diagnostic/complete', methods=['POST'])
@api_error_handler
def api_diagnostic_complete():
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

    for rec in antivirus_info.get('Recommendations', []):
        report.add_recommendation(rec)
    for rec in errors_info.get('Recommendations', []):
        report.add_recommendation(rec)

    report.calculate_overall_status()

    # FIX: Devolver estructura plana que el frontend puede consumir directamente
    result = report.to_dict()
    result['gpu'] = gpu_info
    result['ram'] = ram_info
    result['cpu'] = cpu_info
    result['summary'] = result.get('Summary', {})
    return jsonify(result)


@app.route('/api/diagnostic/full/v2', methods=['POST'])
@api_error_handler
def api_diagnostic_full_v2():
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
    report.calculate_overall_status()

    result = report.to_dict()
    # FIX: Añadir alias para que el frontend pueda leerlos
    result['gpu'] = hardware_info.get('gpu', [])
    result['ram'] = hardware_info.get('ram', {})
    result['cpu'] = hardware_info.get('cpu', {})
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
    diag = DiagnosticService(svc_cfg)
    return jsonify(diag.get_gtav_path())


@app.route('/api/detect/fivem', methods=['POST'])
@api_error_handler
def api_detect_fivem():
    diag = DiagnosticService(svc_cfg)
    return jsonify(diag.get_fivem_status())


@app.route('/api/detect/gpu', methods=['POST'])
@api_error_handler
def api_detect_gpu():
    hw = HardwareService(svc_cfg)
    return jsonify(hw.get_gpu_info())


@app.route('/api/detect/ram', methods=['POST'])
@api_error_handler
def api_detect_ram():
    hw = HardwareService(svc_cfg)
    return jsonify(hw.get_ram_info())


@app.route('/api/detect/cpu', methods=['POST'])
@api_error_handler
def api_detect_cpu():
    hw = HardwareService(svc_cfg)
    return jsonify(hw.get_cpu_info())


@app.route('/api/detect/network', methods=['POST'])
@api_error_handler
def api_detect_network():
    net = NetworkService(svc_cfg)
    return jsonify(net.test_network_quality())


@app.route('/api/detect/mods', methods=['POST'])
@api_error_handler
def api_detect_mods():
    diag = DiagnosticService(svc_cfg)
    return jsonify(diag.detect_gta_mods())


@app.route('/api/detect/conflicts', methods=['POST'])
@api_error_handler
def api_detect_conflicts():
    diag = DiagnosticService(svc_cfg)
    return jsonify(diag.detect_conflicting_software())


@app.route('/api/detect/overlays', methods=['POST'])
@api_error_handler
def api_detect_overlays():
    diag = DiagnosticService(svc_cfg)
    return jsonify(diag.detect_conflicting_overlays())


@app.route('/api/detect/antivirus', methods=['POST'])
@api_error_handler
def api_detect_antivirus():
    hw = HardwareService(svc_cfg)
    return jsonify(hw.get_antivirus_info())


@app.route('/api/detect/requirements', methods=['POST'])
@api_error_handler
def api_detect_requirements():
    diag = DiagnosticService(svc_cfg)
    hw = HardwareService(svc_cfg)
    hardware_info = hw.get_all_hardware_info()
    return jsonify(diag.check_system_requirements(hardware_info))


@app.route('/api/detect/temperatures', methods=['POST'])
@api_error_handler
def api_detect_temperatures():
    hw = HardwareService(svc_cfg)
    return jsonify(hw.get_system_temperatures())


@app.route('/api/detect/packetloss', methods=['POST'])
@api_error_handler
def api_detect_packetloss():
    net = NetworkService(svc_cfg)
    return jsonify(net.test_packet_loss())


@app.route('/api/detect/directx', methods=['POST'])
@api_error_handler
def api_detect_directx():
    diag = DiagnosticService(svc_cfg)
    return jsonify(diag.check_directx())


@app.route('/api/detect/vcredist', methods=['POST'])
@api_error_handler
def api_detect_vcredist():
    diag = DiagnosticService(svc_cfg)
    return jsonify(diag.check_vcredist())


@app.route('/api/analyze/logs', methods=['POST'])
@api_error_handler
def api_analyze_logs():
    diag = DiagnosticService(svc_cfg)
    return jsonify(diag.analyze_fivem_errors())


@app.route('/api/analyze/errors/advanced', methods=['POST'])
@api_error_handler
def api_analyze_errors_advanced():
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
    diag = DiagnosticService(svc_cfg)
    return jsonify(diag.analyze_crash_dumps())


@app.route('/api/verify/gtav', methods=['POST'])
@api_error_handler
def api_verify_gtav():
    diag = DiagnosticService(svc_cfg)
    return jsonify(diag.verify_gtav_integrity())


# ============= REPARACIÓN =============

@app.route('/api/repair/quick', methods=['POST'])
@api_error_handler
def api_repair_quick():
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    repairs_applied = []

    repair.kill_fivem_processes()
    repairs_applied.append('Procesos terminados')

    cache_result = repair.clear_fivem_cache_selective()
    if cache_result.get('cleaned_mb', 0) > 0:
        repairs_applied.append(f"Caché limpiada ({cache_result['cleaned_mb']} MB)")

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
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.kill_fivem_processes())


@app.route('/api/repair/cache/selective', methods=['POST'])
@api_error_handler
def api_repair_cache_selective():
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.clear_fivem_cache_selective())


@app.route('/api/repair/cache/complete', methods=['POST'])
@api_error_handler
def api_repair_cache_complete():
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.clear_fivem_cache_complete())


@app.route('/api/repair/dlls', methods=['POST'])
@api_error_handler
def api_repair_dlls():
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.remove_conflicting_dlls())


@app.route('/api/repair/v8dlls', methods=['POST'])
@api_error_handler
def api_repair_v8dlls():
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.remove_conflicting_dlls())


@app.route('/api/repair/ros', methods=['POST'])
@api_error_handler
def api_repair_ros():
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.repair_ros_authentication())


@app.route('/api/repair/rosfiles', methods=['POST'])
@api_error_handler
def api_repair_rosfiles():
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.repair_ros_authentication())


@app.route('/api/repair/mods/disable', methods=['POST'])
@api_error_handler
def api_repair_mods_disable():
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.disable_gta_mods())


@app.route('/api/repair/conflicts/close', methods=['POST'])
@api_error_handler
def api_repair_conflicts_close():
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.close_conflicting_software())


@app.route('/api/repair/advanced', methods=['POST'])
@api_error_handler
def api_repair_advanced():
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)

    data = request.get_json() or {}
    repairs = data.get('repairs', [])
    valid_repairs = validate_repair_ids(repairs)

    if not valid_repairs:
        return jsonify({
            'success': False,
            'error': 'No se seleccionaron reparaciones válidas',
            'results': []
        })

    return jsonify(repair.run_advanced_repair(valid_repairs))


# ============= OPTIMIZACIÓN =============

@app.route('/api/optimize/firewall', methods=['POST'])
@api_error_handler
def api_optimize_firewall():
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.add_firewall_exclusions())


@app.route('/api/optimize/defender', methods=['POST'])
@api_error_handler
def api_optimize_defender():
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair.add_defender_exclusions())


@app.route('/api/optimize/pagefile', methods=['POST'])
@api_error_handler
def api_optimize_pagefile():
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair._optimize_page_file())


@app.route('/api/optimize/graphics', methods=['POST'])
@api_error_handler
def api_optimize_graphics():
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair._optimize_graphics_config())


@app.route('/api/optimize/texturebudget', methods=['POST'])
@api_error_handler
def api_optimize_texturebudget():
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair._configure_texture_budget())


@app.route('/api/optimize/windows', methods=['POST'])
@api_error_handler
def api_optimize_windows():
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    return jsonify(repair._optimize_windows())


@app.route('/api/optimize/dns', methods=['POST'])
@api_error_handler
def api_optimize_dns():
    net = NetworkService(svc_cfg)
    return jsonify(net.optimize_dns())


@app.route('/api/benchmark', methods=['POST'])
@api_error_handler
def api_benchmark():
    hw = HardwareService(svc_cfg)
    return jsonify(hw.run_benchmark())


# ============= CONFIGURACIÓN =============

@app.route('/api/config/citizenfx', methods=['GET'])
@api_error_handler
def api_config_citizenfx_get():
    diag = DiagnosticService(svc_cfg)
    return jsonify(diag.get_citizenfx_config())


@app.route('/api/config/citizenfx', methods=['POST'])
@api_error_handler
def api_config_citizenfx_post():
    diag_session = get_current_session()
    data = request.get_json() or {}
    ini_path = system_paths.fivem_paths.get('CitizenFXIni', '')
    ensure_directory_exists(os.path.dirname(ini_path))
    try:
        with open(ini_path, 'w', encoding='utf-8') as f:
            for key, value in data.items():
                f.write(f'{key}={value}\n')
        diag_session.report.add_repair_applied('CitizenFX.ini configurado')
        return jsonify({'success': True, 'path': ini_path})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/config/launchparams', methods=['GET'])
@api_error_handler
def api_config_launchparams_get():
    return jsonify({
        'parameters': [],
        'available': [
            {'param': '-novid', 'description': 'Omite video de introducción'},
            {'param': '-threads 4', 'description': 'Usa 4 hilos de CPU'},
            {'param': '-memleakfix', 'description': 'Corrige fugas de memoria'},
            {'param': '-high', 'description': 'Prioridad alta de proceso'}
        ]
    })


@app.route('/api/config/launchparams', methods=['POST'])
@api_error_handler
def api_config_launchparams_post():
    diag_session = get_current_session()
    data = request.get_json() or {}
    parameters = data.get('parameters', [])
    config_path = os.path.join(system_paths.work_folder, 'launch_params.txt')
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(' '.join(parameters))
        diag_session.report.add_repair_applied('Parámetros de lanzamiento configurados')
        diag_session.report.add_recommendation(
            f'Agrega al acceso directo: {" ".join(parameters)}'
        )
        return jsonify({'success': True, 'parameters': parameters})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/config/export', methods=['POST'])
@api_error_handler
def api_config_export():
    import json
    diag_session = get_current_session()
    diag = DiagnosticService(svc_cfg)
    config = {
        'version': SCRIPT_VERSION,
        'timestamp': get_formatted_datetime(),
        'citizenfx': diag.get_citizenfx_config(),
        'report': diag_session.get_report_dict()
    }
    export_path = os.path.join(system_paths.work_folder, f'FiveM_Config_{get_timestamp()}.json')
    try:
        with open(export_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return jsonify({'success': True, 'path': export_path})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/profiles/apply', methods=['POST'])
@api_error_handler
def api_profiles_apply():
    diag_session = get_current_session()
    repair = RepairService(svc_cfg, diag_session)
    data = request.get_json() or {}
    profile = data.get('profile', 'medium')
    valid_profiles = {'potato', 'low', 'medium', 'high', 'ultra'}
    if profile not in valid_profiles:
        return jsonify({'success': False, 'error': 'Perfil no válido'})
    repair._optimize_graphics_config()
    diag_session.report.add_repair_applied(f'Perfil {profile} aplicado')
    return jsonify({'success': True, 'profile': profile})


# ============= BACKUPS =============

@app.route('/api/backups', methods=['GET'])
@api_error_handler
def api_backups():
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
                    size = get_folder_size(item_path) if os.path.isdir(item_path) else os.path.getsize(item_path)
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
    import shutil
    diag_session = get_current_session()
    data = request.get_json() or {}
    backup_path = data.get('path', '')

    if not validate_backup_path(backup_path, system_paths.backup_folder):
        logger.warning(f"Invalid restore path attempt: {backup_path}")
        return jsonify({'success': False, 'error': 'Ruta de backup no válida'}), 400

    if not os.path.exists(backup_path):
        return jsonify({'success': False, 'error': 'Backup no encontrado'}), 404

    backup_name = os.path.basename(backup_path)
    destination = None
    if 'Cache' in backup_name:
        destination = system_paths.fivem_paths.get('Cache', '')
    elif 'CitizenFX' in backup_name:
        destination = system_paths.fivem_paths.get('CitizenFXIni', '')
    else:
        return jsonify({'success': False, 'error': 'No se puede determinar el destino del backup'})

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
    <p>Versión: {SCRIPT_VERSION}</p>
    <div class="section">
        <h2>Estado General: {report.overall_status}</h2>
        <p>Problemas Críticos: <span class="error">{report.critical_issues}</span></p>
        <p>Advertencias: <span class="warning">{report.warnings}</span></p>
    </div>
    <div class="section">
        <h2>Reparaciones Aplicadas</h2>
        {''.join(f'<p class="success">✓ {r}</p>' for r in report.repairs_applied) or '<p>Ninguna</p>'}
    </div>
    <div class="section">
        <h2>Recomendaciones</h2>
        {''.join(f'<p>→ {r}</p>' for r in report.recommendations) or '<p>Ninguna</p>'}
    </div>
</body>
</html>'''

    report_path = os.path.join(system_paths.work_folder, f'FiveM_Report_{get_timestamp()}.html')
    try:
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html)
        return jsonify({'success': True, 'path': report_path})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/report/view')
@api_error_handler
def api_report_view():
    """
    FIX: El endpoint ahora acepta un parámetro ?path= opcional.
    Si no se proporciona, devuelve el reporte más reciente.
    """
    import glob

    requested_path = request.args.get('path', '').strip()

    if requested_path:
        # Validar que la ruta esté dentro de la carpeta de trabajo
        if not validate_backup_path(requested_path, system_paths.work_folder):
            return jsonify({'error': 'Ruta no permitida'}), 400
        if os.path.exists(requested_path) and requested_path.endswith('.html'):
            return send_file(requested_path)

    # Fallback: el más reciente
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
    app.run(host=server_config.host, port=server_config.port, debug=server_config.debug)
