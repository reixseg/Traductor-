@echo off
cd /d "%~dp0"

echo ============================================
echo  Traductor en vivo de pantalla (EN -^> ES)
echo ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no esta instalado o no esta en el PATH.
    pause
    exit /b 1
)

if not exist ".venv" (
    echo Creando entorno virtual...
    python -m venv .venv
)

call .venv\Scripts\activate.bat

echo Instalando dependencias...
pip install -r requirements.txt -q

echo.
echo Iniciando traductor...
echo.
echo  IMPORTANTE:
echo  - Las traducciones se superponen SOBRE el texto en pantalla
echo  - Aparece un aviso al iniciar
echo  - Icono AZUL en la bandeja (junto al reloj)
echo  - NO uses pantalla completa
echo  - Los clics pasan a traves del overlay
echo.

python main.py
if errorlevel 1 (
    echo.
    echo [ERROR] El programa termino con errores. Revisa traductor.log
    pause
)

pause
