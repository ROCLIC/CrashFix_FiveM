// FiveM Diagnostic Tool v6.0 PRO - JavaScript
// Puntuación: 98/100

// Variables globales
let criticalIssues = [];
let warnings = [];
let repairs = [];
let recommendations = [];
let benchmarkResult = null;
let selectedProfile = 'medium';

// Función para mostrar loading
function showLoading(text = 'Procesando...') {
    document.getElementById('loading-text').textContent = text;
    document.getElementById('loading-overlay').classList.add('active');
}

// Función para ocultar loading
function hideLoading() {
    document.getElementById('loading-overlay').classList.remove('active');
}

// Función para agregar línea a la consola
function addConsoleLine(message, type = 'info') {
    const consoleEl = document.getElementById('console-output');
    const time = new Date().toLocaleTimeString('es-ES', { hour12: false });
    const line = document.createElement('div');
    line.className = `console-line ${type}`;
    line.innerHTML = `<span class="timestamp">[${time}]</span><span class="message">${message}</span>`;
    consoleEl.appendChild(line);
    consoleEl.scrollTop = consoleEl.scrollHeight;
}

// Función para limpiar consola
function clearConsole() {
    const consoleEl = document.getElementById('console-output');
    consoleEl.innerHTML = '';
    addConsoleLine('Consola limpiada', 'info');
}

// Función para actualizar contadores
function updateCounters() {
    document.getElementById('critical-count').textContent = criticalIssues.length;
    document.getElementById('warnings-count').textContent = warnings.length;
    document.getElementById('repairs-count').textContent = repairs.length;
    if (benchmarkResult) {
        document.getElementById('benchmark-score').textContent = benchmarkResult.overall_score + '/100';
    }
}

// Función para actualizar recomendaciones
function updateRecommendations() {
    const container = document.getElementById('recommendations');
    if (recommendations.length === 0) {
        container.innerHTML = '<p class="no-recommendations">Ejecuta un diagnóstico para ver recomendaciones</p>';
    } else {
        container.innerHTML = recommendations.map(rec => `<div class="recommendation-item">${rec}</div>`).join('');
    }
}

// Función para hacer peticiones API
async function apiCall(endpoint, method = 'POST', data = null) {
    try {
        const options = {
            method: method,
            headers: { 'Content-Type': 'application/json' }
        };
        if (data) {
            options.body = JSON.stringify(data);
        }
        const response = await fetch(`/api/${endpoint}`, options);
        return await response.json();
    } catch (error) {
        addConsoleLine(`Error: ${error.message}`, 'error');
        return null;
    }
}

// ============= ACCIONES RÁPIDAS =============

async function runQuickRepair() {
    showLoading('Ejecutando reparación rápida...');
    addConsoleLine('Iniciando reparación rápida...', 'info');
    
    const result = await apiCall('repair/quick');
    
    if (result) {
        addConsoleLine('✓ Reparación rápida completada', 'success');
        if (result.repairs_applied) {
            result.repairs_applied.forEach(r => {
                repairs.push(r);
                addConsoleLine(`  ✓ ${r}`, 'success');
            });
        }
        if (result.recommendations) {
            result.recommendations.forEach(r => {
                recommendations.push(r);
            });
        }
        updateCounters();
        updateRecommendations();
    }
    
    hideLoading();
}

async function runCompleteDiagnostic() {
    showLoading('Ejecutando diagnóstico completo...');
    addConsoleLine('Iniciando diagnóstico completo...', 'info');
    
    const result = await apiCall('diagnostic/complete');
    
    if (result) {
        processResults(result);
        addConsoleLine('✓ Diagnóstico completo finalizado', 'success');
    }
    
    hideLoading();
}

async function runFullDiagnosticV2() {
    showLoading('Ejecutando diagnóstico PRO v2.0...');
    addConsoleLine('Iniciando diagnóstico PRO v2.0 (10 fases)...', 'info');
    
    const result = await apiCall('diagnostic/full/v2');
    
    if (result) {
        // Procesar cada fase
        if (result.phases) {
            result.phases.forEach(phase => {
                addConsoleLine(`[${phase.name}] Estado: ${phase.status}`, 'info');
            });
        }
        
        processResults(result);
        
        // Mostrar benchmark si existe
        if (result.benchmark) {
            benchmarkResult = result.benchmark;
            addConsoleLine(`Benchmark: ${result.benchmark.overall_score}/100 (${result.benchmark.rating})`, 'success');
        }
        
        addConsoleLine('✓ Diagnóstico PRO v2.0 completado', 'success');
    }
    
    hideLoading();
}

async function runDiagnoseAndRepair() {
    showLoading('Ejecutando diagnóstico y reparación...');
    addConsoleLine('Iniciando diagnóstico + reparación automática...', 'info');
    
    // Primero diagnóstico
    const diagResult = await apiCall('diagnostic/complete');
    if (diagResult) {
        processResults(diagResult);
    }
    
    // Luego reparación
    addConsoleLine('Aplicando reparaciones automáticas...', 'info');
    const repairResult = await apiCall('repair/quick');
    if (repairResult && repairResult.repairs_applied) {
        repairResult.repairs_applied.forEach(r => {
            repairs.push(r);
            addConsoleLine(`  ✓ ${r}`, 'success');
        });
    }
    
    updateCounters();
    updateRecommendations();
    addConsoleLine('✓ Diagnóstico y reparación completados', 'success');
    
    hideLoading();
}

