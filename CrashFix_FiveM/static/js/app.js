// FiveM Diagnostic Tool v6.2 PRO - JavaScript
// Optimizado: Diagnostico Inteligente unificado + Info Sistema corregida

// ============= ESTADO GLOBAL =============

let criticalIssues = [];
let warnings = [];
let repairs = [];
let recommendations = [];
let benchmarkResult = null;
let selectedProfile = 'medium';

// ============= UI HELPERS =============

function showLoading(text = 'Procesando...') {
    document.getElementById('loading-text').textContent = text;
    document.getElementById('loading-overlay').classList.add('active');
}

function hideLoading() {
    document.getElementById('loading-overlay').classList.remove('active');
}

function addConsoleLine(message, type = 'info') {
    const consoleEl = document.getElementById('console-output');
    const time = new Date().toLocaleTimeString('es-ES', { hour12: false });
    const line = document.createElement('div');
    line.className = `console-line ${type}`;
    line.innerHTML = `<span class="console-time">[${time}]</span><span class="console-msg">${message}</span>`;
    consoleEl.appendChild(line);
    consoleEl.scrollTop = consoleEl.scrollHeight;
}

function clearConsole() {
    document.getElementById('console-output').innerHTML = '';
    addConsoleLine('Consola limpiada', 'info');
}

function resetDiagnosticState() {
    criticalIssues = [];
    warnings = [];
    recommendations = [];
    updateCounters();
    updateRecommendations();
}

function updateCounters() {
    document.getElementById('critical-count').textContent = criticalIssues.length;
    document.getElementById('warnings-count').textContent = warnings.length;
    document.getElementById('repairs-count').textContent = repairs.length;
    if (benchmarkResult) {
        document.getElementById('benchmark-score').textContent = benchmarkResult.overall_score + '/100';
    }
}

function updateRepairsList() {
    const container = document.getElementById('repairs-list');
    if (repairs.length === 0) {
        container.innerHTML = '<div class="repair-item empty">Ninguna reparacion aplicada aun</div>';
    } else {
        container.innerHTML = repairs.map(r =>
            `<div class="repair-item">&check; ${r}</div>`
        ).join('');
    }
}

function updateRecommendations() {
    const container = document.getElementById('recommendations');
    if (recommendations.length === 0) {
        container.innerHTML = '<div class="recommendation-item empty">Ejecuta un diagnostico para ver recomendaciones</div>';
    } else {
        container.innerHTML = recommendations.map(r =>
            `<div class="recommendation-item">&rarr; ${r}</div>`
        ).join('');
    }
}

/**
 * Actualiza la tarjeta de Informacion del Sistema con los datos proporcionados.
 * Centraliza la logica de renderizado para evitar duplicacion.
 */
function updateSystemInfoCard(data) {
    if (!data) return;

    // GPU
    const gpuData = data.gpu || (data.Hardware && data.Hardware.GPU);
    if (gpuData && Array.isArray(gpuData) && gpuData.length > 0) {
        const gpu = gpuData[0];
        const gpuText = gpu.VRAM_GB > 0
            ? `${gpu.Name} (${gpu.VRAM_GB}GB)`
            : gpu.Name;
        document.getElementById('gpu-info').textContent = gpuText;
    }

    // RAM
    const ramData = data.ram || (data.Hardware && data.Hardware.RAM);
    if (ramData && ramData.TotalGB !== undefined) {
        const usedText = ramData.UsedPercent !== undefined ? ` (${ramData.UsedPercent}% usado)` : '';
        document.getElementById('ram-info').textContent = `${ramData.TotalGB} GB${usedText}`;
    }

    // CPU
    const cpuData = data.cpu || (data.Hardware && data.Hardware.CPU);
    if (cpuData && cpuData.Name) {
        const coresText = cpuData.Cores ? ` (${cpuData.Cores}C/${cpuData.Threads}T)` : '';
        document.getElementById('cpu-info').textContent = cpuData.Name + coresText;
    }

    // Sistema Operativo
    const osData = data.os || (data.Hardware && data.Hardware.os);
    if (osData && osData.Name) {
        const archText = osData.Architecture ? ` ${osData.Architecture}` : '';
        document.getElementById('os-info').textContent = osData.Name + archText;
    }

    // GTA V
    const gtaData = data.gta || data.GTA;
    if (gtaData) {
        const gtaEl = document.getElementById('gta-status');
        if (gtaData.Path) {
            const platform = gtaData.Platform ? ` (${gtaData.Platform})` : '';
            gtaEl.textContent = gtaData.Path + platform;
            gtaEl.style.color = 'var(--success)';
            gtaEl.title = gtaData.Path;
        } else {
            gtaEl.textContent = 'No encontrado';
            gtaEl.style.color = 'var(--error)';
        }
    }

    // FiveM
    const fivemData = data.fivem;
    if (fivemData) {
        const fivemEl = document.getElementById('fivem-status');
        if (fivemData.Found) {
            fivemEl.textContent = 'Instalado';
            fivemEl.style.color = 'var(--success)';
        } else {
            fivemEl.textContent = 'No encontrado';
            fivemEl.style.color = 'var(--warning)';
        }
    }

    // Red
    const netData = data.network;
    if (netData) {
        const netEl = document.getElementById('network-status');
        netEl.textContent = `${netData.Status} (${netData.Ping}ms)`;
    }

    // DirectX
    if (data.directx) {
        const dxEl = document.getElementById('directx-status');
        dxEl.textContent = data.directx.feature_level || data.directx.version || 'Desconocido';
    }

    // VC++ Redist
    if (data.vcredist) {
        const vcEl = document.getElementById('vcredist-status');
        vcEl.textContent = data.vcredist.status === 'complete' ? 'OK' : 'Incompleto';
    }
}

