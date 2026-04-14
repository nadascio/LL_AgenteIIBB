from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import pandas as pd
import io
import sys
import os
from typing import List, Dict
import traceback

# Agregar el directorio raíz al path para importar el core existente
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_DIR)

from core.processor import AuditorProcessor
from core.agent import IIBBAgent
from core.database import SessionLocal, init_db

app = FastAPI(title="Lisicki Litvin Tax Audit API", version="2.0.0")

# Inicializar Base de Datos al arrancar
init_db()

# Configurar Directorios
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
templates_dir = os.path.join(CURRENT_DIR, "templates")
static_dir = os.path.join(CURRENT_DIR, "static")

os.makedirs(static_dir, exist_ok=True)
os.makedirs(templates_dir, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializar componentes del core
try:
    db = SessionLocal()
    agent = IIBBAgent()
    processor = AuditorProcessor(db=db)
except Exception as e:
    print(f"CRITICAL ERROR INITIALIZING CORE: {e}")
    traceback.print_exc()

# --- RUTAS ---

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": "2.0.0"}

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    try:
        # Intento con TemplateResponse explícito
        return templates.TemplateResponse(name="index.html", context={"request": request})
    except Exception as e:
        # Fallback a HTML plano para la landing si falla Jinja2 (compatibilidad Python 3.14)
        print(f"Template Error: {e}")
        index_path = os.path.join(templates_dir, "index.html")
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())

@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    try:
        return templates.TemplateResponse(name="dashboard.html", context={"request": request})
    except Exception:
        path = os.path.join(templates_dir, "dashboard.html")
        with open(path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())

@app.get("/report", response_class=HTMLResponse)
async def get_report(request: Request):
    try:
        return templates.TemplateResponse(name="report_v2.html", context={"request": request})
    except Exception:
        path = os.path.join(templates_dir, "report_v2.html")
        with open(path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())

@app.post("/api/audit/upload")
async def upload_audit_file(file: UploadFile = File(...)):
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Formato no soportado.")
    
    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        results_df = processor.process_dataframe(df)
        
        sample_data = results_df.head(5).to_dict(orient="records")
        summary_response = agent.analizar(
            cuit=str(df.iloc[0].get('Cuit', 'Desconocido')),
            periodo="2026",
            registros=sample_data
        )
        
        return {
            "filename": file.filename,
            "results": results_df.to_dict(orient="records"),
            "ai_summary": summary_response
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e), "trace": traceback.format_exc()})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