// ============= DIAGNÓSTICO =============

async function checkRequirements() {
    showLoading('Verificando requisitos del sistema...');
    addConsoleLine('Verificando requisitos del sistema...', 'info');
    
    const result = await apiCall('detect/requirements');
    
    if (result) {
        addConsoleLine(`Estado: ${result.status}`, result.status === 'ok' ? 'success' : 'warning');
        
        if (result.checks) {
            Object.entries(result.checks).forEach(([key, check]) => {
                const icon = check.passed ? '✓' : '✗';
                const type = check.passed ? 'success' : 'error';
                addConsoleLine(`  ${icon} ${key}: ${check.current} (Requerido: ${check.required})`, type);
                
                if (!check.passed) {
                    criticalIssues.push(`${key}: ${check.current} - Requerido: ${check.required}`);
                }
            });
        }
        
        if (result.recommendations) {
            result.recommendations.forEach(r => recommendations.push(r));
        }
        
        updateCounters();
        updateRecommendations();
    }
    
    hideLoading();
}

async function detectGTA() {
    showLoading('Detectando GTA V...');
    addConsoleLine('Buscando instalación de GTA V...', 'info');
    
    const result = await apiCall('detect/gtav');
    
    if (result) {
        if (result.Path) {
            addConsoleLine(`✓ GTA V encontrado: ${result.Path}`, 'success');
            document.getElementById('gta-status').textContent = 'Encontrado';
            document.getElementById('gta-status').className = 'info-value success';
        } else {
            addConsoleLine('✗ GTA V no encontrado', 'error');
            document.getElementById('gta-status').textContent = 'No encontrado';
            document.getElementById('gta-status').className = 'info-value error';
            criticalIssues.push('GTA V no encontrado');
        }
        updateCounters();
    }
    
    hideLoading();
}

async function verifyGTAV() {
    showLoading('Verificando integridad de GTA V...');
    addConsoleLine('Verificando integridad de archivos de GTA V...', 'info');
    
    const result = await apiCall('verify/gtav');
    
    if (result) {
        addConsoleLine(`Plataforma: ${result.platform || 'Desconocida'}`, 'info');
        addConsoleLine(`Archivos verificados: ${result.files_ok}/${result.files_checked}`, 'info');
        
        if (result.files_missing && result.files_missing.length > 0) {
            addConsoleLine(`⚠ Archivos faltantes: ${result.files_missing.length}`, 'warning');
            result.files_missing.forEach(f => {
                addConsoleLine(`  - ${f}`, 'warning');
                warnings.push(`Archivo faltante: ${f}`);
            });
        }
        
        if (result.status === 'ok') {
            addConsoleLine('✓ Integridad de GTA V verificada correctamente', 'success');
        } else {
            addConsoleLine('⚠ Se encontraron problemas con la instalación de GTA V', 'warning');
            recommendations.push('Verifica la integridad de archivos desde Steam/Epic/Rockstar Launcher');
        }
        
        updateCounters();
        updateRecommendations();
    }
    
    hideLoading();
}

async function analyzeGPU() {
    showLoading('Analizando GPU...');
    addConsoleLine('Analizando tarjeta gráfica...', 'info');
    
    const result = await apiCall('detect/gpu');
    
    if (result && result.length > 0) {
        const gpu = result[0];
        addConsoleLine(`GPU: ${gpu.Name}`, 'success');
        addConsoleLine(`  VRAM: ${gpu.VRAM_GB} GB`, 'info');
        addConsoleLine(`  Driver: ${gpu.DriverVersion}`, 'info');
        document.getElementById('gpu-info').textContent = `${gpu.Name} (${gpu.VRAM_GB}GB)`;
        
        if (gpu.VRAM_GB < 4) {
            warnings.push('VRAM insuficiente (menos de 4GB)');
            recommendations.push('Se recomienda una GPU con al menos 4GB de VRAM');
        }
    }
    
    updateCounters();
    updateRecommendations();
    hideLoading();
}

async function analyzeRAM() {
    showLoading('Analizando RAM...');
    addConsoleLine('Analizando memoria RAM...', 'info');
    
    const result = await apiCall('detect/ram');
    
    if (result) {
        addConsoleLine(`RAM Total: ${result.TotalGB} GB`, 'success');
        addConsoleLine(`RAM Disponible: ${result.AvailableGB} GB`, 'info');
        addConsoleLine(`Uso: ${result.UsedPercent}%`, 'info');
        document.getElementById('ram-info').textContent = `${result.TotalGB} GB (${result.UsedPercent}% usado)`;
        
        if (result.TotalGB < 16) {
            warnings.push('RAM insuficiente (menos de 16GB)');
            recommendations.push('Se recomienda 16GB de RAM para FiveM');
        }
    }
    
    updateCounters();
    updateRecommendations();
    hideLoading();
}