// ============= API =============

async function apiCall(endpoint, method = 'POST', data = null) {
    try {
        const options = {
            method,
            headers: { 'Content-Type': 'application/json' }
        };
        if (data) options.body = JSON.stringify(data);
        const response = await fetch(`/api/${endpoint}`, options);
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            addConsoleLine(`Error HTTP ${response.status}: ${err.error || response.statusText}`, 'error');
            return null;
        }
        return await response.json();
    } catch (error) {
        addConsoleLine(`Error de red: ${error.message}`, 'error');
        return null;
    }
}

// ============= PROCESS RESULTS =============

function processResults(result) {
    if (!result) return;

    // Actualizar tarjeta de info del sistema
    updateSystemInfoCard(result);

    // Summary — puede venir como result.summary o result.Summary
    const summary = result.summary || result.Summary;
    if (summary) {
        const critCount = summary.CriticalIssues || 0;
        const warnCount = summary.Warnings || 0;

        for (let i = 0; i < critCount; i++) criticalIssues.push('Problema critico detectado');
        for (let i = 0; i < warnCount; i++) warnings.push('Advertencia detectada');

        const recs = summary.Recommendations || [];
        recs.forEach(r => { if (!recommendations.includes(r)) recommendations.push(r); });

        const reps = summary.RepairsApplied || [];
        reps.forEach(r => { if (!repairs.includes(r)) repairs.push(r); });
    }

    updateCounters();
    updateRepairsList();
    updateRecommendations();
}

// ============= DIAGNOSTICO INTELIGENTE (UNIFICADO) =============

async function runSmartDiagnosis() {
    showLoading('Ejecutando Diagnostico Inteligente...');
    addConsoleLine('Iniciando Diagnostico Inteligente (analisis + reparacion automatica)...', 'info');
    resetDiagnosticState();

    const result = await apiCall('smart/diagnose-and-fix');
    if (result) {
        // Mostrar fases en consola
        (result.phases || []).forEach(phase => {
            const icon = phase.status === 'completed' ? '&check;' : '&cross;';
            addConsoleLine(`${icon} [${phase.name}] ${phase.status}`, phase.status === 'completed' ? 'success' : 'warn');
        });

        // Procesar resultados (actualiza tarjeta de info, contadores, etc.)
        processResults(result);

        // Mostrar reparaciones automaticas aplicadas
        const autoRepairs = result.auto_repairs || [];
        if (autoRepairs.length > 0) {
            addConsoleLine('--- Reparaciones automaticas ---', 'info');
            autoRepairs.forEach(ar => {
                addConsoleLine(`  &check; ${ar.action} (${ar.reason})`, 'success');
                if (!repairs.includes(ar.action)) repairs.push(ar.action);
            });
        }

        // Mostrar requisitos
        if (result.requirements && result.requirements.checks) {
            addConsoleLine('--- Requisitos del sistema ---', 'info');
            Object.entries(result.requirements.checks).forEach(([key, check]) => {
                const icon = check.passed ? '&check;' : '&cross;';
                addConsoleLine(`  ${icon} ${key}: ${check.current} (req: ${check.required})`,
                    check.passed ? 'success' : 'warn');
            });
        }

        updateCounters();
        updateRepairsList();
        updateRecommendations();
        addConsoleLine('&check; Diagnostico Inteligente completado', 'success');
    }
    hideLoading();
}

// ============= ACCIONES RAPIDAS (ORIGINALES - MANTENIDAS) =============

async function runQuickRepair() {
    showLoading('Ejecutando reparacion rapida...');
    addConsoleLine('Iniciando reparacion rapida...', 'info');
    const result = await apiCall('repair/quick');
    if (result) {
        addConsoleLine('&check; Reparacion rapida completada', 'success');
        (result.repairs_applied || []).forEach(r => {
            if (!repairs.includes(r)) repairs.push(r);
            addConsoleLine(`  &check; ${r}`, 'success');
        });
        (result.recommendations || []).forEach(r => {
            if (!recommendations.includes(r)) recommendations.push(r);
        });
        updateCounters();
        updateRepairsList();
        updateRecommendations();
    }
    hideLoading();
}

async function runCompleteDiagnostic() {
    showLoading('Ejecutando diagnostico completo...');
    addConsoleLine('Iniciando diagnostico completo...', 'info');
    resetDiagnosticState();
    const result = await apiCall('diagnostic/complete');
    if (result) {
        processResults(result);
        addConsoleLine('&check; Diagnostico completo finalizado', 'success');
    }
    hideLoading();
}

async function runFullDiagnosticV2() {
    showLoading('Ejecutando diagnostico PRO v2.0...');
    addConsoleLine('Iniciando diagnostico PRO v2.0 (10 fases)...', 'info');
    resetDiagnosticState();
    const result = await apiCall('diagnostic/full/v2');
    if (result) {
        (result.phases || []).forEach(phase => {
            addConsoleLine(`[${phase.name}] Estado: ${phase.status}`, 'info');
        });
        processResults(result);
        if (result.benchmark) {
            benchmarkResult = result.benchmark;
            addConsoleLine(`Benchmark: ${result.benchmark.overall_score}/100 (${result.benchmark.rating})`, 'success');
            updateCounters();
        }
        addConsoleLine('&check; Diagnostico PRO v2.0 completado', 'success');
    }
    hideLoading();
}

