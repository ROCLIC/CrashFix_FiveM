# -*- coding: utf-8 -*-
import re, logging
from typing import Dict, List, Any
from src.utils.system_utils import is_windows, run_command, ping_host

logger = logging.getLogger(__name__)

class NetworkService:
    def __init__(self, config):
        self.config = config
        self.network_config = config.network_config
        self.timeout_config = config.timeout_config

    def test_network_quality(self) -> Dict[str, Any]:
        targets = self.network_config.dns_servers[:2]
        results = []
        total_latency = 0
        successful = 0
        for target in targets:
            ping_result = ping_host(target['ip'], count=1, timeout_ms=1000)
            if ping_result and ping_result['success']:
                results.append({'name': target['name'], 'latency': ping_result['latency_ms'], 'status': 'ok'})
                total_latency += ping_result['latency_ms']
                successful += 1
            else:
                results.append({'name': target['name'], 'latency': 0, 'status': 'failed'})
        avg_latency = round(total_latency / successful) if successful > 0 else 0
        status = 'OK' if successful > 0 else 'Error'
        if avg_latency > self.network_config.max_acceptable_latency_ms:
            status = 'Slow'
        return {'Status': status, 'Ping': avg_latency, 'Tests': results, 'Successful': successful, 'Total': len(targets)}

    def test_packet_loss(self) -> Dict[str, Any]:
        targets = ['8.8.8.8', '1.1.1.1']
        results = []
        if is_windows():
            for target in targets:
                try:
                    result = run_command(['ping', '-n', '10', target], timeout=self.timeout_config.packet_loss_timeout)
                    if result:
                        match = re.search(r'(\d+)%\s*(?:perdidos|loss)', result.stdout, re.IGNORECASE)
                        results.append({'name': target, 'packet_loss': int(match.group(1)) if match else 0})
                    else:
                        results.append({'name': target, 'packet_loss': -1})
                except Exception as e:
                    logger.warning(f"Packet loss test error for {target}: {e}")
                    results.append({'name': target, 'packet_loss': -1})
        else:
            results = [{'name': t, 'packet_loss': 0} for t in targets]
        valid = [r['packet_loss'] for r in results if r['packet_loss'] >= 0]
        avg_loss = round(sum(valid) / len(valid), 1) if valid else 0
        recommendations = []
        if avg_loss > self.network_config.max_acceptable_packet_loss_percent:
            recommendations.append('Contacta a tu ISP, hay pérdida de paquetes significativa')
            recommendations.append('Verifica tu conexión por cable en lugar de WiFi')
        return {'tests': results, 'average_loss': avg_loss, 'recommendations': recommendations}

    def optimize_network_stack(self) -> Dict[str, Any]:
        """Optimiza la pila de red: Flush DNS, Reset Winsock e IP."""
        results = []
        if is_windows():
            commands = [
                ('ipconfig /flushdns', 'Flush DNS Cache'),
                ('netsh winsock reset', 'Reset Winsock Catalog'),
                ('netsh int ip reset', 'Reset TCP/IP Stack')
            ]
            for cmd, desc in commands:
                try:
                    res = run_command(cmd.split(), timeout=10)
                    success = res and res.returncode == 0
                    results.append({'action': desc, 'success': success})
                except Exception as e:
                    results.append({'action': desc, 'success': False, 'error': str(e)})
        
        success_count = sum(1 for r in results if r['success'])
        return {
            'success': success_count > 0,
            'actions': results,
            'message': f"Optimización de red completada: {success_count}/{len(results)} exitosas."
        }

    def optimize_dns(self) -> Dict[str, Any]:
        dns_servers = self.network_config.dns_servers
        results = []
        best = None
        best_latency = 9999
        for dns in dns_servers:
            ping_result = ping_host(dns['ip'], count=1, timeout_ms=1000)
            if ping_result and ping_result['success']:
                latency = ping_result['latency_ms']
                results.append({'name': dns['name'], 'ip': dns['ip'], 'latency_ms': latency, 'status': 'ok' if latency < 100 else 'slow'})
                if latency < best_latency:
                    best_latency = latency
                    best = dns['name']
            else:
                results.append({'name': dns['name'], 'ip': dns['ip'], 'latency_ms': -1, 'status': 'error'})
        return {'dns_test_results': results, 'best_dns': best, 'best_latency': best_latency if best else None, 'recommendation': f'Usa {best} DNS ({best_latency}ms)' if best else None}