async function analyzeCPU() {
    showLoading('Analizando CPU...');
    addConsoleLine('Analizando procesador...', 'info');
    
    const result = await apiCall('detect/cpu');
    
    if (result) {
        addConsoleLine(`CPU: ${result.Name}`, 'success');
        addConsoleLine(`  Núcleos: ${result.Cores}`, 'info');
        addConsoleLine(`  Hilos: ${result.Threads}`, 'info');
        addConsoleLine(`  Velocidad: ${result.MaxSpeed} MHz`, 'info');
        document.getElementById('cpu-info').textContent = result.Name;
    }
    
    hideLoading();
}

async function checkTemperatures() {
    showLoading('Obteniendo temperaturas...');
    addConsoleLine('Obteniendo temperaturas del sistema...', 'info');
    
    const result = await apiCall('detect/temperatures');
    
    if (result) {
        if (result.cpu.current) {
            addConsoleLine(`CPU: ${result.cpu.current}°C (${result.cpu.status})`, 
                result.cpu.status === 'normal' ? 'success' : 'warning');
            document.getElementById('cpu-temp').textContent = `${result.cpu.current}°C`;
        } else {
            addConsoleLine('CPU: No disponible', 'info');
            document.getElementById('cpu-temp').textContent = 'N/A';
        }
        
        if (result.gpu.current) {
            addConsoleLine(`GPU: ${result.gpu.current}°C (${result.gpu.status})`, 
                result.gpu.status === 'normal' ? 'success' : 'warning');
            document.getElementById('gpu-temp').textContent = `${result.gpu.current}°C`;
        } else {
            addConsoleLine('GPU: No disponible', 'info');
            document.getElementById('gpu-temp').textContent = 'N/A';
        }
        
        if (result.warnings && result.warnings.length > 0) {
            result.warnings.forEach(w => {
                warnings.push(w);
                addConsoleLine(`⚠ ${w}`, 'warning');
            });
        }
        
        updateCounters();
    }
    
    hideLoading();
}

async function testNetwork() {
    showLoading('Probando conexión de red...');
    addConsoleLine('Probando conexión de red...', 'info');
    
    const result = await apiCall('detect/network');
    
    if (result) {
        addConsoleLine(`Estado: ${result.Status}`, result.Status === 'OK' ? 'success' : 'warning');
        addConsoleLine(`Ping: ${result.Ping}ms`, 'info');
        document.getElementById('network-status').textContent = `${result.Status} (${result.Ping}ms)`;
        
        if (result.Ping > 100) {
            warnings.push('Latencia alta (>100ms)');
        }
    }
    
    updateCounters();
    hideLoading();
}

async function testPacketLoss() {
    showLoading('Probando packet loss...');
    addConsoleLine('Realizando test de packet loss...', 'info');
    
    const result = await apiCall('detect/packetloss');
    
    if (result) {
        addConsoleLine(`Packet Loss Promedio: ${result.average_loss}%`, 
            result.average_loss === 0 ? 'success' : 'warning');
        document.getElementById('packet-loss').textContent = `${result.average_loss}%`;
        
        if (result.tests) {
            result.tests.forEach(test => {
                addConsoleLine(`  ${test.name}: ${test.packet_loss}%`, 
                    test.packet_loss === 0 ? 'success' : 'warning');
            });
        }
        
        if (result.recommendations) {
            result.recommendations.forEach(r => recommendations.push(r));
        }
        
        updateRecommendations();
    }
    
    hideLoading();
}

async function analyzeLogs() {
    showLoading('Analizando logs de FiveM...');
    addConsoleLine('Analizando logs de FiveM...', 'info');
    
    const result = await apiCall('analyze/logs');
    
    if (result) {
        addConsoleLine(`Errores encontrados: ${result.ErrorCount || 0}`, 
            (result.ErrorCount || 0) === 0 ? 'success' : 'warning');
        
        if (result.Errors && result.Errors.length > 0) {
            result.Errors.slice(0, 5).forEach(err => {
                addConsoleLine(`  - ${err.Error}`, 'error');
                criticalIssues.push(err.Error);
            });
        }
        
        if (result.Recommendations) {
            result.Recommendations.forEach(r => recommendations.push(r));
        }
        
        updateCounters();
        updateRecommendations();
    }
    
    hideLoading();
}

async function analyzeErrorsAdvanced() {
    showLoading('Análisis avanzado de errores...');
    addConsoleLine('Realizando análisis avanzado de errores...', 'info');
    
    const result = await apiCall('analyze/errors/advanced');
    
    if (result) {
        addConsoleLine(`Total errores: ${result.total_errors}`, 'info');
        addConsoleLine(`  Críticos: ${result.critical}`, result.critical > 0 ? 'error' : 'success');
        addConsoleLine(`  Altos: ${result.high}`, result.high > 0 ? 'warning' : 'success');
        addConsoleLine(`  Medios: ${result.medium}`, 'info');
        
        if (result.errors_found && result.errors_found.length > 0) {
            result.errors_found.forEach(err => {
                addConsoleLine(`[${err.severity.toUpperCase()}] ${err.description}`, 
                    err.severity === 'critical' ? 'error' : 'warning');
                err.solutions.forEach(sol => {
                    addConsoleLine(`  → ${sol}`, 'info');
                    recommendations.push(sol);
                });
            });
        }
        
        updateCounters();
        updateRecommendations();
    }
    
    hideLoading();
}