async function runDiagnoseAndRepair() {
    showLoading('Ejecutando diagnostico y reparacion...');
    addConsoleLine('Iniciando diagnostico + reparacion automatica...', 'info');
    resetDiagnosticState();
    const diagResult = await apiCall('diagnostic/complete');
    if (diagResult) processResults(diagResult);
    addConsoleLine('Aplicando reparaciones automaticas...', 'info');
    const repairResult = await apiCall('repair/quick');
    if (repairResult && repairResult.repairs_applied) {
        repairResult.repairs_applied.forEach(r => {
            if (!repairs.includes(r)) repairs.push(r);
            addConsoleLine(`  &check; ${r}`, 'success');
        });
    }
    updateCounters();
    updateRepairsList();
    updateRecommendations();
    addConsoleLine('&check; Diagnostico y reparacion completados', 'success');
    hideLoading();
}

// ============= DIAGNOSTICO =============

async function checkRequirements() {
    showLoading('Verificando requisitos del sistema...');
    addConsoleLine('Verificando requisitos del sistema...', 'info');
    const result = await apiCall('detect/requirements');
    if (result) {
        addConsoleLine(`Estado: ${result.status}`, result.status === 'ok' ? 'success' : 'warn');

        // Mostrar checks en consola
        Object.entries(result.checks || {}).forEach(([key, check]) => {
            const icon = check.passed ? '&check;' : '&cross;';
            addConsoleLine(`  ${icon} ${key}: ${check.current} (req: ${check.required})`,
                check.passed ? 'success' : 'error');
            if (!check.passed) criticalIssues.push(`${key}: ${check.current}`);
        });

        // Actualizar tarjeta de informacion del sistema con datos de hardware
        updateSystemInfoCard(result);

        // Recomendaciones
        (result.recommendations || []).forEach(r => {
            if (!recommendations.includes(r)) recommendations.push(r);
        });

        updateCounters();
        updateRecommendations();
    }
    hideLoading();
}

async function detectGTA() {
    showLoading('Detectando GTA V y FiveM...');
    addConsoleLine('Buscando instalacion de GTA V...', 'info');

    const [gtaResult, fivemResult] = await Promise.all([
        apiCall('detect/gtav'),
        apiCall('detect/fivem')
    ]);

    if (gtaResult) {
        const gtaEl = document.getElementById('gta-status');
        if (gtaResult.Path) {
            addConsoleLine(`&check; GTA V encontrado: ${gtaResult.Path}`, 'success');
            if (gtaResult.Platform) {
                addConsoleLine(`  Plataforma: ${gtaResult.Platform}`, 'info');
            }
            if (gtaResult.AllPaths && gtaResult.AllPaths.length > 1) {
                addConsoleLine(`  Instalaciones encontradas: ${gtaResult.AllPaths.length}`, 'info');
                gtaResult.AllPaths.forEach(p => {
                    addConsoleLine(`    - ${p.path} (${p.platform})`, 'info');
                });
            }
            const platform = gtaResult.Platform ? ` (${gtaResult.Platform})` : '';
            gtaEl.textContent = gtaResult.Path + platform;
            gtaEl.style.color = 'var(--success)';
            gtaEl.title = gtaResult.Path;
        } else {
            addConsoleLine('&cross; GTA V no encontrado', 'error');
            gtaEl.textContent = 'No encontrado';
            gtaEl.style.color = 'var(--error)';
            criticalIssues.push('GTA V no encontrado');
        }
    }

    if (fivemResult) {
        const fivemEl = document.getElementById('fivem-status');
        if (fivemResult.Found) {
            addConsoleLine('&check; FiveM instalado', 'success');
            fivemEl.textContent = 'Instalado';
            fivemEl.style.color = 'var(--success)';
        } else {
            addConsoleLine('&cross; FiveM no encontrado', 'warn');
            fivemEl.textContent = 'No encontrado';
            fivemEl.style.color = 'var(--warning)';
        }
    }

    updateCounters();
    hideLoading();
}

async function verifyGTAV() {
    showLoading('Verificando integridad de GTA V...');
    addConsoleLine('Verificando integridad de archivos de GTA V...', 'info');
    const result = await apiCall('verify/gtav');
    if (result) {
        addConsoleLine(`Archivos verificados: ${result.files_ok}/${result.files_checked}`, 'info');
        (result.files_missing || []).forEach(f => {
            addConsoleLine(`  Faltante: ${f}`, 'warn');
            warnings.push(`Archivo faltante: ${f}`);
        });
        addConsoleLine(result.status === 'ok' ? '&check; Integridad OK' : 'Problemas encontrados',
            result.status === 'ok' ? 'success' : 'warn');
        if (result.status !== 'ok') {
            recommendations.push('Verifica la integridad de archivos desde el launcher');
        }
        updateCounters();
        updateRecommendations();
    }
    hideLoading();
}

async function analyzeGPU() {
    showLoading('Analizando GPU...');
    addConsoleLine('Analizando tarjeta grafica...', 'info');
    const result = await apiCall('detect/gpu');
    if (result && result.length > 0) {
        const gpu = result[0];
        addConsoleLine(`GPU: ${gpu.Name}`, 'success');
        addConsoleLine(`  VRAM: ${gpu.VRAM_GB} GB | Driver: ${gpu.DriverVersion}`, 'info');
        document.getElementById('gpu-info').textContent = `${gpu.Name} (${gpu.VRAM_GB}GB)`;
        if (gpu.VRAM_GB < 4) {
            warnings.push('VRAM insuficiente (menos de 4GB)');
            recommendations.push('Se recomienda una GPU con al menos 4GB de VRAM');
        }
        updateCounters();
        updateRecommendations();
    }
    hideLoading();
}

