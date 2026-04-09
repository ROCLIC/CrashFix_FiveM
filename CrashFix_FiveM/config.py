# -*- coding: utf-8 -*-
"""
Configuración centralizada para FiveM Diagnostic Tool.
"""

import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List

# ============= VERSIÓN Y METADATOS =============
SCRIPT_VERSION = "6.1.0-PRO"
SCRIPT_NAME = "FiveM Diagnostic & AUTO-REPAIR Tool"

# ============= CONFIGURACIÓN DEL SERVIDOR =============
@dataclass
class ServerConfig:
    host: str = os.environ.get('FIVEM_DIAG_HOST', '127.0.0.1')
    port: int = int(os.environ.get('FIVEM_DIAG_PORT', '5000'))
    debug: bool = os.environ.get('FIVEM_DIAG_DEBUG', 'false').lower() == 'true'
    secret_key: str = os.environ.get('FIVEM_DIAG_SECRET', os.urandom(24).hex())

# ============= RUTAS DEL SISTEMA =============
@dataclass
class SystemPaths:
    def __post_init__(self):
        if sys.platform == 'win32':
            self.local_appdata = os.environ.get('LOCALAPPDATA', '')
            self.appdata = os.environ.get('APPDATA', '')
            self.userprofile = os.environ.get('USERPROFILE', '')
            self.system_root = os.environ.get('SystemRoot', 'C:\\Windows')
        else:
            self.local_appdata = '/tmp/FiveM'
            self.appdata = '/tmp/AppData'
            self.userprofile = os.path.expanduser('~')
            self.system_root = '/tmp/Windows'

    @property
    def fivem_paths(self) -> Dict[str, str]:
        return {
            'LocalAppData': os.path.join(self.local_appdata, 'FiveM'),
            'FiveMApp': os.path.join(self.local_appdata, 'FiveM', 'FiveM.app'),
            'Cache': os.path.join(self.local_appdata, 'FiveM', 'FiveM.app', 'cache'),
            'Logs': os.path.join(self.local_appdata, 'FiveM', 'FiveM.app', 'logs'),
            'CitizenFX': os.path.join(self.appdata, 'CitizenFX'),
            'RosId': os.path.join(self.appdata, 'CitizenFX', 'ros_id.dat'),
            'DigitalEntitlements': os.path.join(self.local_appdata, 'DigitalEntitlements'),
            # Ruta real de CitizenFX.ini segun documentacion oficial de FiveM:
            # %localappdata%\FiveM\FiveM.app\CitizenFX.ini
            'CitizenFXIni': os.path.join(self.local_appdata, 'FiveM', 'FiveM.app', 'CitizenFX.ini'),
            # Ruta legacy (algunas instalaciones antiguas)
            'CitizenFXIniLegacy': os.path.join(self.appdata, 'CitizenFX', 'CitizenFX.ini')
        }

    @property
    def work_folder(self) -> str:
        return os.path.join(self.userprofile, 'Documents', 'FiveM_Diagnostic')

    @property
    def backup_folder(self) -> str:
        return os.path.join(self.work_folder, 'Backups')

# ============= CONFIGURACIÓN DE DIAGNÓSTICO =============
@dataclass
class DiagnosticConfig:
    fivem_processes: List[str] = field(default_factory=lambda: [
        'FiveM.exe', 'FiveM_GTAProcess.exe', 'FiveM_ChromeBrowser.exe', 'GTA5.exe'
    ])
    conflicting_dlls: List[str] = field(default_factory=lambda: [
        'v8.dll', 'v8_libbase.dll', 'v8_libplatform.dll'
    ])
    safe_cache_folders: List[str] = field(default_factory=lambda: [
        'browser', 'game', 'priv', 'subprocess'
    ])
    mod_indicators: List[str] = field(default_factory=lambda: [
        'scripts', 'mods', 'OpenIV.asi', 'dinput8.dll', 'ScriptHookV.dll', 'dsound.dll'
    ])
    conflicting_software: List[Dict[str, str]] = field(default_factory=lambda: [
        {'name': 'MSI Afterburner', 'process': 'MSIAfterburner.exe'},
        {'name': 'RivaTuner', 'process': 'RTSS.exe'},
        {'name': 'Fraps', 'process': 'fraps.exe'},
        {'name': 'Razer Cortex', 'process': 'RazerCortex.exe'}
    ])
    overlay_processes: Dict[str, str] = field(default_factory=lambda: {
        'Discord': 'Discord.exe',
        'Steam Overlay': 'GameOverlayUI.exe',
        'GeForce Experience': 'nvcontainer.exe',
        'Xbox Game Bar': 'GameBar.exe'
    })

