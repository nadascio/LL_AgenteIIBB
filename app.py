import streamlit as st
import pandas as pd
import os
from datetime import datetime
from core.database import SessionLocal, Auditoria, ResultadoActividad, ArchivoGenerado, init_db
from core.processor import AuditorProcessor
from sqlalchemy.orm import Session
import time
from core.constants import JURISDICCIONES, format_percentage
from utils.config_manager import test_connection, save_config_to_env, get_current_config, list_ollama_models

# Asegurar que la DB esté lista
init_db()

# Configuración de página
st.set_page_config(
    page_title="Lisicki Litvin - Tax Audit AI",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inyectar Estilos Premium (Tailwind + Custom)
st.markdown("""
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700;800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet"/>
    <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet"/>
    <style>
        [data-testid="stSidebar"] {
            background-color: #f4f3f8;
            border-right: 1px solid #e2e2e7;
        }
        .main {
            background-color: #f9f9fe;
        }
        h1, h2, h3 {
            font-family: 'Manrope', sans-serif !important;
            color: #001e40 !important;
        }
        .stButton>button {
            background-color: #001e40;
            color: white;
            border-radius: 4px;
            font-weight: 600;
            border: none;
            transition: all 0.2s;
        }
        .stButton>button:hover {
            background-color: #003366;
            transform: translateY(-1px);
        }
        .ll-card {
            background: white;
            padding: 1.5rem;
            border-radius: 12px;
            box-shadow: 0px 12px 32px rgba(0,30,64,0.06);
            border: 1px solid rgba(195,198,209, 0.2);
            margin-bottom: 1rem;
        }
    </style>
""", unsafe_allow_html=True)

# --- HEADER ---
def draw_header():
    st.markdown(f"""
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem; border-bottom: 1px solid #eee; padding-bottom: 1rem;">
            <div style="display: flex; align-items: center; gap: 12px;">
                <span class="material-symbols-outlined" style="color: #001e40; font-size: 32px;">account_balance</span>
                <span style="font-size: 24px; font-weight: 800; color: #001e40; font-family: 'Manrope';">Lisicki Litvin</span>
            </div>
            <div style="text-align: right;">
                <span style="color: #666; font-size: 14px;">Portal del Auditor Fiscal</span><br>
                <span style="font-weight: 700; color: #001e40;">Tax Audit AI v2.0</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("""
        <div style="padding: 1rem 0;">
            <h2 style="font-size: 1.25rem; font-weight: 800; margin-bottom: 1.5rem;">Panel de Control</h2>
        </div>
    """, unsafe_allow_html=True)
    
    menu = st.radio(
        "Navegación",
        ["Carga de Datos", "Historial de Auditorías", "⚙️ Configuración", "Guía de Uso"],
        index=0
    )
    
    st.divider()
    # Badge dinámico del estado del motor
    cfg_actual = get_current_config()
    backend_label = cfg_actual['backend'].upper()
    model_label = cfg_actual.get(f"{cfg_actual['backend']}_model", "?")
    st.markdown(f"""
    <div style="background:#f0f9ff;border:1px solid #bfdbfe;border-radius:8px;padding:0.6rem 0.75rem;font-size:0.8rem">
        <div style="font-weight:700;color:#1e40af">Motor de IA Activo</div>
        <div style="color:#374151">🤖 {backend_label} — <code>{model_label}</code></div>
    </div>
    """, unsafe_allow_html=True)

# --- LOGIC & VIEWS ---

def view_carga_datos():
    st.markdown('<h1 style="margin-top: 0;">Carga Masiva de Comprobantes</h1>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([2, 1])
    with col1:
        uploaded_file = st.file_uploader("Arrastra tu archivo Excel de auditoría aquí", type=["xlsx"])
        
    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file)
            required_cols = [
                "Cuit", "Periodo", "Condicion_IVA", "Volumen de Venta", 
                "Desc_Actividad_NAES", "Codigo_NAES", "Des_Actividad_Real", 
                "Alicuota_Anterior", "Codigo_Jurisdiccion", "Situacion_Especial"
            ]
            missing_cols = [c for c in required_cols if c not in df.columns]

            if missing_cols:
                st.error(f"⚠️ Al archivo le faltan columnas: {', '.join(missing_cols)}")
            else:
                st.success("✅ Estructura de datos validada.")
                st.dataframe(df.head(10), use_container_width=True)
                
                if st.button("Iniciar Proceso de Auditoría ✨", use_container_width=True):
                    db = SessionLocal()
                    try:
                        with st.status("Procesando Auditoría...", expanded=True) as status:
                            progress_bar = st.progress(0)
                            log_area = st.empty()
                            def update_ui(msg, progress):
                                log_area.write(msg)
                                progress_bar.progress(progress)
                            processor = AuditorProcessor(db)
                            count = processor.process_dataframe(df, progress_callback=update_ui)
                            status.update(label=f"Auditoría Finalizada: {count} clientes.", state="complete")
                        st.balloons()
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
                    finally:
                        db.close()
        except Exception as e:
            st.error(f"Error al leer el archivo: {e}")

def view_historial():
    st.markdown('<h1>Historial de Auditorías Premium</h1>', unsafe_allow_html=True)
    
    db = SessionLocal()
    auditorias = db.query(Auditoria).order_by(Auditoria.fecha_proceso.desc()).all()
    
    if not auditorias:
        st.warning("Aún no hay auditorías registradas.")
    else:
        # Agrupamos por CUIT y Periodo
        grupos = {}
        for a in auditorias:
            key = (a.cuit, a.periodo)
            if key not in grupos: grupos[key] = []
            grupos[key].append(a)
        
        for (cuit, periodo), lista_audit in grupos.items():
            fecha = lista_audit[0].fecha_proceso.strftime('%d/%m/%Y %H:%M')
            group_key = f"{cuit}_{periodo}".replace('-', '_')
            
            with st.expander(f"🏢 {cuit} | 📅 Período: {periodo} | 🕒 Últ. Proc: {fecha}"):
                
                # Mapeo de datos por jurisdicción
                juris_data = {a.provincia_id: a for a in lista_audit}
                
                st.write("### 📍 Mapa de Situación Federal")
                st.caption("Seleccioná un globito activo para ver el detalle.")
                
                selected_key = f"sel_juris_{group_key}"
                if selected_key not in st.session_state:
                    st.session_state[selected_key] = None
                
                # Grilla 3x8
                for row_idx in range(3):
                    cols = st.columns(8)
                    for col_idx in range(8):
                        juris_id = 901 + (row_idx * 8) + col_idx
                        if juris_id > 924: continue
                        
                        is_active = juris_id in juris_data
                        label = f"{juris_id}"
                        btn_key = f"btn_{group_key}_{juris_id}"
                        
                        with cols[col_idx]:
                            if is_active:
                                if st.button(label, key=btn_key, use_container_width=True, help=f"Ver {JURISDICCIONES.get(juris_id)}"):
                                    st.session_state[selected_key] = juris_id
                            else:
                                st.button(label, key=btn_key, use_container_width=True, disabled=True)
                
                # --- DETALLE DINÁMICO ---
                selected_juris = st.session_state[selected_key]
                if selected_juris and selected_juris in juris_data:
                    audit = juris_data[selected_juris]
                    juris_name = JURISDICCIONES.get(selected_juris, "N/A")
                    st.markdown("---")
                    st.markdown(f"### 🔍 Detalle: {juris_name}")
                    
                    if audit.resumen_ia:
                        resumen = audit.resumen_ia
                        # Detectar si el resumen es un mensaje de error clasificado
                        is_error = any(kw in resumen for kw in ["❌", "🔑", "⚠️", "⏱️", "Error"])
                        if is_error:
                            st.markdown(f"""
                            <div style="background: #fff3f3; border-left: 4px solid #e53e3e; border-radius: 8px; padding: 1rem 1.25rem; margin-bottom: 1rem;">
                                <div style="font-weight: 700; color: #c53030; font-size: 0.9rem; margin-bottom: 4px;">Motor de IA — Diagnóstico del Error</div>
                                <div style="color: #742a2a; font-size: 0.875rem;">{resumen}</div>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.markdown(f"""
                            <div style="background: #f0f9ff; border-left: 4px solid #3b82f6; border-radius: 8px; padding: 1rem 1.25rem; margin-bottom: 1rem;">
                                <div style="font-weight: 700; color: #1e40af; font-size: 0.9rem; margin-bottom: 4px;">Dictamen del Agente LL</div>
                                <div style="color: #1e3a5f; font-size: 0.875rem;">{resumen}</div>
                            </div>
                            """, unsafe_allow_html=True)
                    
                    det_rows = []
                    for r in audit.resultados:
                        det_rows.append({
                            "Actividad": r.actividad_desc,
                            "Base": format_percentage(r.alicuota_base),
                            "Dictamen LL": format_percentage(getattr(r, 'alicuota_ia', r.alicuota_sugerida)),
                            "Justificación": r.justificacion
                        })
                    if det_rows:
                        st.table(pd.DataFrame(det_rows))
                        
                        if audit.archivos:
                            st.write("#### 📦 Reportes")
                            rccols = st.columns(4)
                            for idx, arch in enumerate(audit.archivos):
                                if os.path.exists(arch.ruta_archivo):
                                    with open(arch.ruta_archivo, "rb") as f:
                                        label = "📄 Word" if arch.tipo == "WORD" else "📊 Excel"
                                        rccols[idx % 4].download_button(
                                            label=f"{label}",
                                            data=f.read(),
                                            file_name=arch.nombre_archivo,
                                            key=f"dl_ind_{arch.id}_{idx}_{group_key}"
                                        )

                # --- TABLA MAESTRA CONSOLIDADA ---
                st.markdown("---")
                st.write("### 🏢 Consolidado Maestro Completo")
                master_rows = []
                for audit in lista_audit:
                    j_name = JURISDICCIONES.get(audit.provincia_id, f"{audit.provincia_id}")
                    for r in audit.resultados:
                        master_rows.append({
                            "Juris": j_name,
                            "Actividad": r.actividad_desc,
                            "Base": format_percentage(r.alicuota_base),
                            "IA": format_percentage(getattr(r, 'alicuota_ia', r.alicuota_sugerida)),
                        })
                if master_rows:
                    st.dataframe(pd.DataFrame(master_rows), use_container_width=True, hide_index=True)
    db.close()

def view_guia():
    st.markdown('<h1>Guía de Uso</h1>', unsafe_allow_html=True)
    st.markdown("""
    1. **Prepara tu Excel**: Usa la plantilla LL.
    2. **Sube el archivo**: Procesa en la pestaña de Carga.
    3. **Navega el Mapa**: En el historial, usa la grilla 901-924.
    4. **Consolidado**: Revisa la tabla final para la foto general.
    """)


STATUS_COLORS = {
    "ok":          ("🟢", "#dcfce7", "#166534", "Conectado"),
    "quota_error": ("⚠️", "#fef9c3", "#854d0e", "Cuota agotada"),
    "auth_error":  ("🔑", "#fee2e2", "#991b1b", "Clave inválida"),
    "not_found":   ("❌", "#fee2e2", "#991b1b", "Modelo no encontrado"),
    "error":       ("🔴", "#fce7f3", "#9d174d", "Error de conexión"),
}

def view_configuracion():
    st.markdown('<h1 style="margin-top:0">⚙️ Configuración del Motor de IA</h1>', unsafe_allow_html=True)
    cfg = get_current_config()

    # ── Sección 1: Selector de Backend ──────────────────────────────────────
    st.markdown("### 🤖 Backend de Inteligencia Artificial")
    backends = ["gemini", "ollama", "openai"]
    backend_labels = {"gemini": "☁️ Google Gemini", "ollama": "💻 Ollama (Local / Gratis)", "openai": "🌐 OpenAI"}
    backend_idx = backends.index(cfg["backend"]) if cfg["backend"] in backends else 0

    backend_sel = st.radio(
        "Seleccioná el motor de IA:",
        backends,
        index=backend_idx,
        format_func=lambda x: backend_labels[x],
        horizontal=True,
        key="cfg_backend"
    )

    st.divider()

    # ── Sección 2: Parámetros dinámicos según backend ───────────────────────
    model_sel = ""
    api_key_sel = ""
    base_url_sel = ""

    if backend_sel == "gemini":
        st.markdown("#### Configuración de Google Gemini")
        col1, col2 = st.columns([2, 1])
        with col1:
            api_key_sel = st.text_input(
                "API Key", value=cfg["gemini_api_key"],
                type="password", key="cfg_gemini_key",
                help="Obtenela en https://aistudio.google.com"
            )
        with col2:
            gemini_models = ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"]
            default_idx = gemini_models.index(cfg["gemini_model"]) if cfg["gemini_model"] in gemini_models else 0
            model_sel = st.selectbox("Modelo", gemini_models, index=default_idx, key="cfg_gemini_model")

    elif backend_sel == "ollama":
        st.markdown("#### Configuración de Ollama (Local)")
        col1, col2 = st.columns([2, 1])
        with col1:
            base_url_sel = st.text_input(
                "URL del servidor Ollama",
                value=cfg["ollama_base_url"],
                key="cfg_ollama_url"
            )
        with col2:
            # Intentar listar modelos instalados
            ollama_available = list_ollama_models(base_url_sel or cfg["ollama_base_url"])
            if ollama_available:
                default_ollama = cfg["ollama_model"] if cfg["ollama_model"] in ollama_available else ollama_available[0]
                model_sel = st.selectbox("Modelo instalado", ollama_available,
                                         index=ollama_available.index(default_ollama), key="cfg_ollama_model")
            else:
                model_sel = st.text_input("Nombre del modelo", value=cfg["ollama_model"], key="cfg_ollama_model_txt")

        with st.expander("📦 ¿No tenés Ollama? Ver instrucciones de instalación"):
            st.markdown("""
            1. **Descargar Ollama**: [https://ollama.ai](https://ollama.ai) (Windows/Mac/Linux)
            2. **Instalar un modelo** (elegí uno según tu RAM):

            | Modelo | RAM mínima | Calidad en Español | Comando |
            |--------|-----------|-------------------|----------|
            | `qwen2.5:7b` | 8 GB | ⭐⭐⭐⭐⭐ | `ollama pull qwen2.5:7b` |
            | `llama3.1:8b` | 8 GB | ⭐⭐⭐⭐ | `ollama pull llama3.1:8b` |
            | `mistral:7b` | 8 GB | ⭐⭐⭐ | `ollama pull mistral:7b` |
            | `qwen2.5:3b` | 4 GB | ⭐⭐⭐ | `ollama pull qwen2.5:3b` |

            3. **Iniciar el servidor**: `ollama serve` (queda corriendo en background)
            4. **Seleccionarlo aquí** y hacer clic en "Probar Conexión"
            """)

    elif backend_sel == "openai":
        st.markdown("#### Configuración de OpenAI")
        col1, col2 = st.columns([2, 1])
        with col1:
            api_key_sel = st.text_input(
                "API Key de OpenAI", value=cfg["openai_api_key"],
                type="password", key="cfg_openai_key"
            )
        with col2:
            openai_models = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]
            default_oai_idx = openai_models.index(cfg["openai_model"]) if cfg["openai_model"] in openai_models else 0
            model_sel = st.selectbox("Modelo", openai_models, index=default_oai_idx, key="cfg_openai_model")

    st.divider()

    # ── Sección 3: Botones de acción ─────────────────────────────────────────
    col_save, col_test, col_spacer = st.columns([1, 1, 2])

    with col_save:
        if st.button("💾 Guardar Configuración", use_container_width=True, key="cfg_save_btn"):
            ok = save_config_to_env(
                backend=backend_sel,
                model=model_sel,
                api_key=api_key_sel,
                base_url=base_url_sel
            )
            if ok:
                st.success("✅ Configuración guardada. Reiniciá el servidor para aplicarla.")
            else:
                st.error("❌ No se pudo guardar la configuración.")

    with col_test:
        test_btn = st.button("🔌 Probar Conexión", use_container_width=True, key="cfg_test_btn")

    # ── Sección 4: Resultado del test ────────────────────────────────────────
    if test_btn:
        with st.spinner("Probando conexión..."):
            result = test_connection(
                backend=backend_sel,
                model=model_sel or cfg.get(f"{backend_sel}_model", ""),
                api_key=api_key_sel or cfg.get(f"{backend_sel}_api_key", ""),
                base_url=base_url_sel or cfg.get("ollama_base_url", "http://localhost:11434")
            )

        icon, bg, fg, label = STATUS_COLORS.get(result["status"], STATUS_COLORS["error"])
        latency_txt = f" | Latencia: {result['latency_ms']}ms" if result.get('latency_ms') else ""

        st.markdown(f"""
        <div style="background:{bg};border-radius:10px;padding:1rem 1.25rem;margin-top:1rem">
            <div style="font-size:1.1rem;font-weight:800;color:{fg}">{icon} {label}{latency_txt}</div>
            <div style="color:{fg};margin-top:4px">{result['message']}</div>
        </div>
        """, unsafe_allow_html=True)

        if result.get("models") and backend_sel == "ollama":
            st.markdown("**Modelos Ollama disponibles:**")
            for m in result["models"]:
                st.code(m, language=None)


# --- RENDER ---
draw_header()
if menu == "Carga de Datos": view_carga_datos()
elif menu == "Historial de Auditorías": view_historial()
elif menu == "⚙️ Configuración": view_configuracion()
else: view_guia()