async function analyzeRAM() {
    showLoading('Analizando RAM...');
    addConsoleLine('Analizando memoria RAM...', 'info');
    const result = await apiCall('detect/ram');
    if (result) {
        addConsoleLine(`RAM Total: ${result.TotalGB} GB | Disponible: ${result.AvailableGB} GB | Uso: ${result.UsedPercent}%`, 'info');
        document.getElementById('ram-info').textContent = `${result.TotalGB} GB (${result.UsedPercent}% usado)`;
        if (result.TotalGB < 16) {
            warnings.push('RAM insuficiente (menos de 16GB)');
            recommendations.push('Se recomienda 16GB de RAM para FiveM');
        }
        updateCounters();
        updateRecommendations();
    }
    hideLoading();
}

async function analyzeCPU() {
    showLoading('Analizando CPU...');
    addConsoleLine('Analizando procesador...', 'info');
    const result = await apiCall('detect/cpu');
    if (result) {
        addConsoleLine(`CPU: ${result.Name} | Nucleos: ${result.Cores} | Hilos: ${result.Threads}`, 'info');
        const coresText = result.Cores ? ` (${result.Cores}C/${result.Threads}T)` : '';
        document.getElementById('cpu-info').textContent = result.Name + coresText;
    }
    hideLoading();
}

async function checkTemperatures() {
    showLoading('Obteniendo temperaturas...');
    addConsoleLine('Obteniendo temperaturas del sistema...', 'info');
    const result = await apiCall('detect/temperatures');
    if (result) {
        const cpuTemp = result.cpu && result.cpu.current;
        const gpuTemp = result.gpu && result.gpu.current;
        addConsoleLine(`CPU: ${cpuTemp ? cpuTemp + ' C' : 'N/A'} | GPU: ${gpuTemp ? gpuTemp + ' C' : 'N/A'}`, 'info');
        document.getElementById('cpu-temp').textContent = cpuTemp ? `${cpuTemp} C` : 'N/A';
        document.getElementById('gpu-temp').textContent = gpuTemp ? `${gpuTemp} C` : 'N/A';
        (result.warnings || []).forEach(w => {
            warnings.push(w);
            addConsoleLine(`${w}`, 'warn');
        });
        updateCounters();
    }
    hideLoading();
}

async function testNetwork() {
    showLoading('Probando conexion de red...');
    addConsoleLine('Probando conexion de red...', 'info');
    const result = await apiCall('detect/network');
    if (result) {
        addConsoleLine(`Estado: ${result.Status} | Ping: ${result.Ping}ms`,
            result.Status === 'OK' ? 'success' : 'warn');
        document.getElementById('network-status').textContent = `${result.Status} (${result.Ping}ms)`;
        if (result.Ping > 100) warnings.push('Latencia alta (>100ms)');
        updateCounters();
    }
    hideLoading();
}

async function testPacketLoss() {
    showLoading('Probando packet loss...');
    addConsoleLine('Realizando test de packet loss...', 'info');
    const result = await apiCall('detect/packetloss');
    if (result) {
        addConsoleLine(`Packet Loss Promedio: ${result.average_loss}%`,
            result.average_loss === 0 ? 'success' : 'warn');
        document.getElementById('packet-loss').textContent = `${result.average_loss}%`;
        (result.recommendations || []).forEach(r => {
            if (!recommendations.includes(r)) recommendations.push(r);
        });
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
            (result.ErrorCount || 0) === 0 ? 'success' : 'warn');
        (result.Errors || []).slice(0, 5).forEach(err => {
            addConsoleLine(`  - ${err.Error}`, 'error');
            criticalIssues.push(err.Error);
        });
        (result.Recommendations || []).forEach(r => {
            if (!recommendations.includes(r)) recommendations.push(r);
        });
        updateCounters();
        updateRecommendations();
    }
    hideLoading();
}

async function analyzeErrorsAdvanced() {
    showLoading('Analisis avanzado de errores...');
    addConsoleLine('Realizando analisis avanzado de errores...', 'info');
    const result = await apiCall('analyze/errors/advanced');
    if (result) {
        addConsoleLine(`Total: ${result.total_errors} | Criticos: ${result.critical} | Altos: ${result.high}`, 'info');
        (result.errors_found || []).forEach(err => {
            addConsoleLine(`[${err.severity.toUpperCase()}] ${err.description}`,
                err.severity === 'critical' ? 'error' : 'warn');
            (err.solutions || []).forEach(sol => {
                if (!recommendations.includes(sol)) recommendations.push(sol);
            });
        });
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
        const count = (result.dumps_found || []).length;
        addConsoleLine(`Crash dumps encontrados: ${count}`, count > 0 ? 'warn' : 'success');
        (result.analysis || []).forEach(a => {
            addConsoleLine(`  ${a.file} (${a.date})`, 'warn');
        });
        (result.recommendations || []).forEach(r => {
            if (!recommendations.includes(r)) recommendations.push(r);
        });
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
            addConsoleLine(`Mods encontrados: ${result.ModsFound.length}`, 'warn');
            result.ModsFound.forEach(mod => {
                addConsoleLine(`  - ${mod}`, 'warn');
                warnings.push(`Mod detectado: ${mod}`);
            });
            if (!recommendations.includes('Desactiva los mods antes de jugar FiveM'))
                recommendations.push('Desactiva los mods antes de jugar FiveM');
        } else {
            addConsoleLine('&check; No se encontraron mods', 'success');
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
            addConsoleLine(`Software conflictivo: ${result.ConflictsFound.length}`, 'warn');
            result.ConflictsFound.forEach(c => {
                addConsoleLine(`  - ${c}`, 'warn');
                warnings.push(`Software conflictivo: ${c}`);
            });
        } else {
            addConsoleLine('&check; No se encontro software conflictivo', 'success');
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
            addConsoleLine(`Overlays: ${result.overlays_found.length}`, 'warn');
            result.overlays_found.forEach(o => {
                warnings.push(`Overlay: ${o.name}`);
                addConsoleLine(`  - ${o.name}`, 'warn');
            });
        } else {
            addConsoleLine('&check; No se encontraron overlays conflictivos', 'success');
        }
        (result.recommendations || []).forEach(r => {
            if (!recommendations.includes(r)) recommendations.push(r);
        });
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
        (result.Installed || []).forEach(av => addConsoleLine(`Antivirus: ${av}`, 'info'));
        (result.Recommendations || []).forEach(r => {
            if (!recommendations.includes(r)) recommendations.push(r);
        });
        updateRecommendations();
    }
    hideLoading();
}

