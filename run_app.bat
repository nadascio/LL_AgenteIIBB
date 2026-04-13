@echo off
:: Truco: Título temporal para evitar que el script se mate a sí mismo durante la limpieza
TITLE Limpiador_Cerrando_Duplicados
taskkill /F /FI "WINDOWTITLE eq Agente IIBB - Tax Audit LL*" /T >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Agente IIBB - Tax Audit AI*" /T >nul 2>&1

TITLE Agente IIBB - Tax Audit LL
echo ========================================================
echo   Lisicki Litvin - IIBB Tax Audit LL
echo   Iniciando servidor local...
echo   (Se han cerrado instancias previas para evitar conflictos)
echo ========================================================
echo.

:: Matar cualquier proceso Streamlit/Python corriendo en el puerto 8501
echo [SISTEMA] Liberando puerto 8501 (si estaba en uso)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8501 " ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
)
timeout /t 1 /nobreak >nul

:: Verificar si existe el entorno virtual
if exist .venv\Scripts\activate (
    echo [SISTEMA] Activando entorno virtual...
    call .venv\Scripts\activate
) else (
    echo [ADVERTENCIA] No se encontro el entorno virtual .venv.
    echo Intentando correr con el Python del sistema...
)

:: Ejecutar Streamlit
echo [SISTEMA] Lanzando aplicacion en http://localhost:8501
echo.
streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --server.fileWatcherType none

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Hubo un problema al iniciar la aplicacion.
    echo Asegurate de tener instaladas las dependencias: pip install -r requirements.txt
    pause
)