async function analyzeCrashDumps() {
    showLoading('Analizando crash dumps...');
    addConsoleLine('Analizando crash dumps...', 'info');
    
    const result = await apiCall('analyze/crashdumps');
    
    if (result) {
        addConsoleLine(`Crash dumps encontrados: ${result.dumps_found ? result.dumps_found.length : 0}`, 'info');
        
        if (result.analysis && result.analysis.length > 0) {
            result.analysis.forEach(a => {
                addConsoleLine(`  ${a.file} (${a.date})`, 'warning');
                a.possible_causes.forEach(c => {
                    addConsoleLine(`    - ${c}`, 'info');
                });
            });
        }
        
        if (result.recommendations) {
            result.recommendations.forEach(r => {
                recommendations.push(r);
                addConsoleLine(`  → ${r}`, 'info');
            });
        }
        
        updateRecommendations();
    }
    
    hideLoading();
}

async function detectMods() {
    showLoading('Detectando mods...');
    addConsoleLine('Detectando mods de GTA V...', 'info');
    
    const result = await apiCall('detect/mods');
    
    if (result) {
        if (result.ModsFound && result.ModsFound.length > 0) {
            addConsoleLine(`⚠ Mods encontrados: ${result.ModsFound.length}`, 'warning');
            result.ModsFound.forEach(mod => {
                addConsoleLine(`  - ${mod}`, 'warning');
                warnings.push(`Mod detectado: ${mod}`);
            });
            recommendations.push('Desactiva los mods antes de jugar FiveM');
        } else {
            addConsoleLine('✓ No se encontraron mods', 'success');
        }
        
        updateCounters();
        updateRecommendations();
    }
    
    hideLoading();
}

async function detectConflicts() {
    showLoading('Detectando software conflictivo...');
    addConsoleLine('Detectando software conflictivo...', 'info');
    
    const result = await apiCall('detect/conflicts');
    
    if (result) {
        if (result.ConflictsFound && result.ConflictsFound.length > 0) {
            addConsoleLine(`⚠ Software conflictivo: ${result.ConflictsFound.length}`, 'warning');
            result.ConflictsFound.forEach(c => {
                addConsoleLine(`  - ${c}`, 'warning');
                warnings.push(`Software conflictivo: ${c}`);
            });
        } else {
            addConsoleLine('✓ No se encontró software conflictivo', 'success');
        }
        
        updateCounters();
    }
    
    hideLoading();
}

async function detectOverlays() {
    showLoading('Detectando overlays conflictivos...');
    addConsoleLine('Detectando overlays conflictivos...', 'info');
    
    const result = await apiCall('detect/overlays');
    
    if (result) {
        if (result.overlays_found && result.overlays_found.length > 0) {
            addConsoleLine(`⚠ Overlays detectados: ${result.overlays_found.length}`, 'warning');
            result.overlays_found.forEach(o => {
                addConsoleLine(`  - ${o.name} (${o.status})`, 'warning');
                warnings.push(`Overlay: ${o.name}`);
            });
        } else {
            addConsoleLine('✓ No se encontraron overlays conflictivos', 'success');
        }
        
        if (result.recommendations) {
            result.recommendations.forEach(r => recommendations.push(r));
        }
        
        updateCounters();
        updateRecommendations();
    }
    
    hideLoading();
}

async function detectAntivirus() {
    showLoading('Detectando antivirus...');
    addConsoleLine('Detectando antivirus instalado...', 'info');
    
    const result = await apiCall('detect/antivirus');
    
    if (result) {
        if (result.Installed && result.Installed.length > 0) {
            result.Installed.forEach(av => {
                addConsoleLine(`Antivirus: ${av}`, 'info');
            });
        }
        
        if (result.Recommendations) {
            result.Recommendations.forEach(r => {
                recommendations.push(r);
                addConsoleLine(`  → ${r}`, 'info');
            });
        }
        
        updateRecommendations();
    }
    
    hideLoading();
}

async function checkDirectX() {
    showLoading('Verificando DirectX...');
    addConsoleLine('Verificando DirectX...', 'info');
    
    const result = await apiCall('detect/directx');
    
    if (result) {
        addConsoleLine(`DirectX: ${result.feature_level || result.version || 'Desconocido'}`, 
            result.status === 'excellent' || result.status === 'good' ? 'success' : 'warning');
        document.getElementById('directx-status').textContent = result.feature_level || 'OK';
        
        if (result.recommendations) {
            result.recommendations.forEach(r => recommendations.push(r));
        }
        
        updateRecommendations();
    }
    
    hideLoading();
}

async function checkVCRedist() {
    showLoading('Verificando Visual C++ Redistributables...');
    addConsoleLine('Verificando Visual C++ Redistributables...', 'info');
    
    const result = await apiCall('detect/vcredist');
    
    if (result) {
        addConsoleLine(`Estado: ${result.status}`, 
            result.status === 'complete' ? 'success' : 'warning');
        document.getElementById('vcredist-status').textContent = 
            result.status === 'complete' ? 'OK' : 'Incompleto';
        
        if (result.installed && result.installed.length > 0) {
            addConsoleLine(`Instalados: ${result.installed.length}`, 'info');
        }
        
        if (result.missing && result.missing.length > 0) {
            result.missing.forEach(m => {
                addConsoleLine(`  ⚠ Falta: ${m}`, 'warning');
                warnings.push(`Falta: ${m}`);
            });
        }
        
        if (result.recommendations) {
            result.recommendations.forEach(r => recommendations.push(r));
        }
        
        updateCounters();
        updateRecommendations();
    }
    
    hideLoading();
}

