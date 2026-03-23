# -*- coding: utf-8 -*-
import os, logging
from datetime import datetime
from typing import Optional

class Logger:
    _instances = {}
    def __new__(cls, name='fivem_diagnostic', log_dir=None):
        if name not in cls._instances:
            inst = super().__new__(cls)
            cls._instances[name] = inst
        return cls._instances[name]
    def __init__(self, name='fivem_diagnostic', log_dir=None):
        if hasattr(self, '_initialized'): return
        self.name = name
        self.logger = logging.getLogger(name)
        if not self.logger.handlers:
            self.logger.setLevel(logging.DEBUG)
            ch = logging.StreamHandler()
            ch.setLevel(logging.INFO)
            ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S'))
            self.logger.addHandler(ch)
            if log_dir:
                try:
                    os.makedirs(log_dir, exist_ok=True)
                    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                    fh = logging.FileHandler(os.path.join(log_dir, f'FiveM_Diagnostic_{ts}.log'), encoding='utf-8')
                    fh.setLevel(logging.DEBUG)
                    fh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'))
                    self.logger.addHandler(fh)
                except (OSError, IOError): pass
        self._initialized = True
    def debug(self, m): self.logger.debug(m)
    def info(self, m): self.logger.info(m)
    def warning(self, m): self.logger.warning(m)
    def error(self, m): self.logger.error(m)
    def critical(self, m): self.logger.critical(m)
    def exception(self, m): self.logger.exception(m)

_app_logger = None

def get_logger(log_dir=None):
    global _app_logger
    if _app_logger is None: _app_logger = Logger('fivem_diagnostic', log_dir)
    return _app_logger

def setup_logging(log_dir: str):
    return get_logger(log_dir)
