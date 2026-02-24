# -*- coding: utf-8 -*-
"""
Gestión de sesiones para FiveM Diagnostic Tool.

Este módulo reemplaza las variables globales mutables con un sistema
de sesiones que mantiene el estado por usuario/request.
"""

import uuid
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from collections import OrderedDict


@dataclass
class RepairStats:
    """Estadísticas de reparaciones."""
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
    
    def increment_attempted(self) -> None:
        self.attempted += 1
    
    def increment_successful(self) -> None:
        self.successful += 1
    
    def increment_failed(self) -> None:
        self.failed += 1


@dataclass
class DiagnosticReport:
    """Reporte de diagnóstico."""
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
        return {
            'Metadata': {
                'Version': self.version,
                'Timestamp': self.timestamp
            },
            'Summary': {
                'OverallStatus': self.overall_status,
                'CriticalIssues': self.critical_issues,
                'Warnings': self.warnings,
                'Recommendations': self.recommendations.copy(),
                'RepairsApplied': self.repairs_applied.copy(),
                'RepairsFailed': self.repairs_failed.copy()
            },
            'GTA': self.gta_info.copy(),
            'FiveM': self.fivem_info.copy(),
            'Hardware': self.hardware_info.copy(),
            'Network': self.network_info.copy(),
            'Software': self.software_info.copy(),
            'Errors': self.errors_info.copy()
        }
    
    def add_recommendation(self, recommendation: str) -> None:
        if recommendation and recommendation not in self.recommendations:
            self.recommendations.append(recommendation)
    
    def add_repair_applied(self, repair: str) -> None:
        if repair:
            self.repairs_applied.append(repair)
    
    def add_repair_failed(self, repair: str) -> None:
        if repair:
            self.repairs_failed.append(repair)
    
    def increment_critical(self) -> None:
        self.critical_issues += 1
    
    def increment_warnings(self) -> None:
        self.warnings += 1
    
    def calculate_overall_status(self) -> str:
        """Calcula el estado general basado en problemas encontrados."""
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
    """
    Sesión de diagnóstico individual.
    
    Mantiene el estado de un diagnóstico específico, incluyendo
    el reporte y las estadísticas de reparación.
    """
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    report: DiagnosticReport = field(default_factory=DiagnosticReport)
    repair_stats: RepairStats = field(default_factory=RepairStats)
    
    def __post_init__(self):
        from config import SCRIPT_VERSION, get_formatted_datetime
        self.report.version = SCRIPT_VERSION
        self.report.timestamp = get_formatted_datetime()
    
    def update_activity(self) -> None:
        """Actualiza el timestamp de última actividad."""
        self.last_activity = datetime.now()
    
    def get_report_dict(self) -> Dict[str, Any]:
        """Obtiene el reporte como diccionario."""
        return self.report.to_dict()
    
    def get_stats_dict(self) -> Dict[str, int]:
        """Obtiene las estadísticas como diccionario."""
        return self.repair_stats.to_dict()


class SessionManager:
    """
    Gestor de sesiones de diagnóstico.
    
    Implementa un almacén thread-safe de sesiones con límite
    de capacidad y limpieza automática de sesiones antiguas.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, max_sessions: int = 100):
        """Implementa patrón singleton."""
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
        """
        Crea una nueva sesión de diagnóstico.
        
        Returns:
            Nueva sesión de diagnóstico
        """
        with self._session_lock:
            # Limpiar sesiones antiguas si se alcanza el límite
            while len(self._sessions) >= self._max_sessions:
                self._sessions.popitem(last=False)
            
            session = DiagnosticSession()
            self._sessions[session.session_id] = session
            return session
    
    def get_session(self, session_id: str) -> Optional[DiagnosticSession]:
        """
        Obtiene una sesión por su ID.
        
        Args:
            session_id: ID de la sesión
            
        Returns:
            Sesión si existe, None en caso contrario
        """
        with self._session_lock:
            session = self._sessions.get(session_id)
            if session:
                session.update_activity()
                # Mover al final para LRU
                self._sessions.move_to_end(session_id)
            return session
    
    def get_or_create_session(self, session_id: Optional[str] = None) -> DiagnosticSession:
        """
        Obtiene una sesión existente o crea una nueva.
        
        Args:
            session_id: ID de sesión opcional
            
        Returns:
            Sesión existente o nueva
        """
        if session_id:
            session = self.get_session(session_id)
            if session:
                return session
        return self.create_session()
    
    def delete_session(self, session_id: str) -> bool:
        """
        Elimina una sesión.
        
        Args:
            session_id: ID de la sesión a eliminar
            
        Returns:
            True si se eliminó, False si no existía
        """
        with self._session_lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False
    
    def cleanup_old_sessions(self, max_age_minutes: int = 60) -> int:
        """
        Limpia sesiones antiguas.
        
        Args:
            max_age_minutes: Edad máxima en minutos
            
        Returns:
            Número de sesiones eliminadas
        """
        from datetime import timedelta
        
        cutoff = datetime.now() - timedelta(minutes=max_age_minutes)
        removed = 0
        
        with self._session_lock:
            sessions_to_remove = [
                sid for sid, session in self._sessions.items()
                if session.last_activity < cutoff
            ]
            
            for sid in sessions_to_remove:
                del self._sessions[sid]
                removed += 1
        
        return removed
    
    @property
    def active_sessions_count(self) -> int:
        """Número de sesiones activas."""
        return len(self._sessions)


# Instancia global del gestor de sesiones
session_manager = SessionManager()


def get_session_manager() -> SessionManager:
    """Obtiene la instancia del gestor de sesiones."""
    return session_manager