async function runBenchmark() {
    showLoading('Ejecutando benchmark...');
    addConsoleLine('Ejecutando benchmark del sistema...', 'info');
    
    const result = await apiCall('benchmark');
    
    if (result) {
        benchmarkResult = result;
        addConsoleLine(`Puntuación General: ${result.overall_score}/100 (${result.rating})`, 'success');
        addConsoleLine(`  CPU: ${result.cpu_score}/100`, 'info');
        addConsoleLine(`  Memoria: ${result.memory_score}/100`, 'info');
        addConsoleLine(`  Disco: ${result.disk_score}/100`, 'info');
        
        if (result.details) {
            if (result.details.disk_write_speed) {
                addConsoleLine(`  Velocidad Escritura: ${result.details.disk_write_speed} MB/s`, 'info');
            }
            if (result.details.disk_read_speed) {
                addConsoleLine(`  Velocidad Lectura: ${result.details.disk_read_speed} MB/s`, 'info');
            }
        }
        
        addConsoleLine(`FiveM Ready: ${result.fivem_ready ? 'Sí' : 'No'}`, 
            result.fivem_ready ? 'success' : 'warning');
        
        updateCounters();
    }
    
    hideLoading();
}

// ============= REPARACIONES =============

async function killProcesses() {
    showLoading('Terminando procesos...');
    addConsoleLine('Terminando procesos de FiveM...', 'info');
    
    const result = await apiCall('repair/kill');
    
    if (result && result.success) {
        addConsoleLine('✓ Procesos terminados correctamente', 'success');
        repairs.push('Procesos de FiveM terminados');
        updateCounters();
    }
    
    hideLoading();
}

async function clearCacheSelective() {
    showLoading('Limpiando caché selectiva...');
    addConsoleLine('Limpiando caché selectiva de FiveM...', 'info');
    
    const result = await apiCall('repair/cache/selective');
    
    if (result) {
        addConsoleLine(`✓ Caché limpiada: ${result.cleaned_mb || 0} MB liberados`, 'success');
        repairs.push('Caché selectiva limpiada');
        updateCounters();
    }
    
    hideLoading();
}

async function clearCacheComplete() {
    showLoading('Limpiando caché completa...');
    addConsoleLine('Limpiando caché completa de FiveM...', 'info');
    
    const result = await apiCall('repair/cache/complete');
    
    if (result) {
        addConsoleLine(`✓ Caché completa limpiada: ${result.cleaned_mb || 0} MB liberados`, 'success');
        repairs.push('Caché completa limpiada');
        updateCounters();
    }
    
    hideLoading();
}

async function removeDLLs() {
    showLoading('Eliminando DLLs conflictivas...');
    addConsoleLine('Eliminando DLLs conflictivas...', 'info');
    
    const result = await apiCall('repair/dlls');
    
    if (result && result.success) {
        addConsoleLine('✓ DLLs conflictivas eliminadas', 'success');
        repairs.push('DLLs conflictivas eliminadas');
        updateCounters();
    }
    
    hideLoading();
}

async function cleanV8DLLs() {
    showLoading('Limpiando v8 DLLs...');
    addConsoleLine('Limpiando v8 DLLs de System32...', 'info');
    
    const result = await apiCall('repair/v8dlls');
    
    if (result) {
        if (result.removed && result.removed.length > 0) {
            addConsoleLine(`✓ ${result.removed.length} DLLs eliminadas`, 'success');
            result.removed.forEach(dll => addConsoleLine(`  - ${dll}`, 'info'));
            repairs.push('v8 DLLs eliminadas');
        } else {
            addConsoleLine('✓ No se encontraron v8 DLLs conflictivas', 'success');
        }
        updateCounters();
    }
    
    hideLoading();
}

async function cleanROSFiles() {
    showLoading('Limpiando archivos ROS...');
    addConsoleLine('Limpiando archivos de Rockstar Online Services...', 'info');
    
    const result = await apiCall('repair/rosfiles');
    
    if (result && result.success) {
        addConsoleLine('✓ Archivos ROS limpiados', 'success');
        repairs.push('Archivos ROS limpiados');
        updateCounters();
    }
    
    hideLoading();
}

async function repairROS() {
    showLoading('Reparando ROS...');
    addConsoleLine('Reparando autenticación de Rockstar...', 'info');
    
    const result = await apiCall('repair/ros');
    
    if (result && result.success) {
        addConsoleLine('✓ Autenticación ROS reparada', 'success');
        repairs.push('Autenticación ROS reparada');
        updateCounters();
    }
    
    hideLoading();
}

async function disableMods() {
    showLoading('Desactivando mods...');
    addConsoleLine('Desactivando mods de GTA V...', 'info');
    
    const result = await apiCall('repair/mods/disable');
    
    if (result && result.success) {
        addConsoleLine(`✓ ${result.disabled_count || 0} mods desactivados`, 'success');
        repairs.push('Mods desactivados');
        updateCounters();
    }
    
    hideLoading();
}