async function checkDirectX() {
    showLoading('Verificando DirectX...');
    addConsoleLine('Verificando DirectX...', 'info');
    const result = await apiCall('detect/directx');
    if (result) {
        const level = result.feature_level || result.version || 'Desconocido';
        addConsoleLine(`DirectX: ${level}`, result.status === 'good' ? 'success' : 'warn');
        document.getElementById('directx-status').textContent = level;
    }
    hideLoading();
}

async function checkVCRedist() {
    showLoading('Verificando Visual C++ Redistributables...');
    addConsoleLine('Verificando Visual C++ Redistributables...', 'info');
    const result = await apiCall('detect/vcredist');
    if (result) {
        addConsoleLine(`VC++ Redist: ${result.status}`, result.status === 'complete' ? 'success' : 'warn');
        document.getElementById('vcredist-status').textContent = result.status === 'complete' ? 'OK' : 'Incompleto';
        (result.missing || []).forEach(m => {
            warnings.push(`Falta: ${m}`);
            addConsoleLine(`  Falta: ${m}`, 'warn');
        });
        (result.recommendations || []).forEach(r => {
            if (!recommendations.includes(r)) recommendations.push(r);
        });
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
        addConsoleLine(`Benchmark: ${result.overall_score}/100 (${result.rating})`, 'success');
        addConsoleLine(`  CPU: ${result.cpu_score} | RAM: ${result.memory_score} | Disco: ${result.disk_score}`, 'info');
        addConsoleLine(`FiveM Ready: ${result.fivem_ready ? 'Si' : 'No'}`,
            result.fivem_ready ? 'success' : 'warn');
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
        addConsoleLine('&check; Procesos terminados correctamente', 'success');
        repairs.push('Procesos de FiveM terminados');
        updateCounters(); updateRepairsList();
    }
    hideLoading();
}

async function clearCacheSelective() {
    showLoading('Limpiando cache selectiva...');
    addConsoleLine('Limpiando cache selectiva de FiveM...', 'info');
    const result = await apiCall('repair/cache/selective');
    if (result) {
        addConsoleLine(`&check; Cache limpiada: ${result.cleaned_mb || 0} MB liberados`, 'success');
        repairs.push('Cache selectiva limpiada');
        updateCounters(); updateRepairsList();
    }
    hideLoading();
}

async function clearCacheComplete() {
    showLoading('Limpiando cache completa...');
    addConsoleLine('Limpiando cache completa de FiveM...', 'info');
    const result = await apiCall('repair/cache/complete');
    if (result) {
        addConsoleLine(`&check; Cache completa limpiada: ${result.cleaned_mb || 0} MB`, 'success');
        if (result.details && result.details.length > 0) {
            result.details.forEach(d => {
                addConsoleLine(`  ${d.folder}: ${d.size_mb} MB`, 'info');
            });
        }
        repairs.push('Cache completa limpiada');
        updateCounters(); updateRepairsList();
    }
    hideLoading();
}

async function removeDLLs() {
    showLoading('Eliminando DLLs conflictivas...');
    addConsoleLine('Eliminando DLLs conflictivas...', 'info');
    const result = await apiCall('repair/dlls');
    if (result && result.success) {
        addConsoleLine('&check; DLLs conflictivas procesadas', 'success');
        repairs.push('DLLs conflictivas eliminadas');
        updateCounters(); updateRepairsList();
    }
    hideLoading();
}

async function cleanV8DLLs() {
    showLoading('Limpiando v8 DLLs...');
    addConsoleLine('Limpiando v8 DLLs de System32...', 'info');
    const result = await apiCall('repair/v8dlls');
    if (result) {
        const removed = result.removed || [];
        addConsoleLine(removed.length > 0
            ? `&check; ${removed.length} DLLs eliminadas`
            : '&check; No se encontraron v8 DLLs conflictivas', 'success');
        if (removed.length > 0) { repairs.push('v8 DLLs eliminadas'); updateRepairsList(); }
        updateCounters();
    }
    hideLoading();
}

async function cleanROSFiles() {
    showLoading('Limpiando archivos ROS...');
    addConsoleLine('Limpiando archivos de Rockstar Online Services...', 'info');
    const result = await apiCall('repair/rosfiles');
    if (result && result.success) {
        addConsoleLine('&check; Archivos ROS limpiados', 'success');
        repairs.push('Archivos ROS limpiados');
        updateCounters(); updateRepairsList();
    }
    hideLoading();
}

async function repairROS() {
    showLoading('Reparando ROS...');
    addConsoleLine('Reparando autenticacion de Rockstar...', 'info');
    const result = await apiCall('repair/ros');
    if (result && result.success) {
        addConsoleLine('&check; Autenticacion ROS reparada', 'success');
        repairs.push('Autenticacion ROS reparada');
        updateCounters(); updateRepairsList();
    }
    hideLoading();
}

