import streamlit as st
import pandas as pd
import os
import logging
from datetime import datetime
import base64
from core.database import SessionLocal, Auditoria, ResultadoActividad, ArchivoGenerado, init_db
from core.processor import AuditorProcessor
from sqlalchemy.orm import Session
import time
from utils.config_manager import test_connection, save_config_to_env, get_current_config, list_ollama_models

# Asegurar que la DB esté lista
init_db()

# --- DEPURACIÓN Y HELPERS ---
def get_base64_logo(name):
    """Codifica un logo local en base64 para inyección HTML."""
    try:
        path = os.path.join("assets", f"{name}.png")
        if os.path.exists(path):
            with open(path, "rb") as f:
                data = f.read()
            return f"data:image/png;base64,{base64.b64encode(data).decode()}"
    except Exception:
        pass
    return ""

# Configuración de página
st.set_page_config(
    page_title="Lisicki Litvin - Tax Audit AI",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ESTILOS ESTABLES ---
st.markdown("""
    <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet"/>
    <style>
        .stButton>button {
            border-radius: 4px;
            font-weight: 600;
        }
        /* Ajuste de contenedor principal */
        .main {
            padding-top: 2rem;
        }
        /* SIDEBAR — NAVEGACIÓN: BOTONES JUNTOS */
        [data-testid="stSidebar"] .stButton {
            margin-bottom: 4px !important;
        }
        
        /* 📏 LÍNEA DIVISORIA SOBRIA */
        [data-testid="stSidebar"] {
            border-right: 1px solid #d1d1d1 !important;
        }
        
        /* 📦 CAJA DE CARGA (UPLOADER) — RECTIFICACIÓN NUCLEAR */
        [data-testid="stFileUploaderDropzone"] {
            border: 2px dashed #94a3b8 !important;
            border-radius: 12px !important;
            padding: 2.5rem !important;
            background-color: #f8fafc !important;
            transition: all 0.3s ease;
            position: relative;
        }
        [data-testid="stFileUploaderDropzone"]:hover {
            border-color: #10b981 !important;
            background-color: #f0fdf4 !important;
        }
        
        /* Ocultar textos originales y meter la LEYENDA */
        [data-testid="stFileUploaderDropzone"] div[data-testid="stFileDropzoneInstructions"] span,
        [data-testid="stFileUploaderDropzone"] div[data-testid="stFileDropzoneInstructions"] small {
            display: none !important;
        }
        [data-testid="stFileUploaderDropzone"]::before {
            content: "Arrastrar o Subir Archivo" !important;
            display: block !important;
            font-size: 1.25rem !important;
            font-weight: 700 !important;
            color: #001e40 !important;
            margin-bottom: 0.5rem !important;
            text-align: center !important;
        }
        
        /* El Botón de Upload */
        [data-testid="stFileUploaderDropzone"] button {
            background-color: #ffffff !important;
            border: 1px solid #e2e8f0 !important;
            color: #1e293b !important;
            visibility: hidden;
            position: relative;
            padding: 10px 20px !important;
            margin: 0 auto !important;
            display: block !important;
        }
        [data-testid="stFileUploaderDropzone"] button::after {
            content: "Upload";
            visibility: visible;
            position: absolute;
            left: 50%;
            top: 50%;
            transform: translate(-50%, -50%);
            font-weight: 700;
            color: #001e40;
        }
        
        /* 🖼️ FIX LOGOS V2 — SOLO EN CONFIGURACIÓN (EXCLUYE SIDEBAR) */
        div.main div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] {
            display: flex !important;
            align-items: center !important;
            gap: 4px !important;
        }
        div.main div[role="radiogroup"] label div[data-testid="stMarkdownContainer"]::before {
            content: "" !important;
            display: inline-block !important;
            width: 24px !important;
            height: 24px !important;
            margin-right: 12px !important;
            vertical-align: middle !important;
            background-size: contain !important;
            background-repeat: no-repeat !important;
            background-position: center !important;
            flex-shrink: 0 !important;
        }
        
        div.main div[role="radiogroup"] label:nth-of-type(1) div[data-testid="stMarkdownContainer"]::before { background-image: url('""" + get_base64_logo("Gemini_v2") + """') !important; }
        div.main div[role="radiogroup"] label:nth-of-type(2) div[data-testid="stMarkdownContainer"]::before { background-image: url('""" + get_base64_logo("Ollama") + """') !important; }
        div.main div[role="radiogroup"] label:nth-of-type(3) div[data-testid="stMarkdownContainer"]::before { background-image: url('""" + get_base64_logo("OpenAI_v2") + """') !important; }
        div.main div[role="radiogroup"] label:nth-of-type(4) div[data-testid="stMarkdownContainer"]::before { background-image: url('""" + get_base64_logo("Claude_v2") + """') !important; }
    </style>
""", unsafe_allow_html=True)

# --- HEADER SIMPLE ---
def draw_header():
    st.markdown(f"""
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem; border-bottom: 1px solid #eee; padding-bottom: 1rem;">
            <div style="display: flex; align-items: center; gap: 12px;">
                <span class="material-symbols-outlined" style="color: #001e40; font-size: 32px;">account_balance</span>
                <span style="font-size: 24px; font-weight: 800; color: #001e40;">Lisicki Litvin</span>
            </div>
            <div style="text-align: right;">
                <span style="color: #666; font-size: 14px;">Portal del Auditor Fiscal</span><br>
                <span style="font-weight: 700; color: #001e40;">IIBB Tax Audit LL V1.0.0</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

# --- VISTAS ---

def view_carga_datos():
    st.markdown('<h1 style="margin-top: 0;">Carga de Archivo de Auditoría Fiscal</h1>', unsafe_allow_html=True)
    st.markdown("<p style='color:#666; margin-bottom:1.5rem'>Suba el archivo con el detalle de las actividades a consultar por jurisdicción del cliente.</p>", unsafe_allow_html=True)

    col_up, col_tpl = st.columns([3, 1])
    with col_up:
        uploaded_file = st.file_uploader("Arrastra o sube tu archivo Excel de auditoría aquí", type=["xlsx"], label_visibility="collapsed")
    with col_tpl:
        st.markdown('<p style="font-weight: 700; color: #001e40; margin-bottom: 0.5rem;">📥 Descarga Plantilla Modelo</p>', unsafe_allow_html=True)
        st.markdown('<p style="font-size: 0.8rem; color: #64748b; margin-bottom: 1rem;">Modelo a completar para importar sus actividades.</p>', unsafe_allow_html=True)
        try:
            with open("Plantilla_Auditoria_Modelo.xlsx", "rb") as f:
                st.download_button(
                    label="📥 Descargar Plantilla",
                    data=f.read(),
                    file_name="Plantilla_Auditoria_Modelo.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
        except:
            st.warning("⚠️ Plantilla no encontrada")
        
    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file)
            required_cols = [
                "Cuit", "Periodo", "Condicion_IVA", "Volumen de Venta", 
                "Desc_Actividad_NAES", "Codigo_NAES", "Des_Actividad_Real", 
                "Alicuota_Anterior", "Codigo_Jurisdiccion", "Situacion_Especial"
            ]
            missing_cols = [c for c in required_cols if c not in df.columns]
            
            if not missing_cols:
                st.success(f"✅ Archivo '{uploaded_file.name}' listo para procesar. ({len(df)} registros encontrados)")
                if st.button("🚀 INICIAR AUDITORÍA", use_container_width=True):
                    with st.spinner("🤖 El Agente está analizando las normativas jurisdiccionales..."):
                        db = SessionLocal()
                        try:
                            processor = AuditorProcessor(db=db)
                            processor.process_dataframe(df)
                            db.commit()
                            st.balloons()
                            st.success("✅ Auditoría completada con éxito.")
                            if st.button("🔎 Ver Resultado en Historial", use_container_width=True):
                                st.session_state.selected_menu = "Historial de Auditorías"
                                st.rerun()
                        except Exception as e:
                            db.rollback()
                            st.error(f"❌ Error durante la auditoría: {e}")
                        finally:
                            db.close()
            else:
                st.error(f"❌ El archivo no cumple con el formato requerido. Columnas faltantes: {', '.join(missing_cols)}")
        except Exception as e:
            st.error(f"Error al leer el archivo: {e}")

def view_historial():
    st.markdown('<h1>Historial de Auditorías</h1>', unsafe_allow_html=True)

    db = SessionLocal()
    auditorias = db.query(Auditoria).order_by(Auditoria.id.desc()).all()

    if not auditorias:
        st.info("No hay auditorías registradas aún.")
        db.close()
        return

    # Selector de Auditoría
    options = [f"🏢 CUIT: {a.cuit} | Ejercicio: {a.periodo} | ID: {a.id}" for a in auditorias]
    selected_label = st.selectbox("Seleccione una auditoría:", options)
    selected_id = int(selected_label.split("ID: ")[1])
    audit = db.query(Auditoria).filter(Auditoria.id == selected_id).first()

    if audit:
        st.divider()

        # Info general
        col1, col2, col3 = st.columns(3)
        col1.metric("CUIT", audit.cuit)
        col2.metric("Ejercicio", audit.periodo)
        col3.metric("Estado", audit.estado or "—")

        if audit.resumen_ia:
            st.info(f"**🤖 Resumen IA:**\n\n{audit.resumen_ia}")

        # Resultados de actividades
        resultados = db.query(ResultadoActividad).filter(ResultadoActividad.auditoria_id == audit.id).all()

        if resultados:
            st.markdown("### 📋 Actividades Auditadas")
            df_res = pd.DataFrame([{
                "Actividad":          r.actividad_desc or "—",
                "NAES":               r.naes or "—",
                "Alíc. Base (%)":     r.alicuota_base,
                "Alíc. Sugerida (%)": r.alicuota_sugerida,
                "Alíc. IA (%)":       r.alicuota_ia,
                "Normativa":          r.normativa_ref or "—",
            } for r in resultados])
            st.dataframe(df_res, use_container_width=True)

            # Detalle por actividad
            with st.expander("📄 Ver justificaciones IA por actividad"):
                for r in resultados:
                    st.markdown(f"**{r.actividad_desc or r.naes}**")
                    st.write(r.justificacion or "Sin justificación registrada.")
                    st.divider()
        else:
            st.warning("Esta auditoría no tiene actividades registradas.")

        # Archivos descargables
        if audit.archivos:
            st.markdown("### 📥 Reportes Generados")
            for arch in audit.archivos:
                try:
                    with open(arch.ruta_archivo, "rb") as f:
                        st.download_button(
                            f"Descargar {arch.tipo} — {arch.nombre_archivo}",
                            f.read(),
                            arch.nombre_archivo,
                            key=f"dl_{arch.id}"
                        )
                except FileNotFoundError:
                    st.warning(f"Archivo no encontrado: {arch.nombre_archivo}")

        # Acciones avanzadas
        st.divider()
        if st.checkbox("⚙️ Acciones Avanzadas"):
            if st.button("🗑️ Eliminar TODA esta auditoría", use_container_width=True):
                db.query(ArchivoGenerado).filter(ArchivoGenerado.auditoria_id == audit.id).delete()
                db.query(ResultadoActividad).filter(ResultadoActividad.auditoria_id == audit.id).delete()
                db.query(Auditoria).filter(Auditoria.id == audit.id).delete()
                db.commit()
                st.success("Auditoría eliminada.")
                st.rerun()

    db.close()

def view_guia():
    st.markdown("## 📖 Guía de Operación del Agente")
    st.markdown("""
    Este sistema asiste en la auditoría de Ingresos Brutos. 
    Para garantizar resultados óptimos, siga este protocolo:
    """)

    col1, col2 = st.columns(2)
    with col1:
        st.info("""
        ### 1. Preparación del Archivo
        Utilice siempre la **Plantilla Modelo**. Asegúrese de completar:
        - **Cuit**: Sin guiones (preferencialmente).
        - **Periodo**: Año fiscal (Ej: 2026).
        - **Volumen de Venta**: Monto base para la alícuota.
        """)
    with col2:
        st.info("""
        ### 2. Procesamiento
        Una vez cargado el archivo:
        - El Agente validará la estructura.
        - Se iniciará el motor de IA para cruzar con normativas.
        - El resultado se guardará en el **Historial**.
        """)

    st.divider()
    st.markdown("### 📥 Descarga Plantilla Modelo")
    st.markdown("Descargue el archivo Excel base para completar con los datos del contribuyente antes de realizar la carga.")
    try:
        with open("Plantilla_Auditoria_Modelo.xlsx", "rb") as f:
            st.download_button(
                label="📥 Descargar Plantilla Oficial",
                data=f.read(),
                file_name="Plantilla_Auditoria_Modelo.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    except:
        st.error("No se encontró el archivo de plantilla.")

    st.markdown("---")
    st.markdown("### 📋 Glosario de Columnas (Estructura Base)")
    st.write("""
    | Columna | Descripción del Contenido | Ejemplo |
    | :--- | :--- | :--- |
    | **Cuit** | CUIT del contribuyente (numérico o con guiones). | 30-71452638-9 |
    | **Periodo** | Año fiscal objeto de la auditoría. | 2026 |
    | **Condicion_IVA** | Encuadre impositivo del cliente. | Responsable Inscripto |
    | **Volumen de Venta** | Monto base facturado total en el ejercicio. | 1500000.50 |
    | **Desc_Actividad_NAES** | Descripción oficial según el nomenclador. | Venta al por menor de... |
    | **Codigo_NAES** | Código numérico de la actividad (NAES). | 466932 |
    | **Des_Actividad_Real** | Descripción de la actividad según el cliente. | Fabricación de insumos |
    | **Alicuota_Anterior** | Alícuota que venía aplicando el cliente. | 3.5 |
    | **Codigo_Jurisdiccion** | Número de jurisdicción (ej: 901 para CABA). | 902 |
    | **Situacion_Especial** | Comentarios para la IA (exenciones, bases). | Exento por ley local |
    """)

def view_configuracion():
    st.markdown('<h1>Configuración del Sistema</h1>', unsafe_allow_html=True)
    
    if 'config_auth' not in st.session_state:
        st.session_state.config_auth = False

    if not st.session_state.get('config_auth'):
        st.markdown('<div style="max-width: 400px; margin: 0 auto; padding: 2rem; border: 1px solid #eee; border-radius: 12px; text-align: center;">', unsafe_allow_html=True)
        st.write("### 🔒 Acceso Restringido")
        pw = st.text_input("Contraseña de Administrador", type="password", key="pw_config_input")
        if st.button("🔑 Desbloquear", use_container_width=True):
            if pw == "1234":
                st.session_state.config_auth = True
                st.rerun()
            else:
                st.error("Contraseña incorrecta")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    st.markdown("### ⚙️ Configuración del Motor de IA")
    cfg = get_current_config()
    
    # Selector de Backend con Logos
    backends = ["gemini", "ollama", "openai", "anthropic"]
    backend_labels = {
        "gemini": "Gemini", 
        "ollama": "Ollama", 
        "openai": "OpenAI",
        "anthropic": "Claude"
    }
    backend_idx = backends.index(cfg["backend"]) if cfg["backend"] in backends else 0
    backend_sel = st.radio("Motor de Inteligencia Artificial:", backends, index=backend_idx, format_func=lambda x: backend_labels[x], horizontal=True)

    st.divider()
    
    # Campos dinámicos
    model_sel = ""
    api_key_sel = ""
    base_url_sel = ""

    if backend_sel == "gemini":
        col1, col2 = st.columns([2, 1])
        with col1:
            api_key_sel = st.text_input("API Key (Gemini)", value=cfg["gemini_api_key"], type="password")
        with col2:
            gemini_models = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
            model_sel = st.selectbox("Modelo", gemini_models, index=gemini_models.index(cfg["gemini_model"]) if cfg["gemini_model"] in gemini_models else 0)

    elif backend_sel == "ollama":
        col1, col2 = st.columns([2, 1])
        with col1:
            base_url_sel = st.text_input("URL del Servidor Ollama", value=cfg["ollama_base_url"])
        with col2:
            ollama_available = list_ollama_models(base_url_sel)
            if ollama_available:
                model_sel = st.selectbox("Modelo Instalado", ollama_available, index=ollama_available.index(cfg["ollama_model"]) if cfg["ollama_model"] in ollama_available else 0)
            else:
                model_sel = st.text_input("Nombre del Modelo", value=cfg["ollama_model"])
        with st.expander("❓ Ayuda Ollama"):
            st.markdown("Asegúrese de tener Ollama corriendo (`ollama serve`) y el modelo descargado (`ollama pull qwen2.5:7b`).")

    elif backend_sel == "openai":
        col1, col2 = st.columns([2, 1])
        with col1:
            api_key_sel = st.text_input("API Key (OpenAI)", value=cfg["openai_api_key"], type="password")
        with col2:
            openai_models = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"]
            model_sel = st.selectbox("Modelo", openai_models, index=openai_models.index(cfg["openai_model"]) if cfg["openai_model"] in openai_models else 0)

    elif backend_sel == "anthropic":
        col1, col2 = st.columns([2, 1])
        with col1:
            api_key_sel = st.text_input("API Key (Anthropic)", value=cfg["anthropic_api_key"], type="password")
        with col2:
            anthropic_models = ["claude-3-5-sonnet-20240620", "claude-3-opus-20240229", "claude-3-sonnet-20240229"]
            model_sel = st.selectbox("Modelo", anthropic_models, index=anthropic_models.index(cfg["anthropic_model"]) if cfg["anthropic_model"] in anthropic_models else 0)

    st.divider()
    
    # Acciones
    c_save, c_test, _ = st.columns([1, 1, 2])
    with c_save:
        if st.button("💾 Guardar Cambios", use_container_width=True):
            save_config_to_env(backend=backend_sel, model=model_sel, api_key=api_key_sel, base_url=base_url_sel)
            if 'processor' in st.session_state: del st.session_state.processor
            st.success("✅ Configuración guardada.")
            st.rerun()
    
    with c_test:
        if st.button("🔌 Probar Conexión", use_container_width=True):
            with st.spinner("Conectando..."):
                res = test_connection(backend=backend_sel, model=model_sel, api_key=api_key_sel, base_url=base_url_sel)
                if res["status"] == "success":
                    st.success(f"🟢 Conexión Exitosa ({res['latency_ms']}ms)")
                else:
                    st.error(f"🔴 Error: {res['message']}")

    # Mantenimiento
    st.markdown("<br><br>", unsafe_allow_html=True)
    with st.expander("⚠️ Zona de Peligro (Auditorías)"):
        st.warning("Esto borrará permanentemente todo el historial de auditorías.")
        if st.button("🗑️ Borrar Todo el Historial", use_container_width=True):
            from core.database import clear_all_audits
            db = SessionLocal()
            clear_all_audits(db)
            db.close()
            st.success("Historial eliminado.")
            st.rerun()
    
    if st.button("🔒 Bloquear y Salir", use_container_width=True):
        st.session_state.config_auth = False
        st.rerun()

# --- RENDER ---
draw_header()

with st.sidebar:
    st.markdown("## 🔍 IIBB Tax Audit LL")

    nav_items = [
        ("📤 Carga de Datos",          "Carga de Datos"),
        ("📊 Historial de Auditorías", "Historial de Auditorías"),
        ("📖 Guía de Uso",             "Guía de Uso"),
        ("⚙️ Configuración",           "Configuración"),
    ]

    if 'selected_menu' not in st.session_state:
        st.session_state.selected_menu = "Carga de Datos"

    for label, key in nav_items:
        if st.button(label, key=f"nav_{key}", use_container_width=True):
            st.session_state.selected_menu = key
            st.rerun()

    selected_menu = st.session_state.selected_menu
    
    st.divider()
    cfg = get_current_config()
    backend_key = cfg['backend'].lower()
    
    # Mapeo de estilos por backend (Logos Locales en Base64)
    STYLE_MAP = {
        "ollama": {
            "icon": get_base64_logo("Ollama"), 
            "color": "#22c55e", 
            "label": "Ollama (Local)"
        },
        "gemini": {
            "icon": get_base64_logo("Gemini_v2"), 
            "color": "#3b82f6", 
            "label": "Google Gemini"
        },
        "openai": {
            "icon": get_base64_logo("OpenAI_v2"), 
            "color": "#10b981", 
            "label": "OpenAI"
        },
        "anthropic": {
            "icon": get_base64_logo("Claude_v2"), 
            "color": "#d97706", 
            "label": "Claude"
        }
    }
    
    info = STYLE_MAP.get(backend_key, {"icon": "🤖", "color": "#64748b", "label": backend_key.upper()})
    active_model = cfg.get(f"{backend_key}_model", "Desconocido")
    
    st.markdown(f"""
    <div style="background:{info['color']}15; border:1px solid {info['color']}; border-radius:10px; padding:0.75rem; margin-top:1rem;">
        <div style="font-size:0.85rem; font-weight:700; color:{info['color']}; display:flex; align-items:center; gap:10px;">
            <img src="{info['icon']}" width="22" style="border-radius:4px;"> {info['label']}
        </div>
        <div style="font-size:0.75rem; color:#475569; margin-top:6px; font-family: monospace; padding-left: 32px;">
            Modelo: <b>{active_model}</b>
        </div>
        <div style="font-size:0.7rem; color:{info['color']}; margin-top:4px; font-weight:600; padding-left: 32px;">
            Estado: Operativo 🟢
        </div>
    </div>
    """, unsafe_allow_html=True)

if selected_menu == "Carga de Datos":
    view_carga_datos()
elif selected_menu == "Historial de Auditorías":
    view_historial()
elif selected_menu == "Guía de Uso":
    view_guia()
elif selected_menu == "Configuración":
    view_configuracion()