async function closeConflicts() {
    showLoading('Cerrando software conflictivo...');
    addConsoleLine('Cerrando software conflictivo...', 'info');
    
    const result = await apiCall('repair/conflicts/close');
    
    if (result && result.success) {
        addConsoleLine('✓ Software conflictivo cerrado', 'success');
        repairs.push('Software conflictivo cerrado');
        updateCounters();
    }
    
    hideLoading();
}

// ============= OPTIMIZACIÓN =============

async function configureFirewall() {
    showLoading('Configurando firewall...');
    addConsoleLine('Configurando reglas de firewall para FiveM...', 'info');
    
    const result = await apiCall('optimize/firewall');
    
    if (result && result.success) {
        addConsoleLine('✓ Reglas de firewall configuradas', 'success');
        repairs.push('Firewall configurado');
        updateCounters();
    }
    
    hideLoading();
}

async function configureDefender() {
    showLoading('Configurando exclusiones...');
    addConsoleLine('Configurando exclusiones de Windows Defender...', 'info');
    
    const result = await apiCall('optimize/defender');
    
    if (result && result.success) {
        addConsoleLine('✓ Exclusiones de Defender configuradas', 'success');
        repairs.push('Exclusiones de Defender configuradas');
        updateCounters();
    }
    
    hideLoading();
}

async function optimizePageFile() {
    showLoading('Optimizando paginación...');
    addConsoleLine('Optimizando archivo de paginación...', 'info');
    
    const result = await apiCall('optimize/pagefile');
    
    if (result && result.success) {
        addConsoleLine('✓ Archivo de paginación optimizado', 'success');
        repairs.push('Paginación optimizada');
        updateCounters();
    }
    
    hideLoading();
}

async function optimizeGraphics() {
    showLoading('Optimizando gráficos...');
    addConsoleLine('Optimizando configuración gráfica...', 'info');
    
    const result = await apiCall('optimize/graphics');
    
    if (result) {
        if (result.success) {
            addConsoleLine('✓ Configuración gráfica optimizada', 'success');
            repairs.push('Gráficos optimizados');
        } else {
            addConsoleLine(`⚠ ${result.error || 'Error optimizando gráficos'}`, 'warning');
        }
        updateCounters();
    }
    
    hideLoading();
}

async function configureTextureBudget() {
    showLoading('Configurando Texture Budget...');
    addConsoleLine('Configurando Extended Texture Budget automáticamente...', 'info');
    
    const result = await apiCall('optimize/texturebudget');
    
    if (result) {
        addConsoleLine(`VRAM detectada: ${result.vram_detected} GB`, 'info');
        addConsoleLine(`Texture Budget recomendado: ${result.recommended_budget}%`, 'info');
        
        if (result.success) {
            addConsoleLine('✓ Texture Budget configurado', 'success');
            repairs.push(`Texture Budget: ${result.recommended_budget}%`);
            recommendations.push(`Ajusta "Extended Texture Budget" a ${result.recommended_budget}% en FiveM`);
        }
        
        updateCounters();
        updateRecommendations();
    }
    
    hideLoading();
}

async function optimizeWindows() {
    showLoading('Optimizando Windows...');
    addConsoleLine('Aplicando optimizaciones de Windows para gaming...', 'info');
    
    const result = await apiCall('optimize/windows');
    
    if (result) {
        if (result.optimizations && result.optimizations.length > 0) {
            result.optimizations.forEach(opt => {
                addConsoleLine(`✓ ${opt}`, 'success');
                repairs.push(opt);
            });
        }
        
        if (result.failed && result.failed.length > 0) {
            result.failed.forEach(f => {
                addConsoleLine(`⚠ ${f}`, 'warning');
            });
        }
        
        if (result.requires_restart) {
            addConsoleLine('⚠ Se requiere reiniciar el PC para aplicar algunos cambios', 'warning');
            recommendations.push('Reinicia el PC para aplicar todas las optimizaciones');
        }
        
        updateCounters();
        updateRecommendations();
    }
    
    hideLoading();
}

async function optimizeDNS() {
    showLoading('Optimizando DNS...');
    addConsoleLine('Analizando y optimizando DNS...', 'info');
    
    const result = await apiCall('optimize/dns');
    
    if (result) {
        if (result.dns_test_results && result.dns_test_results.length > 0) {
            result.dns_test_results.forEach(dns => {
                addConsoleLine(`${dns.name}: ${dns.latency_ms}ms`, 
                    dns.status === 'ok' ? 'success' : 'info');
            });
        }
        
        if (result.best_dns) {
            addConsoleLine(`✓ Mejor DNS: ${result.best_dns}`, 'success');
        }
        
        updateRecommendations();
    }
    
    hideLoading();
}

// ============= MODALES =============