async function disableMods() {
    showLoading('Desactivando mods...');
    addConsoleLine('Desactivando mods de GTA V...', 'info');
    const result = await apiCall('repair/mods/disable');
    if (result && result.success) {
        addConsoleLine(`&check; ${result.disabled_count || 0} mods desactivados`, 'success');
        repairs.push('Mods desactivados');
        updateCounters(); updateRepairsList();
    }
    hideLoading();
}

async function closeConflicts() {
    showLoading('Cerrando software conflictivo...');
    addConsoleLine('Cerrando software conflictivo...', 'info');
    const result = await apiCall('repair/conflicts/close');
    if (result && result.success) {
        addConsoleLine('&check; Software conflictivo cerrado', 'success');
        repairs.push('Software conflictivo cerrado');
        updateCounters(); updateRepairsList();
    }
    hideLoading();
}

// ============= OPTIMIZACION =============

async function configureFirewall() {
    showLoading('Configurando firewall...');
    addConsoleLine('Configurando reglas de firewall para FiveM...', 'info');
    const result = await apiCall('optimize/firewall');
    if (result && result.success) {
        addConsoleLine('&check; Reglas de firewall configuradas', 'success');
        repairs.push('Firewall configurado');
        updateCounters(); updateRepairsList();
    }
    hideLoading();
}

async function configureDefender() {
    showLoading('Configurando exclusiones...');
    addConsoleLine('Configurando exclusiones de Windows Defender...', 'info');
    const result = await apiCall('optimize/defender');
    if (result && result.success) {
        addConsoleLine('&check; Exclusiones de Defender configuradas', 'success');
        repairs.push('Exclusiones de Defender configuradas');
        updateCounters(); updateRepairsList();
    }
    hideLoading();
}

async function optimizePageFile() {
    showLoading('Analizando paginacion...');
    addConsoleLine('Analizando archivo de paginacion...', 'info');
    const result = await apiCall('optimize/pagefile');
    if (result && result.success) {
        if (result.needs_adjustment) {
            addConsoleLine(`⚠ Paginacion insuficiente: ${result.current_mb} MB actual, ${result.recommended_mb} MB recomendado`, 'warning');
            const recMsg = `Configura el archivo de paginacion a ${result.recommended_mb} MB (actual: ${result.current_mb} MB)`;
            if (!recommendations.includes(recMsg)) {
                recommendations.push(recMsg);
            }
        } else {
            addConsoleLine(`&check; Paginacion correcta: ${result.current_mb} MB (recomendado: ${result.recommended_mb} MB)`, 'success');
        }
        updateRecommendations();
    }
    hideLoading();
}

async function optimizeGraphics() {
    showLoading('Optimizando graficos...');
    addConsoleLine('Optimizando configuracion grafica...', 'info');
    const result = await apiCall('optimize/graphics');
    if (result) {
        if (result.success) {
            addConsoleLine('&check; Configuracion grafica optimizada', 'success');
            repairs.push('Graficos optimizados');
            updateCounters(); updateRepairsList();
        } else {
            addConsoleLine(`${result.error || 'Error optimizando graficos'}`, 'warn');
        }
    }
    hideLoading();
}

async function configureTextureBudget() {
    showLoading('Configurando Texture Budget...');
    addConsoleLine('Configurando Extended Texture Budget automaticamente...', 'info');
    const result = await apiCall('optimize/texturebudget');
    if (result) {
        addConsoleLine(`VRAM: ${result.vram_detected}GB -> Texture Budget: ${result.recommended_budget}%`, 'info');
        if (result.success) {
            repairs.push(`Texture Budget: ${result.recommended_budget}%`);
            if (!recommendations.includes(`Ajusta "Extended Texture Budget" a ${result.recommended_budget}% en FiveM`)) {
                recommendations.push(`Ajusta "Extended Texture Budget" a ${result.recommended_budget}% en FiveM`);
            }
            updateCounters(); updateRepairsList(); updateRecommendations();
        }
    }
    hideLoading();
}

async function optimizeWindows() {
    showLoading('Optimizando Windows...');
    addConsoleLine('Aplicando optimizaciones de Windows para gaming...', 'info');
    const result = await apiCall('optimize/windows');
    if (result) {
        (result.optimizations || []).forEach(opt => {
            addConsoleLine(`&check; ${opt}`, 'success');
            repairs.push(opt);
        });
        (result.failed || []).forEach(f => addConsoleLine(`${f}`, 'warn'));
        if (result.requires_restart) {
            if (!recommendations.includes('Reinicia el PC para aplicar todas las optimizaciones')) {
                recommendations.push('Reinicia el PC para aplicar todas las optimizaciones');
            }
            updateRecommendations();
        }
        updateCounters(); updateRepairsList();
    }
    hideLoading();
}

