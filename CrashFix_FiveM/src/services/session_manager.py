# -*- coding: utf-8 -*-
"""Gestión de sesiones - igual que original."""
import uuid
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from collections import OrderedDict

@dataclass
class RepairStats:
    attempted: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0
    def to_dict(self): return {'Attempted': self.attempted, 'Successful': self.successful, 'Failed': self.failed, 'Skipped': self.skipped}
    def increment_attempted(self): self.attempted += 1
    def increment_successful(self): self.successful += 1
    def increment_failed(self): self.failed += 1

@dataclass
class DiagnosticReport:
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

    def to_dict(self):
        return {
            'Metadata': {'Version': self.version, 'Timestamp': self.timestamp},
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

    def add_recommendation(self, r):
        if r and r not in self.recommendations: self.recommendations.append(r)
    def add_repair_applied(self, r):
        if r: self.repairs_applied.append(r)
    def add_repair_failed(self, r):
        if r: self.repairs_failed.append(r)
    def increment_critical(self): self.critical_issues += 1
    def increment_warnings(self): self.warnings += 1
    def calculate_overall_status(self):
        if self.critical_issues > 0: self.overall_status = 'Critico'
        elif self.warnings > 2: self.overall_status = 'Regular'
        elif self.warnings > 0: self.overall_status = 'Bueno'
        else: self.overall_status = 'Excelente'
        return self.overall_status

@dataclass
class DiagnosticSession:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    report: DiagnosticReport = field(default_factory=DiagnosticReport)
    repair_stats: RepairStats = field(default_factory=RepairStats)

    def __post_init__(self):
        from config import SCRIPT_VERSION, get_formatted_datetime
        self.report.version = SCRIPT_VERSION
        self.report.timestamp = get_formatted_datetime()

    def update_activity(self): self.last_activity = datetime.now()
    def get_report_dict(self): return self.report.to_dict()
    def get_stats_dict(self): return self.repair_stats.to_dict()

class SessionManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, max_sessions=100):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, max_sessions=100):
        if self._initialized: return
        self._sessions: OrderedDict[str, DiagnosticSession] = OrderedDict()
        self._max_sessions = max_sessions
        self._session_lock = threading.Lock()
        self._initialized = True

    def create_session(self):
        with self._session_lock:
            while len(self._sessions) >= self._max_sessions:
                self._sessions.popitem(last=False)
            s = DiagnosticSession()
            self._sessions[s.session_id] = s
            return s

    def get_session(self, session_id):
        with self._session_lock:
            s = self._sessions.get(session_id)
            if s:
                s.update_activity()
                self._sessions.move_to_end(session_id)
            return s

    def get_or_create_session(self, session_id=None):
        if session_id:
            s = self.get_session(session_id)
            if s: return s
        return self.create_session()

    def delete_session(self, session_id):
        with self._session_lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False

    @property
    def active_sessions_count(self): return len(self._sessions)

session_manager = SessionManager()

def get_session_manager(): return session_manager
