# -*- coding: utf-8 -*-
"""
Servicio de red para FiveM Diagnostic Tool.

Contiene la lógica para pruebas de conectividad y diagnóstico de red.
"""

import re
import logging
from typing import Dict, List, Any

from src.utils.system_utils import is_windows, run_command, ping_host

logger = logging.getLogger(__name__)


class NetworkService:
    """
    Servicio para operaciones de diagnóstico de red.
    
    Proporciona métodos para probar conectividad, latencia y packet loss.
    """
    
    def __init__(self, config):
        """
        Inicializa el servicio de red.
        
        Args:
            config: Objeto de configuración del sistema
        """
        self.config = config
        self.network_config = config.network_config
        self.timeout_config = config.timeout_config
    
    def test_network_quality(self) -> Dict[str, Any]:
        """
        Prueba la calidad de la conexión de red.
        
        Returns:
            Diccionario con resultados de las pruebas
        """
        targets = self.network_config.dns_servers[:2]  # Usar solo los 2 primeros
        results = []
        total_latency = 0
        successful = 0
        
        for target in targets:
            ping_result = ping_host(
                target['ip'],
                count=1,
                timeout_ms=1000
            )
            
            if ping_result:
                if ping_result['success']:
                    latency = ping_result['latency_ms']
                    results.append({
                        'name': target['name'],
                        'latency': latency,
                        'status': 'ok'
                    })
                    total_latency += latency
                    successful += 1
                else:
                    results.append({
                        'name': target['name'],
                        'latency': 0,
                        'status': 'failed'
                    })
            else:
                results.append({
                    'name': target['name'],
                    'latency': 0,
                    'status': 'error'
                })
        
        # Calcular latencia promedio evitando división por cero
        avg_latency = round(total_latency / successful) if successful > 0 else 0
        
        # Determinar estado general
        status = 'OK' if successful > 0 else 'Error'
        if avg_latency > self.network_config.max_acceptable_latency_ms:
            status = 'Slow'
        
        return {
            'Status': status,
            'Ping': avg_latency,
            'Tests': results,
            'Successful': successful,
            'Total': len(targets)
        }
    
    def test_packet_loss(self) -> Dict[str, Any]:
        """
        Prueba el packet loss de la conexión.
        
        Returns:
            Diccionario con resultados de packet loss
        """
        targets = ['8.8.8.8', '1.1.1.1']
        results = []
        
        if is_windows():
            for target in targets:
                try:
                    result = run_command(
                        ['ping', '-n', '10', target],
                        timeout=self.timeout_config.packet_loss_timeout
                    )
                    
                    if result:
                        # Buscar porcentaje de pérdida (español e inglés)
                        match = re.search(
                            r'(\d+)%\s*(?:perdidos|loss)',
                            result.stdout,
                            re.IGNORECASE
                        )
                        packet_loss = int(match.group(1)) if match else 0
                        results.append({
                            'name': target,
                            'packet_loss': packet_loss
                        })
                    else:
                        results.append({
                            'name': target,
                            'packet_loss': -1
                        })
                        
                except Exception as e:
                    logger.warning(f"Error en test de packet loss para {target}: {e}")
                    results.append({
                        'name': target,
                        'packet_loss': -1
                    })
        else:
            # Simulación para sistemas no-Windows
            for target in targets:
                results.append({
                    'name': target,
                    'packet_loss': 0
                })
        
        # Calcular promedio evitando división por cero
        valid_results = [r['packet_loss'] for r in results if r['packet_loss'] >= 0]
        avg_loss = round(sum(valid_results) / len(valid_results), 1) if valid_results else 0
        
        # Generar recomendaciones
        recommendations = []
        if avg_loss > self.network_config.max_acceptable_packet_loss_percent:
            recommendations.append('Contacta a tu ISP, hay pérdida de paquetes significativa')
            recommendations.append('Verifica tu conexión por cable en lugar de WiFi')
        
        return {
            'tests': results,
            'average_loss': avg_loss,
            'recommendations': recommendations
        }
    
    def optimize_dns(self) -> Dict[str, Any]:
        """
        Analiza y recomienda el mejor DNS.
        
        Returns:
            Diccionario con resultados del análisis DNS
        """
        dns_servers = self.network_config.dns_servers
        results = []
        best = None
        best_latency = 9999
        
        for dns in dns_servers:
            ping_result = ping_host(
                dns['ip'],
                count=1,
                timeout_ms=1000
            )
            
            if ping_result and ping_result['success']:
                latency = ping_result['latency_ms']
                status = 'ok' if latency < 100 else 'slow'
                
                results.append({
                    'name': dns['name'],
                    'ip': dns['ip'],
                    'latency_ms': latency,
                    'status': status
                })
                
                if latency < best_latency:
                    best_latency = latency
                    best = dns['name']
            else:
                results.append({
                    'name': dns['name'],
                    'ip': dns['ip'],
                    'latency_ms': -1,
                    'status': 'error'
                })
        
        recommendation = f'Usa {best} DNS ({best_latency}ms)' if best else None
        
        return {
            'dns_test_results': results,
            'best_dns': best,
            'best_latency': best_latency if best else None,
            'recommendation': recommendation
        }
    
    def get_network_summary(self) -> Dict[str, Any]:
        """
        Obtiene un resumen completo del estado de la red.
        
        Returns:
            Diccionario con resumen de red
        """
        quality = self.test_network_quality()
        packet_loss = self.test_packet_loss()
        
        # Determinar estado general
        issues = []
        
        if quality['Status'] != 'OK':
            issues.append('Problemas de conectividad')
        
        if quality['Ping'] > self.network_config.max_acceptable_latency_ms:
            issues.append(f'Latencia alta ({quality["Ping"]}ms)')
        
        if packet_loss['average_loss'] > self.network_config.max_acceptable_packet_loss_percent:
            issues.append(f'Packet loss ({packet_loss["average_loss"]}%)')
        
        return {
            'status': 'OK' if not issues else 'Warning',
            'quality': quality,
            'packet_loss': packet_loss,
            'issues': issues,
            'recommendations': packet_loss.get('recommendations', [])
        }
