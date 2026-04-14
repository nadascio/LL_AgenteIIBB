@echo off
echo ======================================================
echo   LISICKI LITVIN - SUITE PROFESIONAL FASE 2 (SaaS)
echo ======================================================
echo.
echo Iniciando servidor backend (FastAPI)...
echo Acceso: http://localhost:8000
echo.
python -m uvicorn Fase2_SaaS.backend.main:app --host 0.0.0.0 --port 8000 --reload
pause
