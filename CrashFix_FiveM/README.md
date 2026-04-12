# 🚀CrashFix_FiveM v6.2 PRO (10/10 Optimized)

Herramienta web profesional de diagnóstico y reparación automática diseñada específicamente para la comunidad de FiveM. Esta aplicación detecta y soluciona de forma inteligente problemas de hardware, software, red y configuración que causan crasheos en FiveM/GTA V.

---

## 🏆 Novedades de la Versión 6.2 (Abril 2026)

Esta versión ha sido sometida a una auditoría técnica integral, alcanzando un nivel **10/10 en funcionalidad y robustez**.

### ✨ Características Principales
- **🤖 Mantenimiento Total (Un-Solo-Clic):** Sistema de diagnóstico inteligente que no solo detecta, sino que aplica automáticamente reparaciones de red, limpieza de caché, desactivación de mods conflictivos y ajustes de hardware en un solo ciclo.
- **🖥️ Soporte Multi-GPU Avanzado:** Detección precisa de sistemas híbridos (Laptops Intel/NVIDIA). Identifica VRAM real y prioriza la GPU dedicada para diagnósticos térmicos y de rendimiento.
- **📡 Monitoreo Proactivo 24/7:** Vigilancia en tiempo real. La aplicación emite alertas visuales instantáneas si detecta temperaturas críticas, falta de RAM o pérdida de paquetes mientras está abierta.
- **🔍 Base de Datos de Errores 2024-2026:** Actualizada con los patrones de error más recientes de FiveM, incluyendo `ERR_GFX_D3D_SWAPCHAIN_ALLOC`, `Pool Size Overflow` y crasheos de memoria en `GTA5.exe+`.
- **🛡️ Robustez "Anti-Windows":** Lógica de "fuerza bruta" para el borrado de archivos. Maneja automáticamente permisos de escritura y reintentos para eliminar carpetas bloqueadas de caché y logs sin fallar.

---

## 🛠️ Funcionalidades Detalladas

### 📊 Diagnóstico Exhaustivo
- **Hardware:** Análisis de GPU, RAM, CPU y almacenamiento con detección de temperaturas en tiempo real.
- **Software:** Identificación de overlays conflictivos (Discord, Steam, NVIDIA) y programas en segundo plano (MSI Afterburner, RivaTuner).
- **Red:** Test de latencia, pérdida de paquetes (Packet Loss) y optimizador de DNS para encontrar el servidor más rápido según tu ubicación.
- **Integridad:** Verificación de archivos esenciales de GTA V y versiones de VC++ Redistributables.

### 🔧 Reparaciones y Optimizaciones
- **Limpieza Inteligente:** Borrado selectivo o completo de caché y logs de FiveM con gestión de permisos.
- **Reparación de ROS:** Solución de problemas de autenticación de Rockstar Online Services.
- **Ajustes Gráficos:** Calculador de **Texture Budget** basado en VRAM y optimización automática de `settings.xml`.
- **Windows Gaming:** Configuración de reglas de Firewall, exclusiones de Defender y optimización de la pila de red (TCP/IP Reset).

---

## 🚀 Instalación y Uso

### Requisitos
- **Python** 3.11 o superior (recomendado)
- **Windows** 10/11 (funcionalidad completa)
- **Permisos de Administrador** (necesarios para reparaciones de sistema)

### Guía Rápida
```bash
# 1. Clonar el repositorio
git clone https://github.com/DSW-robinsonruiz/CrashFix_FiveM.git
cd CrashFix_FiveM/CrashFix_FiveM

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Iniciar la aplicación
python app.py
```
Accede a la interfaz desde tu navegador en: `http://127.0.0.1:5000`

---

## 📁 Estructura del Proyecto

- `app.py`: Servidor Flask principal y API sincronizada.
- `config.py`: Configuración centralizada y base de datos de errores 2026.
- `src/services/`: Lógica de negocio (Diagnóstico, Reparación, Hardware, Red).
- `src/utils/`: Utilidades de sistema, archivos y validación robusta.
- `static/ & templates/`: Interfaz de usuario moderna y proactiva.

---

## 📄 Licencia

Este proyecto está bajo la Licencia Apache 2.0. Desarrollado para mejorar la estabilidad de la comunidad de FiveM.

**Desarrollado con ❤️ para jugadores de FiveM.**
