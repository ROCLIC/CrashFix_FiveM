# -*- coding: utf-8 -*-
"""
Gestion de sesiones de diagnostico.

Proporciona las clases para manejar el estado de las sesiones de
diagnostico, incluyendo reportes, estadisticas de reparacion y
gestion de multiples sesiones concurrentes.
"""

import uuid
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from collections import OrderedDict


@dataclass
class RepairStats:
    """Estadisticas de reparaciones realizadas durante una sesion."""
    attempted: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0

    def to_dict(self) -> Dict[str, int]:
        return {
            'Attempted': self.attempted,
            'Successful': self.successful,
            'Failed': self.failed,
            'Skipped': self.skipped
        }

    def increment_attempted(self):
        self.attempted += 1

    def increment_successful(self):
        self.successful += 1

    def increment_failed(self):
        self.failed += 1


@dataclass
class DiagnosticReport:
    """Reporte de diagnostico que acumula resultados y recomendaciones."""
    version: str = ''
    timestamp: str = ''
    overall_status: str = 'Pendiente'
    critical_issues: int = 0
    warnings: int = 0
    recommendations: List[str] = field(default_factory=list)
    repairs_applied: List[str] = field(default_factory=list)
    repairs_failed: List[str] = field(default_factory=list)
    gta_info: Dict[str, Any] = field(default_factory=dict)
    fivem_info: Dict[str, Any] = field(default_factory=dict)
    hardware_info: Dict[str, Any] = field(default_factory=dict)
    network_info: Dict[str, Any] = field(default_factory=dict)
    software_info: Dict[str, Any] = field(default_factory=dict)
    errors_info: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serializa el reporte a un diccionario."""
        return {
            'Metadata': {
                'Version': self.version,
                'Timestamp': self.timestamp
            },
            'Summary': {
                'OverallStatus': self.overall_status,
                'CriticalIssues': self.critical_issues,
                'Warnings': self.warnings,
                'Recommendations': list(self.recommendations),
                'RepairsApplied': list(self.repairs_applied),
                'RepairsFailed': list(self.repairs_failed)
            },
            'GTA': dict(self.gta_info),
            'Hardware': dict(self.hardware_info),
            'Network': dict(self.network_info),
            'Software': dict(self.software_info),
            'Errors': dict(self.errors_info)
        }

    def add_recommendation(self, r: str):
        """Agrega una recomendacion si no existe ya."""
        if r and r not in self.recommendations:
            self.recommendations.append(r)

    def add_repair_applied(self, r: str):
        """Registra una reparacion aplicada exitosamente."""
        if r:
            self.repairs_applied.append(r)

    def add_repair_failed(self, r: str):
        """Registra una reparacion fallida."""
        if r:
            self.repairs_failed.append(r)

    def increment_critical(self):
        """Incrementa el contador de problemas criticos."""
        self.critical_issues += 1

    def increment_warnings(self):
        """Incrementa el contador de advertencias."""
        self.warnings += 1

    def reset_counters(self):
        """Reinicia los contadores para un nuevo diagnostico."""
        self.critical_issues = 0
        self.warnings = 0

    def calculate_overall_status(self) -> str:
        """
        Calcula el estado general basado en los contadores de problemas.

        Retorna:
            'Critico' si hay problemas criticos
            'Regular' si hay mas de 2 advertencias
            'Bueno' si hay entre 1 y 2 advertencias
            'Excelente' si no hay problemas
        """
        if self.critical_issues > 0:
            self.overall_status = 'Critico'
        elif self.warnings > 2:
            self.overall_status = 'Regular'
        elif self.warnings > 0:
            self.overall_status = 'Bueno'
        else:
            self.overall_status = 'Excelente'
        return self.overall_status


@dataclass
class DiagnosticSession:
    """Sesion de diagnostico individual con su reporte y estadisticas."""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    report: DiagnosticReport = field(default_factory=DiagnosticReport)
    repair_stats: RepairStats = field(default_factory=RepairStats)
    action_history: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        from config import SCRIPT_VERSION, get_formatted_datetime
        self.report.version = SCRIPT_VERSION
        self.report.timestamp = get_formatted_datetime()

    def update_activity(self):
        """Actualiza la marca de tiempo de ultima actividad."""
        self.last_activity = datetime.now()

    def add_action(self, action_type: str, description: str, status: str = 'info', details: Any = None):
        """Registra una accion en el historial con timestamp."""
        self.action_history.append({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
            'type': action_type,
            'description': description,
            'status': status,
            'details': details
        })
        self.update_activity()

    def get_report_dict(self) -> Dict[str, Any]:
        """Devuelve el reporte serializado como diccionario."""
        return self.report.to_dict()

    def get_stats_dict(self) -> Dict[str, int]:
        """Devuelve las estadisticas de reparacion como diccionario."""
        return self.repair_stats.to_dict()


class SessionManager:
    """
    Gestor de sesiones singleton con soporte para multiples sesiones
    concurrentes y limpieza automatica por LRU.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, max_sessions: int = 100):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, max_sessions: int = 100):
        if self._initialized:
            return
        self._sessions: OrderedDict[str, DiagnosticSession] = OrderedDict()
        self._max_sessions = max_sessions
        self._session_lock = threading.Lock()
        self._initialized = True

    def create_session(self) -> DiagnosticSession:
        """Crea una nueva sesion, eliminando la mas antigua si se excede el limite."""
        with self._session_lock:
            while len(self._sessions) >= self._max_sessions:
                self._sessions.popitem(last=False)
            s = DiagnosticSession()
            self._sessions[s.session_id] = s
            return s

    def get_session(self, session_id: str) -> Optional[DiagnosticSession]:
        """Obtiene una sesion por su ID y actualiza su posicion LRU."""
        with self._session_lock:
            s = self._sessions.get(session_id)
            if s:
                s.update_activity()
                self._sessions.move_to_end(session_id)
            return s

    def get_or_create_session(
        self, session_id: Optional[str] = None
    ) -> DiagnosticSession:
        """Obtiene una sesion existente o crea una nueva."""
        if session_id:
            s = self.get_session(session_id)
            if s:
                return s
        return self.create_session()

    def delete_session(self, session_id: str) -> bool:
        """Elimina una sesion por su ID."""
        with self._session_lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False

    @property
    def active_sessions_count(self) -> int:
        """Devuelve el numero de sesiones activas."""
        return len(self._sessions)


# Instancia singleton global
session_manager = SessionManager()


def get_session_manager() -> SessionManager:
    """Devuelve la instancia singleton del gestor de sesiones."""
    return session_manager