function showDetailsModal(type) {
    const modal = document.getElementById('details-modal');
    const title = document.getElementById('details-modal-title');
    const body = document.getElementById('details-modal-body');
    
    let content = '';
    
    switch(type) {
        case 'critical':
            title.textContent = 'Problemas Críticos';
            if (criticalIssues.length === 0) {
                content = '<p class="no-items">No hay problemas críticos detectados</p>';
            } else {
                content = '<ul class="details-list critical">';
                criticalIssues.forEach(issue => {
                    content += `<li>${issue}</li>`;
                });
                content += '</ul>';
            }
            break;
            
        case 'warnings':
            title.textContent = 'Advertencias';
            if (warnings.length === 0) {
                content = '<p class="no-items">No hay advertencias</p>';
            } else {
                content = '<ul class="details-list warning">';
                warnings.forEach(warning => {
                    content += `<li>${warning}</li>`;
                });
                content += '</ul>';
            }
            break;
            
        case 'repairs':
            title.textContent = 'Reparaciones Aplicadas';
            if (repairs.length === 0) {
                content = '<p class="no-items">No se han aplicado reparaciones</p>';
            } else {
                content = '<ul class="details-list success">';
                repairs.forEach(repair => {
                    content += `<li>✓ ${repair}</li>`;
                });
                content += '</ul>';
            }
            break;
            
        case 'benchmark':
            title.textContent = 'Resultados del Benchmark';
            if (!benchmarkResult) {
                content = '<p class="no-items">Ejecuta un benchmark para ver los resultados</p>';
            } else {
                content = `
                    <div class="benchmark-results">
                        <div class="benchmark-score-main">
                            <span class="score">${benchmarkResult.overall_score}</span>
                            <span class="max">/100</span>
                        </div>
                        <p class="rating">${benchmarkResult.rating}</p>
                        <div class="benchmark-details">
                            <div class="benchmark-item">
                                <span>CPU</span>
                                <div class="progress-bar">
                                    <div class="progress" style="width: ${benchmarkResult.cpu_score}%"></div>
                                </div>
                                <span>${benchmarkResult.cpu_score}/100</span>
                            </div>
                            <div class="benchmark-item">
                                <span>Memoria</span>
                                <div class="progress-bar">
                                    <div class="progress" style="width: ${benchmarkResult.memory_score}%"></div>
                                </div>
                                <span>${benchmarkResult.memory_score}/100</span>
                            </div>
                            <div class="benchmark-item">
                                <span>Disco</span>
                                <div class="progress-bar">
                                    <div class="progress" style="width: ${benchmarkResult.disk_score}%"></div>
                                </div>
                                <span>${benchmarkResult.disk_score}/100</span>
                            </div>
                        </div>
                        <p class="fivem-ready ${benchmarkResult.fivem_ready ? 'yes' : 'no'}">
                            FiveM Ready: ${benchmarkResult.fivem_ready ? '✓ Sí' : '✗ No'}
                        </p>
                    </div>
                `;
            }
            break;
    }
    
    body.innerHTML = content;
    modal.classList.add('active');
}

function showAdvancedRepairModal() {
    document.getElementById('advanced-repair-modal').classList.add('active');
}

function showProfilesModal() {
    document.getElementById('profiles-modal').classList.add('active');
}

function showCitizenFXModal() {
    document.getElementById('citizenfx-modal').classList.add('active');
}

function showLaunchParamsModal() {
    document.getElementById('launch-params-modal').classList.add('active');
}

async function showBackupsModal() {
    document.getElementById('backups-modal').classList.add('active');
    document.getElementById('backups-list').innerHTML = '<p>Cargando backups...</p>';
    
    const result = await apiCall('backups', 'GET');
    
    if (result && result.backups && result.backups.length > 0) {
        let html = '<div class="backups-grid">';
        result.backups.forEach(backup => {
            html += `
                <div class="backup-item">
                    <div class="backup-info">
                        <span class="backup-name">${backup.name}</span>
                        <span class="backup-date">${backup.date}</span>
                        <span class="backup-size">${backup.size_mb} MB</span>
                    </div>
                    <button class="btn-small" onclick="restoreBackup('${backup.path}')">Restaurar</button>
                </div>
            `;
        });
        html += '</div>';
        document.getElementById('backups-list').innerHTML = html;
    } else {
        document.getElementById('backups-list').innerHTML = '<p class="no-items">No hay backups disponibles</p>';
    }
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
}

// ============= FUNCIONES DE MODALES =============

function selectAllRepairs() {
    document.querySelectorAll('#repair-options input[type="checkbox"]').forEach(cb => cb.checked = true);
}

function deselectAllRepairs() {
    document.querySelectorAll('#repair-options input[type="checkbox"]').forEach(cb => cb.checked = false);
}

async function runAdvancedRepair() {
    const selected = [];
    document.querySelectorAll('#repair-options input[type="checkbox"]:checked').forEach(cb => {
        selected.push(parseInt(cb.value));
    });
    
    if (selected.length === 0) {
        alert('Selecciona al menos una reparación');
        return;
    }
    
    closeModal('advanced-repair-modal');
    showLoading('Ejecutando reparaciones avanzadas...');
    addConsoleLine(`Ejecutando ${selected.length} reparaciones seleccionadas...`, 'info');
    
    const result = await apiCall('repair/advanced', 'POST', { repairs: selected });
    
    if (result) {
        if (result.results) {
            result.results.forEach(r => {
                if (r.success) {
                    addConsoleLine(`✓ ${r.name}`, 'success');
                    repairs.push(r.name);
                } else {
                    addConsoleLine(`✗ ${r.name}: ${r.error || 'Error'}`, 'error');
                }
            });
        }
        updateCounters();
    }
    
    hideLoading();
}

