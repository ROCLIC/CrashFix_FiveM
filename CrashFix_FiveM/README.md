# FiveM Diagnostic & AUTO-REPAIR Tool v6.1 PRO

Herramienta web de diagnostico y reparacion automatica para FiveM. Detecta problemas de hardware, software, red y configuracion que causan crashes en FiveM/GTA V, y aplica reparaciones de forma automatizada.

## Caracteristicas

- **Diagnostico completo del sistema**: GPU, RAM, CPU, temperaturas, red, DirectX, VC++ Redistributables.
- **Analisis de errores**: Lee los logs de FiveM, detecta patrones de error conocidos y sugiere soluciones.
- **Reparacion automatica**: Limpieza de cache, eliminacion de DLLs conflictivas, reparacion de ROS, desactivacion de mods.
- **Optimizacion**: Configuracion grafica, Texture Budget, reglas de firewall, exclusiones de Defender, optimizaciones de Windows.
- **Perfiles de rendimiento**: Potato, Bajo, Medio, Alto, Ultra — ajusta automaticamente la configuracion segun tu hardware.
- **Backups automaticos**: Crea respaldos antes de cada reparacion para poder restaurar facilmente.
- **Benchmark del sistema**: Evalua CPU, RAM y disco para determinar si tu PC esta listo para FiveM.

## Requisitos

- **Python** 3.8 o superior
- **Windows** 10/11 (funcionalidad completa; en Linux funciona con capacidades reducidas)
- **Flask** 2.3+

## Instalacion

```bash
# Clonar el repositorio
git clone https://github.com/DSW-robinsonruiz/CrashFix_FiveM.git
cd CrashFix_FiveM/CrashFix_FiveM

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar
python app.py
```

La herramienta se abrira en `http://127.0.0.1:5000`.

## Estructura del Proyecto

```
CrashFix_FiveM/
  app.py                    # Aplicacion Flask principal (rutas y API)
  config.py                 # Configuracion centralizada
  requirements.txt          # Dependencias de Python
  src/
    services/
      diagnostic_service.py # Deteccion de GTA V, errores, mods, conflictos
      repair_service.py     # Reparaciones y optimizaciones
      hardware_service.py   # Informacion de GPU, RAM, CPU, temperaturas
      network_service.py    # Tests de red, packet loss, DNS
      session_manager.py    # Gestion de sesiones y reportes
    utils/
      system_utils.py       # Comandos del sistema, procesos, ping
      file_utils.py         # Operaciones de archivos y backups
      logging_utils.py      # Sistema de logging personalizado
      validation.py         # Validacion de entradas y rutas
  static/
    css/style.css           # Estilos de la interfaz web
    js/app.js               # Logica del frontend
  templates/
    index.html              # Interfaz web principal
```

## Variables de Entorno (Opcionales)

| Variable | Descripcion | Valor por defecto |
|---|---|---|
| `FIVEM_DIAG_HOST` | Host del servidor | `127.0.0.1` |
| `FIVEM_DIAG_PORT` | Puerto del servidor | `5000` |
| `FIVEM_DIAG_DEBUG` | Modo debug | `false` |
| `FIVEM_DIAG_SECRET` | Clave secreta de Flask | Generada automaticamente |

## API Endpoints

### Diagnostico

| Metodo | Endpoint | Descripcion |
|---|---|---|
| POST | `/api/diagnostic/complete` | Diagnostico completo |
| POST | `/api/diagnostic/full/v2` | Diagnostico PRO v2 (10 fases + benchmark) |
| POST | `/api/detect/gtav` | Detectar GTA V |
| POST | `/api/detect/fivem` | Detectar FiveM |
| POST | `/api/detect/gpu` | Informacion de GPU |
| POST | `/api/detect/ram` | Informacion de RAM |
| POST | `/api/detect/cpu` | Informacion de CPU |
| POST | `/api/detect/network` | Test de red |
| POST | `/api/detect/requirements` | Verificar requisitos del sistema |
| POST | `/api/detect/temperatures` | Temperaturas del sistema |
| POST | `/api/detect/packetloss` | Test de packet loss |
| POST | `/api/detect/directx` | Verificar DirectX |
| POST | `/api/detect/vcredist` | Verificar VC++ Redistributables |

### Reparacion

| Metodo | Endpoint | Descripcion |
|---|---|---|
| POST | `/api/repair/quick` | Reparacion rapida |
| POST | `/api/repair/kill` | Terminar procesos de FiveM |
| POST | `/api/repair/cache/selective` | Limpiar cache selectiva |
| POST | `/api/repair/cache/complete` | Limpiar cache completa |
| POST | `/api/repair/dlls` | Eliminar DLLs conflictivas |
| POST | `/api/repair/v8dlls` | Eliminar v8 DLLs de System32 |
| POST | `/api/repair/ros` | Reparar autenticacion ROS |
| POST | `/api/repair/rosfiles` | Limpiar archivos ROS |
| POST | `/api/repair/mods/disable` | Desactivar mods |
| POST | `/api/repair/conflicts/close` | Cerrar software conflictivo |
| POST | `/api/repair/advanced` | Reparaciones avanzadas (seleccionables) |

### Optimizacion

| Metodo | Endpoint | Descripcion |
|---|---|---|
| POST | `/api/optimize/firewall` | Configurar firewall |
| POST | `/api/optimize/defender` | Exclusiones de Defender |
| POST | `/api/optimize/pagefile` | Optimizar paginacion |
| POST | `/api/optimize/graphics` | Optimizar graficos |
| POST | `/api/optimize/texturebudget` | Configurar Texture Budget |
| POST | `/api/optimize/windows` | Optimizaciones de Windows |
| POST | `/api/optimize/dns` | Optimizar DNS |

## Licencia

Apache License 2.0