async function updateGPUDriver() {
    showLoading('Verificando driver GPU...');
    addConsoleLine('Verificando estado del driver de GPU...', 'info');

    // Primero verificar si hay actualizacion disponible
    const check = await apiCall('detect/driver-update');
    if (!check || !check.success) {
        addConsoleLine('No se pudo verificar el estado del driver', 'error');
        hideLoading();
        return;
    }

    addConsoleLine(`GPU: ${check.gpu_name}`, 'info');
    addConsoleLine(`Driver actual: ${check.current_driver}`, 'info');
    addConsoleLine(`Fabricante: ${check.vendor ? check.vendor.toUpperCase() : 'Desconocido'}`, 'info');

    if (check.latest_driver) {
        addConsoleLine(`Ultima version disponible: ${check.latest_driver}`, 'info');
    }

    if (!check.needs_update) {
        addConsoleLine('&check; El driver de GPU ya esta actualizado', 'success');
        hideLoading();
        return;
    }

    // Hay actualizacion disponible
    const latestText = check.latest_driver ? ` (${check.latest_driver})` : '';
    addConsoleLine(`\u26a0 Driver desactualizado. Actualizacion disponible${latestText}`, 'warning');
    addConsoleLine('Descargando e instalando driver...', 'info');

    const result = await apiCall('repair/update-driver');
    if (result) {
        if (result.action === 'installed') {
            addConsoleLine(`&check; Driver actualizado: ${result.previous_driver} -> ${result.new_driver}`, 'success');
            repairs.push(`Driver GPU actualizado a ${result.new_driver}`);
            if (!recommendations.includes('Reinicia el PC para completar la actualizacion del driver')) {
                recommendations.push('Reinicia el PC para completar la actualizacion del driver');
            }
            updateRecommendations();
        } else if (result.action === 'opened_installer') {
            addConsoleLine('&check; Instalador abierto. Sigue las instrucciones en pantalla.', 'success');
            repairs.push('Instalador de driver GPU abierto');
        } else if (result.action === 'manual') {
            const url = result.download_url || '';
            addConsoleLine(`Descarga manual necesaria: ${url}`, 'warning');
            if (url && !recommendations.includes(`Actualiza el driver GPU desde: ${url}`)) {
                recommendations.push(`Actualiza el driver GPU desde: ${url}`);
            }
            updateRecommendations();
        } else if (result.action === 'none') {
            addConsoleLine('&check; ' + (result.message || 'Driver ya actualizado'), 'success');
        } else {
            addConsoleLine('Error: ' + (result.error || 'No se pudo actualizar'), 'error');
        }
        updateCounters();
        updateRepairsList();
    }
    hideLoading();
}

async function optimizeDNS() {
    showLoading('Optimizando DNS...');
    addConsoleLine('Analizando y optimizando DNS...', 'info');
    const result = await apiCall('optimize/dns');
    if (result) {
        (result.dns_test_results || []).forEach(dns => {
            addConsoleLine(`${dns.name}: ${dns.latency_ms}ms`, dns.status === 'ok' ? 'success' : 'info');
        });
        if (result.best_dns) addConsoleLine(`&check; Mejor DNS: ${result.best_dns}`, 'success');
        if (result.recommendation) {
            if (!recommendations.includes(result.recommendation))
                recommendations.push(result.recommendation);
            updateRecommendations();
        }
    }
    hideLoading();
}

// ============= MODALES =============

