@echo off
title FiveM Diagnostic Tool v6.1 PRO

echo ==============================================
echo   FiveM Diagnostic & AUTO-REPAIR Tool v6.1
echo   Herramienta de Diagnostico Avanzado
echo ==============================================
echo.

:: Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no esta instalado o no esta en el PATH
    pause
    exit /b 1
)

echo [OK] Python detectado
echo.

:: Verificar Flask
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Instalando dependencias...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] No se pudieron instalar las dependencias
        pause
        exit /b 1
    )
)

echo [OK] Dependencias listas
echo.

echo [INFO] Iniciando servidor...
echo http://127.0.0.1:5000
echo.

python app.py
pause