# ============= PATRONES DE ERROR =============
@dataclass
class ErrorPatterns:
    patterns: Dict[str, Dict[str, str]] = field(default_factory=lambda: {
        'ERR_GFX_D3D_INIT': {
            'severity': 'critical',
            'description': 'Error de inicialización de DirectX',
            'solution': 'Actualiza los drivers de tu GPU'
        },
        'ERR_MEM_MULTIALLOC_FREE': {
            'severity': 'critical',
            'description': 'Error de gestión de memoria',
            'solution': 'Aumenta la memoria virtual del sistema'
        },
        'ERR_GEN_INVALID': {
            'severity': 'high',
            'description': 'Error genérico de validación',
            'solution': 'Verifica la integridad de los archivos del juego'
        },
        'Entry Point Not Found': {
            'severity': 'critical',
            'description': 'DLL conflictiva en System32',
            'solution': 'Elimina v8.dll de la carpeta System32'
        },
        'ERR_GFX_STATE': {
            'severity': 'high',
            'description': 'Error de estado gráfico',
            'solution': 'Reinicia el juego y verifica drivers'
        },
        'ERR_NET_TIMEOUT': {
            'severity': 'medium',
            'description': 'Timeout de conexión',
            'solution': 'Verifica tu conexión a internet'
        }
    })

# ============= TEXTURE BUDGET =============
@dataclass
class TextureBudgetConfig:
    vram_to_budget: Dict[int, int] = field(default_factory=lambda: {
        2: 25, 4: 35, 6: 50, 8: 65, 10: 75,
    })

    def get_recommended_budget(self, vram_gb: float) -> int:
        if vram_gb <= 2:
            return 25
        elif vram_gb <= 4:
            return 35
        elif vram_gb <= 6:
            return 50
        elif vram_gb <= 8:
            return 65
        else:
            return 75

# ============= TIMEOUTS =============
@dataclass
class TimeoutConfig:
    powershell_timeout: int = 30
    ping_timeout: int = 5
    packet_loss_timeout: int = 15
    nvidia_smi_timeout: int = 5
    process_kill_wait: float = 1.0

# ============= REQUISITOS =============
@dataclass
class SystemRequirements:
    min_ram_gb: int = 8
    recommended_ram_gb: int = 16
    min_vram_gb: int = 2
    recommended_vram_gb: int = 4
    min_benchmark_score: int = 50

# ============= RED =============
@dataclass
class NetworkConfig:
    dns_servers: List[Dict[str, str]] = field(default_factory=lambda: [
        {'name': 'Google DNS', 'ip': '8.8.8.8'},
        {'name': 'Cloudflare', 'ip': '1.1.1.1'},
        {'name': 'OpenDNS', 'ip': '208.67.222.222'}
    ])
    max_acceptable_latency_ms: int = 100
    max_acceptable_packet_loss_percent: float = 5.0

# ============= INSTANCIAS GLOBALES =============
server_config = ServerConfig()
system_paths = SystemPaths()
diagnostic_config = DiagnosticConfig()
error_patterns = ErrorPatterns()
texture_budget_config = TextureBudgetConfig()
timeout_config = TimeoutConfig()
system_requirements = SystemRequirements()
network_config = NetworkConfig()

BACKUP_CATEGORIES = ['Cache', 'Mods', 'Config', 'DLLs', 'ROS', 'General']

def is_windows() -> bool:
    return sys.platform == 'win32'

def get_timestamp() -> str:
    from datetime import datetime
    return datetime.now().strftime('%Y%m%d_%H%M%S')

def get_formatted_datetime() -> str:
    from datetime import datetime
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