function showDetailsModal(type) {
    const modal = document.getElementById('details-modal');
    const title = document.getElementById('details-modal-title');
    const body = document.getElementById('details-modal-body');
    let content = '';

    switch (type) {
        case 'critical':
            title.textContent = 'Problemas Criticos';
            content = criticalIssues.length === 0
                ? '<p class="no-items">No hay problemas criticos detectados</p>'
                : `<ul class="details-list critical">${criticalIssues.map(i => `<li>${i}</li>`).join('')}</ul>`;
            break;
        case 'warnings':
            title.textContent = 'Advertencias';
            content = warnings.length === 0
                ? '<p class="no-items">No hay advertencias</p>'
                : `<ul class="details-list warning">${warnings.map(w => `<li>${w}</li>`).join('')}</ul>`;
            break;
        case 'repairs':
            title.textContent = 'Reparaciones Aplicadas';
            content = repairs.length === 0
                ? '<p class="no-items">No se han aplicado reparaciones</p>'
                : `<ul class="details-list success">${repairs.map(r => `<li>&check; ${r}</li>`).join('')}</ul>`;
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
                        ${['cpu_score:CPU', 'memory_score:Memoria', 'disk_score:Disco'].map(s => {
                            const [key, label] = s.split(':');
                            return `<div class="benchmark-item">
                                <span>${label}</span>
                                <div class="progress-bar"><div class="progress" style="width:${benchmarkResult[key]}%"></div></div>
                                <span>${benchmarkResult[key]}/100</span>
                            </div>`;
                        }).join('')}
                    </div>
                    <p class="fivem-ready ${benchmarkResult.fivem_ready ? 'yes' : 'no'}">
                        FiveM Ready: ${benchmarkResult.fivem_ready ? '&check; Si' : '&cross; No'}
                    </p>
                </div>`;
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

async function showCitizenFXModal() {
    // Cargar configuracion actual del archivo antes de mostrar el modal
    const config = await apiCall('config/citizenfx', 'GET');
    if (config) {
        // UpdateChannel
        const channelSelect = document.getElementById('update-channel');
        if (channelSelect && config.UpdateChannel) {
            channelSelect.value = config.UpdateChannel;
        }
        // SavedBuildNumber (el archivo usa SavedBuildNumber, no GameBuild)
        const buildSelect = document.getElementById('game-build');
        if (buildSelect) {
            const buildValue = config.SavedBuildNumber || config.GameBuild || '';
            // Verificar si el valor existe como opcion, si no, seleccionar vacio
            const optionExists = Array.from(buildSelect.options).some(opt => opt.value === buildValue);
            buildSelect.value = optionExists ? buildValue : '';
        }
        // DisableNVSP
        const nvspCheck = document.getElementById('disable-nvsp');
        if (nvspCheck) {
            nvspCheck.checked = config.DisableNVSP === '1';
        }
        // EnableFullMemoryDump
        const dumpsCheck = document.getElementById('enable-dumps');
        if (dumpsCheck) {
            dumpsCheck.checked = config.EnableFullMemoryDump === '1';
        }

        // Mostrar ruta del archivo y estado
        const pathInfo = config._path || 'No encontrado';
        const existsText = config._exists ? '' : ' (se creara al guardar)';
        addConsoleLine(`CitizenFX.ini: ${pathInfo}${existsText}`, 'info');
    }
    document.getElementById('citizenfx-modal').classList.add('active');
}

function showLaunchParamsModal() {
    document.getElementById('launch-params-modal').classList.add('active');
}

async function showBackupsModal() {
    document.getElementById('backups-modal').classList.add('active');
    document.getElementById('backups-list').innerHTML = '<p style="color:var(--text-muted);">Cargando backups...</p>';
    const result = await apiCall('backups', 'GET');
    if (result && result.backups && result.backups.length > 0) {
        document.getElementById('backups-list').innerHTML = result.backups.map(b => `
            <div class="backup-item">
                <div class="backup-info">
                    <span class="backup-name">${b.name}</span>
                    <span class="backup-meta"><span class="backup-category">${b.category}</span>${b.date} &mdash; ${b.size_mb} MB</span>
                </div>
                <button class="btn-restore" onclick="restoreBackup('${b.path.replace(/'/g, "\\'")}')">Restaurar</button>
            </div>`).join('');
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
    if (selected.length === 0) { alert('Selecciona al menos una reparacion'); return; }

    closeModal('advanced-repair-modal');
    showLoading('Ejecutando reparaciones avanzadas...');
    addConsoleLine(`Ejecutando ${selected.length} reparaciones seleccionadas...`, 'info');

    const result = await apiCall('repair/advanced', 'POST', { repairs: selected });
    if (result) {
        (result.results || []).forEach(r => {
            if (r.success) {
                addConsoleLine(`&check; ${r.name}`, 'success');
                if (!repairs.includes(r.name)) repairs.push(r.name);
            } else {
                addConsoleLine(`&cross; ${r.name}: ${r.error || 'Error'}`, 'error');
            }
        });
        updateCounters();
        updateRepairsList();
    }
    hideLoading();
}

function selectProfile(profile, el) {
    selectedProfile = profile;
    document.querySelectorAll('.profile-card').forEach(card => card.classList.remove('selected'));
    if (el) el.classList.add('selected');
}

async function applySelectedProfile() {
    closeModal('profiles-modal');
    showLoading(`Aplicando perfil ${selectedProfile}...`);
    addConsoleLine(`Aplicando perfil de rendimiento: ${selectedProfile}`, 'info');
    const result = await apiCall('profiles/apply', 'POST', { profile: selectedProfile });
    if (result && result.success) {
        addConsoleLine('&check; Perfil aplicado correctamente', 'success');
        repairs.push(`Perfil ${selectedProfile} aplicado`);
        updateCounters(); updateRepairsList();
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
    showLoading('Guardando configuracion CitizenFX.ini...');
    addConsoleLine('Guardando configuracion CitizenFX.ini...', 'info');
    const result = await apiCall('config/citizenfx', 'POST', settings);
    if (result && result.success) {
        addConsoleLine(`&check; CitizenFX.ini guardado en: ${result.path}`, 'success');
        if (result.config) {
            const keys = Object.keys(result.config);
            addConsoleLine(`Claves configuradas: ${keys.join(', ')}`, 'info');
        }
        if (settings.GameBuild) {
            addConsoleLine(`Build del juego: ${settings.GameBuild}`, 'info');
        }
        addConsoleLine(`Canal: ${settings.UpdateChannel} | NVSP: ${settings.DisableNVSP === '1' ? 'Desactivado' : 'Activado'} | Dumps: ${settings.EnableFullMemoryDump === '1' ? 'Si' : 'No'}`, 'info');
        repairs.push('CitizenFX.ini configurado');
        updateCounters(); updateRepairsList();
    } else {
        addConsoleLine(`Error al guardar CitizenFX.ini: ${result ? result.error : 'Sin respuesta'}`, 'error');
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
    showLoading('Guardando parametros...');
    const result = await apiCall('config/launchparams', 'POST', { parameters: params });
    if (result && result.success) {
        addConsoleLine(`&check; Parametros guardados: ${params.join(' ')}`, 'success');
        repairs.push('Parametros de lanzamiento configurados');
        updateCounters(); updateRepairsList();
    }
    hideLoading();
}

async function restoreBackup(path) {
    if (!confirm('Estas seguro de que deseas restaurar este backup?')) return;
    showLoading('Restaurando backup...');
    const result = await apiCall('backups/restore', 'POST', { path });
    if (result && result.success) {
        addConsoleLine('&check; Backup restaurado correctamente', 'success');
    } else {
        addConsoleLine('&cross; Error restaurando backup: ' + (result && result.error || 'desconocido'), 'error');
    }
    hideLoading();
}

async function generateReport() {
    showLoading('Generando reporte...');
    addConsoleLine('Generando reporte HTML...', 'info');
    const result = await apiCall('report/generate');
    if (result && result.success) {
        addConsoleLine(`&check; Reporte generado: ${result.path}`, 'success');
        window.open(`/api/report/view?path=${encodeURIComponent(result.path)}`, '_blank');
    }
    hideLoading();
}

async function exportConfig() {
    showLoading('Exportando configuracion...');
    addConsoleLine('Exportando configuracion...', 'info');
    const result = await apiCall('config/export');
    if (result && result.success) {
        addConsoleLine(`&check; Configuracion exportada: ${result.path}`, 'success');
    }
    hideLoading();
}

// ============= ESTADO =============

async function refreshStatus() {
    addConsoleLine('Actualizando estado...', 'info');
    const result = await apiCall('status', 'GET');
    if (result) {
        document.getElementById('status-value').textContent = result.status || 'Listo';
        addConsoleLine('Estado actualizado', 'success');
    }
}

// Cerrar modales clickando fuera
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('modal-overlay')) {
        e.target.classList.remove('active');
    }
});

// Inicializacion
document.addEventListener('DOMContentLoaded', function() {
    refreshStatus();
});
