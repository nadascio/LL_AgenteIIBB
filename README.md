# Agente de Ingresos Brutos — Auditoría Fiscal Premium (Lisicki Litvin)

Agente de IA diseñado para automatizar la auditoría de Ingresos Brutos (IIBB) en Argentina. Utiliza **RAG (Retrieval-Augmented Generation)** para analizar normativas provinciales y cruzar datos de contribuyentes con el historial de casos de la firma.

---

## 🚀 Instalación en Nueva PC

### 1. Requisitos Previos
*   **Python 3.10+**: Asegúrate de tenerlo instalado.
*   **Ollama (Opcional pero Recomendado)**: Descarga desde [ollama.ai](https://ollama.ai) para procesamiento 100% local y gratis.

### 2. Clonar y Configurar Entorno
```powershell
# Clonar repositorio
git clone https://github.com/nadascio/LL_AgenteIIBB.git
cd LL_AgenteIIBB

# Crear y activar entorno virtual
python -m venv .venv
.venv\Scripts\Activate.ps1

# Instalar dependencias
pip install -r requirements.txt
```

### 3. Configurar Variables de Entorno
Copiá el archivo `.env.example` a uno nuevo llamado `.env`:
```powershell
copy .env.example .env
```
Editá el `.env` con tus claves:
*   Si usás **Gemini**: Obtené tu clave en [AI Studio](https://aistudio.google.com).
*   Si usás **Ollama**: Asegurate de correr `ollama pull qwen2.5:7b`.

---

## 🖥️ Uso de la Aplicación

Para lanzar el portal del auditor, simplemente ejecutá:
```powershell
./run_app.bat
```
Esto abrirá la interfaz en [http://localhost:8501](http://localhost:8501).

### Secciones del Portal:
1.  **Carga de Datos**: Subí el Excel de LL para procesar auditorías masivas.
2.  **Historial de Auditorías**: Mapa interactivo de las 24 jurisdicciones con detalle técnico y descarga de informes Word/Excel.
3.  **Configuración**: Cambiá el motor de IA (Gemini / Ollama), actualizá el modelo o probá la conexión en tiempo real.

---

## 🏗️ Arquitectura
*   **Frontend**: Streamlit (Premium UI)
*   **Base de datos**: SQLite + SQLAlchemy
*   **Motor RAG**: ChromaDB + SentenceTransformers (Local)
*   **Reportes**: `python-docx` (Word) y `xlsxwriter` (Excel)
*   **IA**: Soporte multi-backend vía LangChain (Gemini, Ollama, OpenAI)

---

## 🛡️ Seguridad
*   Los datos de clientes y las API Keys **NO** se suben al repositorio (están en `.gitignore`).
*   Para pasar datos entre computadoras, se recomienda mover manualmente la carpeta `data/` si se desea mantener el historial.

---
*Desarrollado para Lisicki Litvin — Tax Audit AI v2.0*
