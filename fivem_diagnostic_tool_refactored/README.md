# FiveM Diagnostic & AUTO-REPAIR Tool v6.1 PRO

Herramienta profesional de diagnóstico y reparación automática para FiveM.

## Características

- **Diagnóstico Completo**: Análisis exhaustivo del sistema, GTA V, FiveM y red
- **Reparación Automática**: Corrección de problemas comunes con un solo clic
- **Optimización**: Configuración automática para mejor rendimiento
- **Backups Automáticos**: Respaldo antes de cada reparación
- **Interfaz Web**: Interfaz moderna y fácil de usar

## Requisitos

- Windows 10/11
- Python 3.8 o superior
- GTA V instalado
- FiveM instalado

## Instalación

1. Descarga o clona el proyecto
2. Ejecuta `start.bat`
3. Abre tu navegador en `http://127.0.0.1:5000`

## Estructura del Proyecto

```
fivem_diagnostic_tool/
├── app.py                 # Aplicación principal Flask
├── config.py              # Configuración centralizada
├── requirements.txt       # Dependencias
├── start.bat              # Script de inicio
├── src/
│   ├── services/          # Lógica de negocio
│   │   ├── diagnostic_service.py
│   │   ├── repair_service.py
│   │   ├── hardware_service.py
│   │   ├── network_service.py
│   │   └── session_manager.py
│   └── utils/             # Utilidades
│       ├── file_utils.py
│       ├── system_utils.py
│       ├── logging_utils.py
│       └── validation.py
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── app.js
└── templates/
    └── index.html
```

## Cambios en v6.1 PRO

### Correcciones de Seguridad
- Validación de rutas para prevenir path traversal
- Validación de IDs de reparación
- Headers de seguridad HTTP
- Manejo seguro de sesiones

### Mejoras de Arquitectura
- Eliminación de variables globales mutables
- Separación de responsabilidades (servicios)
- Sistema de sesiones para estado
- Configuración centralizada
- Manejo de excepciones específico

### Mejoras de Código
- Documentación completa con docstrings
- Type hints en todas las funciones
- Logging estructurado
- Manejo de errores robusto

## API Endpoints

### Diagnóstico
- `POST /api/diagnostic/complete` - Diagnóstico completo
- `POST /api/detect/gtav` - Detectar GTA V
- `POST /api/detect/gpu` - Información de GPU
- `POST /api/detect/ram` - Información de RAM
- `POST /api/detect/network` - Test de red

### Reparación
- `POST /api/repair/quick` - Reparación rápida
- `POST /api/repair/cache/selective` - Limpiar caché selectiva
- `POST /api/repair/cache/complete` - Limpiar caché completa
- `POST /api/repair/dlls` - Eliminar DLLs conflictivas
- `POST /api/repair/advanced` - Reparación avanzada

### Optimización
- `POST /api/optimize/firewall` - Configurar firewall
- `POST /api/optimize/defender` - Exclusiones Defender
- `POST /api/optimize/graphics` - Optimizar gráficos

## Licencia

MIT License

## Autor

FiveM Diagnostic Tool Team