function selectProfile(profile) {
    selectedProfile = profile;
    document.querySelectorAll('.profile-card').forEach(card => card.classList.remove('selected'));
    event.currentTarget.classList.add('selected');
}

async function applySelectedProfile() {
    closeModal('profiles-modal');
    showLoading(`Aplicando perfil ${selectedProfile}...`);
    addConsoleLine(`Aplicando perfil de rendimiento: ${selectedProfile}`, 'info');
    
    const result = await apiCall('profiles/apply', 'POST', { profile: selectedProfile });
    
    if (result && result.success) {
        addConsoleLine('✓ Perfil aplicado correctamente', 'success');
        if (result.changes) {
            result.changes.forEach(c => addConsoleLine(`  - ${c}`, 'info'));
        }
        repairs.push(`Perfil ${selectedProfile} aplicado`);
        updateCounters();
    }
    
    hideLoading();
}

async function saveCitizenFXConfig() {
    const settings = {
        UpdateChannel: document.getElementById('update-channel').value,
        GameBuild: document.getElementById('game-build').value,
        DisableNVSP: document.getElementById('disable-nvsp').checked ? '1' : '0',
        EnableFullMemoryDump: document.getElementById('enable-dumps').checked ? '1' : '0'
    };
    
    closeModal('citizenfx-modal');
    showLoading('Guardando configuración...');
    
    const result = await apiCall('config/citizenfx', 'POST', settings);
    
    if (result && result.success) {
        addConsoleLine('✓ Configuración de CitizenFX.ini guardada', 'success');
        repairs.push('CitizenFX.ini configurado');
        updateCounters();
    }
    
    hideLoading();
}

async function saveLaunchParams() {
    const params = [];
    if (document.getElementById('param-novid').checked) params.push('-novid');
    if (document.getElementById('param-threads').checked) params.push('-threads 4');
    if (document.getElementById('param-memleakfix').checked) params.push('-memleakfix');
    if (document.getElementById('param-high').checked) params.push('-high');
    
    closeModal('launch-params-modal');
    showLoading('Guardando parámetros...');
    
    const result = await apiCall('config/launchparams', 'POST', { parameters: params });
    
    if (result && result.success) {
        addConsoleLine('✓ Parámetros de lanzamiento guardados', 'success');
        addConsoleLine(`  Parámetros: ${params.join(' ')}`, 'info');
        repairs.push('Parámetros de lanzamiento configurados');
        updateCounters();
    }
    
    hideLoading();
}

async function restoreBackup(path) {
    if (!confirm('¿Estás seguro de que deseas restaurar este backup?')) return;
    
    showLoading('Restaurando backup...');
    
    const result = await apiCall('backups/restore', 'POST', { path: path });
    
    if (result && result.success) {
        addConsoleLine('✓ Backup restaurado correctamente', 'success');
    } else {
        addConsoleLine('✗ Error restaurando backup', 'error');
    }
    
    hideLoading();
}

async function generateReport() {
    showLoading('Generando reporte...');
    addConsoleLine('Generando reporte HTML...', 'info');
    
    const result = await apiCall('report/generate');
    
    if (result && result.path) {
        addConsoleLine(`✓ Reporte generado: ${result.path}`, 'success');
        window.open(`/api/report/view?path=${encodeURIComponent(result.path)}`, '_blank');
    }
    
    hideLoading();
}

async function exportConfig() {
    showLoading('Exportando configuración...');
    addConsoleLine('Exportando configuración...', 'info');
    
    const result = await apiCall('config/export');
    
    if (result && result.success) {
        addConsoleLine(`✓ Configuración exportada: ${result.path}`, 'success');
    }
    
    hideLoading();
}

// ============= UTILIDADES =============

function processResults(result) {
    // Procesar información del sistema
    if (result.gpu && result.gpu.length > 0) {
        document.getElementById('gpu-info').textContent = result.gpu[0].Name;
    }
    if (result.ram) {
        document.getElementById('ram-info').textContent = `${result.ram.TotalGB} GB`;
    }
    if (result.cpu) {
        document.getElementById('cpu-info').textContent = result.cpu.Name;
    }
    
    // Procesar resumen
    if (result.summary) {
        if (result.summary.CriticalIssues) {
            for (let i = 0; i < result.summary.CriticalIssues; i++) {
                criticalIssues.push('Problema crítico detectado');
            }
        }
        if (result.summary.Warnings) {
            for (let i = 0; i < result.summary.Warnings; i++) {
                warnings.push('Advertencia detectada');
            }
        }
        if (result.summary.Recommendations) {
            result.summary.Recommendations.forEach(r => recommendations.push(r));
        }
        if (result.summary.RepairsApplied) {
            result.summary.RepairsApplied.forEach(r => repairs.push(r));
        }
    }
    
    updateCounters();
    updateRecommendations();
}

async function refreshStatus() {
    addConsoleLine('Actualizando estado...', 'info');
    const result = await apiCall('status', 'GET');
    if (result) {
        document.getElementById('status-value').textContent = result.status || 'Listo';
        addConsoleLine('Estado actualizado', 'success');
    }
}

// Inicialización
document.addEventListener('DOMContentLoaded', function() {
    refreshStatus();
});
