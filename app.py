import streamlit as st
import pandas as pd
import os
import logging
from datetime import datetime
import base64
from core.database import SessionLocal, Auditoria, ResultadoActividad, ArchivoGenerado, ActivityLog, init_db, log_actividad
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
    logo_b64 = get_base64_logo("logo_ll_digital")
    logo_html = (
        f'<img src="{logo_b64}" style="height:64px; object-fit:contain;">'
        if logo_b64 else
        '<span style="font-size:24px;font-weight:800;color:#1a3a6b;">LL Digital</span>'
    )
    st.markdown(f"""
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:2rem; border-bottom:2px solid #e8edf4; padding-bottom:1.2rem;">
            {logo_html}
            <div style="text-align:right;">
                <span style="color:#888; font-size:13px; letter-spacing:0.02em;">Portal del Auditor Fiscal</span><br>
                <span style="font-weight:700; color:#001e40; font-size:15px;">IIBB Tax Audit LL V1.0.0</span>
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
                            cuits_archivo = df["Cuit"].astype(str).unique().tolist()
                            periodos_archivo = df["Periodo"].astype(str).unique().tolist()
                            log_actividad(db, "CONSULTA_INICIADA",
                                detalle=f"Archivo: {uploaded_file.name} | "
                                        f"CUITs: {', '.join(cuits_archivo)} | "
                                        f"Períodos: {', '.join(periodos_archivo)} | "
                                        f"Registros: {len(df)}")
                            processor = AuditorProcessor(db=db)
                            processor.process_dataframe(df)
                            db.commit()
                            log_actividad(db, "CONSULTA_COMPLETADA",
                                detalle=f"Archivo: {uploaded_file.name} | {len(df)} registro(s) procesado(s)")
                            st.balloons()
                            st.session_state.auditoria_completada = True
                        except Exception as e:
                            db.rollback()
                            log_actividad(db, "CONSULTA_ERROR",
                                detalle=f"Archivo: {uploaded_file.name} | Error: {str(e)[:200]}")
                            st.error(f"❌ Error durante la auditoría: {e}")
                            st.session_state.auditoria_completada = False
                        finally:
                            db.close()

                if st.session_state.get("auditoria_completada"):
                    st.success("✅ Auditoría completada con éxito.")
                    if st.button("🔎 Ver Resultado en Historial", use_container_width=True):
                        st.session_state.auditoria_completada = False
                        st.session_state.selected_menu = "Historial de Auditorías"
                        st.rerun()
            else:
                st.error(f"❌ El archivo no cumple con el formato requerido. Columnas faltantes: {', '.join(missing_cols)}")
        except Exception as e:
            st.error(f"Error al leer el archivo: {e}")

def _render_validacion(juris_code, all_items, db):
    """Formulario de validación humana para todas las actividades de una jurisdicción."""
    from datetime import datetime as _dt
    from memory.case_history import CaseHistory

    if not all_items:
        return

    # Estado actual de validación
    val_estados = [getattr(i["resultado"], "validacion_estado", "PENDIENTE") for i in all_items]
    todas_validadas = all(e in {"ACEPTADO", "MODIFICADO"} for e in val_estados)

    with st.expander("📝 Validación de Criterios" + (" — ✅ Completada" if todas_validadas else " — ⏳ Pendiente"), expanded=not todas_validadas):

        if todas_validadas:
            st.success("Esta jurisdicción ya fue validada. Podés revisar o corregir las decisiones tomadas.")
            # Mostrar resumen de lo validado
            for i in all_items:
                r = i["resultado"]
                est = getattr(r, "validacion_estado", "—")
                ali_v = getattr(r, "alicuota_validada", None)
                com_v = getattr(r, "comentario_validacion", "") or ""
                fecha_v = getattr(r, "fecha_validacion", None)
                validado_por = getattr(r, "validado_por", None) or "—"
                equipo = getattr(r, "equipo_validacion", None) or "—"
                icon = "✅" if est == "ACEPTADO" else "⚠️"
                fecha_str = fecha_v.strftime("%d/%m/%Y %H:%M") if fecha_v else "—"
                st.markdown(
                    f'{icon} **{r.actividad_desc or r.naes}** — '
                    f'Alíc. validada: **{ali_v:.2f}%**'
                )
                st.caption(
                    f"👤 {validado_por} · 🏢 {equipo} · 📅 {fecha_str}"
                    + (f"\n💬 {com_v}" if com_v else "")
                )
            st.divider()
            if not st.checkbox("🔄 Modificar validación", key=f"reabrir_val_{juris_code}"):
                return

        st.caption("Revisá el dictamen de la IA y confirmá o modificá la alícuota para cada actividad. "
                   "El comentario es **obligatorio** cuando se modifica el criterio.")

        with st.form(key=f"form_val_{juris_code}"):
            decisiones = []

            for idx, i in enumerate(all_items):
                r = i["resultado"]
                audit = i["audit"]
                alicuota_ia = r.alicuota_ia or r.alicuota_sugerida or 0.0
                ant = getattr(r, "alicuota_anterior", None)
                ant_str = f" | Anterior: {ant:.2f}%" if ant else ""
                val_prev = getattr(r, "validacion_estado", "PENDIENTE")
                ali_val_prev = getattr(r, "alicuota_validada", None) or alicuota_ia
                com_prev = getattr(r, "comentario_validacion", "") or ""

                st.markdown(f"**Actividad {idx + 1}:** {r.actividad_desc or r.naes or '—'}")
                st.caption(f"Alíc. IA: **{alicuota_ia:.2f}%**{ant_str} | {r.normativa_ref or '—'}")

                col_radio, col_num = st.columns([2, 1])
                with col_radio:
                    default_idx = 1 if val_prev == "MODIFICADO" else 0
                    accion = st.radio(
                        "Decisión:",
                        ["✅ Acepto el criterio IA", "📝 Modifico la alícuota"],
                        index=default_idx,
                        key=f"val_radio_{r.id}",
                        horizontal=True,
                    )
                with col_num:
                    # Nota: dentro de st.form el `disabled` no reacciona al radio —
                    # siempre habilitamos el campo; la lógica de cuál valor usar
                    # se resuelve en el submit según la opción del radio.
                    nueva_alicuota = st.number_input(
                        "Nueva alícuota (%):",
                        min_value=0.0, max_value=100.0,
                        value=float(ali_val_prev),
                        step=0.01,
                        format="%.2f",
                        key=f"val_num_{r.id}",
                    )

                comentario = st.text_area(
                    "Comentario (obligatorio si modificás la alícuota):",
                    value=com_prev,
                    placeholder="Ej: Se aplica tasa reducida por Decreto 123/26 — el tramo de volumen "
                                "cambia respecto a lo determinado por la IA...",
                    key=f"val_com_{r.id}",
                    height=80,
                )

                decisiones.append({
                    "resultado": r,
                    "audit": audit,
                    "alicuota_ia": alicuota_ia,
                    "accion": accion,
                    "nueva_alicuota": nueva_alicuota,
                    "comentario": comentario,
                })

                if idx < len(all_items) - 1:
                    st.divider()

            submitted = st.form_submit_button(
                "✅ Confirmar validación de esta jurisdicción",
                use_container_width=True,
                type="primary",
            )

            if submitted:
                # Validar: comentario obligatorio si modifica
                errores = []
                for d in decisiones:
                    if d["accion"] == "📝 Modifico la alícuota" and not d["comentario"].strip():
                        errores.append(f"• **{d['resultado'].actividad_desc or d['resultado'].naes}**: el comentario es obligatorio al modificar.")

                if errores:
                    st.error("Corregí los siguientes errores antes de confirmar:\n\n" + "\n".join(errores))
                else:
                    # Identidad del validador — en el futuro vendrá del sistema de usuarios
                    USUARIO_ACTUAL = "Especialista"
                    EQUIPO_ACTUAL  = "Lisicki Litvin"

                    case_history = CaseHistory()
                    for d in decisiones:
                        r = d["resultado"]
                        acepta = d["accion"] == "✅ Acepto el criterio IA"
                        ali_final = d["alicuota_ia"] if acepta else d["nueva_alicuota"]
                        com_final = d["comentario"].strip() or ("Criterio IA aceptado sin modificaciones." if acepta else "")

                        r.validacion_estado   = "ACEPTADO" if acepta else "MODIFICADO"
                        r.alicuota_validada   = ali_final
                        r.comentario_validacion = com_final
                        r.fecha_validacion    = _dt.now()
                        r.validado_por        = USUARIO_ACTUAL
                        r.equipo_validacion   = EQUIPO_ACTUAL

                        # Actualizar CaseHistory — futuros análisis verán criterio validado por experto
                        caso_id = getattr(d["audit"], "caso_id", None)
                        if caso_id:
                            firma = f"{USUARIO_ACTUAL} ({EQUIPO_ACTUAL})"
                            case_history.update_validation(
                                case_id=caso_id,
                                expert_validated=True,
                                expert_comments=f"[{firma}] {com_final}",
                                final_alicuota=ali_final,
                            )

                    db.commit()

                    # Log de cada decisión individual
                    for d in decisiones:
                        accion_log = "VALIDACION_ACEPTADA" if d["accion"] == "✅ Acepto el criterio IA" else "VALIDACION_MODIFICADA"
                        r = d["resultado"]
                        log_actividad(db, accion_log,
                            usuario=USUARIO_ACTUAL, equipo=EQUIPO_ACTUAL,
                            cuit=getattr(d["audit"], "cuit", None),
                            periodo=getattr(d["audit"], "periodo", None),
                            jurisdiccion_id=juris_code,
                            auditoria_id=getattr(d["audit"], "id", None),
                            detalle=f"NAES: {r.naes} | Alíc. IA: {d['alicuota_ia']:.2f}% → "
                                    f"Validada: {(d['alicuota_ia'] if d['accion'] == '✅ Acepto el criterio IA' else d['nueva_alicuota']):.2f}% | "
                                    f"{d['comentario'][:150] if d['comentario'] else ''}")

                    st.success(f"✅ Validación guardada por **{USUARIO_ACTUAL}** — **{EQUIPO_ACTUAL}**. "
                               "Los criterios quedan registrados como precedentes experto.")
                    st.rerun()


def _render_jurisdiccion_detail(juris_code, audits, db):
    """Muestra todas las actividades de una jurisdicción agrupadas."""
    import re as _re
    from core.constants import JURISDICCIONES

    nombre = JURISDICCIONES.get(juris_code, f"Jurisdicción {juris_code}")

    # Recopilar todos los resultados de todos los registros de esta jurisdicción
    all_items = []
    for audit in sorted(audits, key=lambda a: a.id):
        resultados = db.query(ResultadoActividad).filter(ResultadoActividad.auditoria_id == audit.id).all()
        for r in resultados:
            all_items.append({"audit": audit, "resultado": r})

    estados = {a.estado for a in audits}
    color_ia = "#2e7d32" if "COMPLETADO" in estados else ("#c62828" if "ERROR" in estados else "#e65100")
    estado_label = "COMPLETADO" if "COMPLETADO" in estados else ("ERROR" if "ERROR" in estados else "PROCESANDO")

    # Badge de validación humana
    val_estados = {getattr(i["resultado"], "validacion_estado", "PENDIENTE") for i in all_items}
    if val_estados == {"ACEPTADO"}:
        val_badge = '<span style="background:#1565c0;color:#fff;font-size:0.72rem;font-weight:600;padding:3px 12px;border-radius:12px;">✅ VALIDADO</span>'
    elif "MODIFICADO" in val_estados and "PENDIENTE" not in val_estados:
        val_badge = '<span style="background:#6a1b9a;color:#fff;font-size:0.72rem;font-weight:600;padding:3px 12px;border-radius:12px;">⚠️ REVISADO</span>'
    elif "PENDIENTE" not in val_estados:
        val_badge = '<span style="background:#1565c0;color:#fff;font-size:0.72rem;font-weight:600;padding:3px 12px;border-radius:12px;">✅ VALIDADO</span>'
    else:
        val_badge = '<span style="background:#78909c;color:#fff;font-size:0.72rem;font-weight:600;padding:3px 12px;border-radius:12px;">⏳ Pendiente validación</span>'

    st.markdown(
        f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:1rem;">'
        f'<span style="font-size:1.1rem;font-weight:700;color:#001e40;">📋 {juris_code} · {nombre}</span>'
        f'<span style="background:{color_ia};color:#fff;font-size:0.72rem;font-weight:600;padding:3px 12px;border-radius:12px;">{estado_label}</span>'
        f'{val_badge}'
        f'<span style="color:#888;font-size:0.78rem;">{len(all_items)} actividad(es)</span>'
        f'</div>',
        unsafe_allow_html=True
    )

    if not all_items:
        st.warning("No hay actividades registradas para esta jurisdicción.")
        return

    # Tabla combinada de actividades
    st.markdown("##### 📋 Actividades Auditadas")

    def _delta_str(ant, det):
        if ant is None or ant == 0.0:
            return "—"
        delta = round(det - ant, 4)
        if abs(delta) < 0.001:
            return "= Sin variación"
        arrow = "▲" if delta > 0 else "▼"
        return f"{arrow} {delta:+.2f} pp"

    _nan = float("nan")
    df_res = pd.DataFrame([{
        "Actividad":             i["resultado"].actividad_desc or "—",
        "NAES":                  i["resultado"].naes or "—",
        "Alíc. Anterior (%)":    getattr(i["resultado"], "alicuota_anterior", None) or _nan,
        "Alíc. IA (%)":          i["resultado"].alicuota_ia or i["resultado"].alicuota_sugerida,
        "Alíc. Definitiva (%)":  (v if (v := getattr(i["resultado"], "alicuota_validada", None)) is not None else _nan),
        "Variación":             _delta_str(
                                    getattr(i["resultado"], "alicuota_anterior", None),
                                    i["resultado"].alicuota_ia or i["resultado"].alicuota_sugerida
                                 ),
        "Normativa":             i["resultado"].normativa_ref or "—",
    } for i in all_items])
    st.dataframe(
        df_res, use_container_width=True,
        column_config={
            "Actividad": st.column_config.TextColumn(
                "Actividad", width="large",
                help="Descripción de la actividad económica según el nomenclador NAES "
                     "(Nomenclador de Actividades Económicas del Sistema Federal de Recaudación) "
                     "tal como figura en la normativa provincial."
            ),
            "NAES": st.column_config.TextColumn(
                "NAES",
                help="Código numérico del Nomenclador de Actividades Económicas del Sistema "
                     "Federal de Recaudación (NAES), vigente desde 2018 en reemplazo del CUACM. "
                     "Identifica unívocamente la actividad económica a nivel nacional para la "
                     "liquidación de Ingresos Brutos bajo el Convenio Multilateral."
            ),
            "Alíc. Anterior (%)": st.column_config.NumberColumn(
                "Alíc. Anterior (%)", format="%.2f",
                help="Alícuota que el contribuyente venía aplicando en el período anterior, "
                     "declarada en el archivo de carga. Sirve como base de comparación para "
                     "detectar variaciones y posibles errores históricos."
            ),
            "Alíc. IA (%)": st.column_config.NumberColumn(
                "Alíc. IA (%)", format="%.2f",
                help="Tasa determinada por el Agente IA. Incorpora: alícuota base de la normativa, "
                     "reducción por tramo de volumen de ventas y análisis de la situación especial "
                     "del contribuyente. Es el dictamen inicial que el especialista debe revisar y confirmar."
            ),
            "Alíc. Definitiva (%)": st.column_config.NumberColumn(
                "Alíc. Definitiva (%)", format="%.2f",
                help="Alícuota confirmada por el especialista tras la validación. "
                     "Si el auditor aceptó el criterio IA, coincide con la Alíc. IA. "
                     "Si lo modificó, refleja su propio criterio técnico. "
                     "Aparece vacío (—) mientras la actividad no haya sido validada."
            ),
            "Variación": st.column_config.TextColumn(
                "Variación",
                help="Diferencia en puntos porcentuales (pp) entre la Alíc. IA y la "
                     "Alíc. Anterior. ▲ indica aumento, ▼ indica reducción. Una variación "
                     "significativa puede indicar un error previo o un cambio normativo."
            ),
            "Normativa": st.column_config.TextColumn(
                "Normativa", width="medium",
                help="Ley, decreto o resolución que sustenta la alícuota IA, con el artículo "
                     "específico recuperado por el motor RAG al momento del análisis. "
                     "El valor se actualiza con cada reprocesamiento: con la normativa CABA "
                     "indexada, las actividades de CABA mostrarán sus artículos propios "
                     "(Ley 6927) en lugar de los de BsAs."
            ),
        }
    )

    # Resúmenes IA — etiquetados por actividad(es) que cubre cada análisis
    resumenes = [a for a in audits if a.resumen_ia]
    if resumenes:
        with st.expander("🤖 Ver resúmenes IA"):
            for audit in resumenes:
                # Identificar actividades de este audit para el título
                acts_de_audit = [i["resultado"] for i in all_items if i["audit"].id == audit.id]
                if acts_de_audit:
                    acts_label = " · ".join(
                        f"NAES {r.naes}" + (f" – {r.actividad_desc[:35]}…" if r.actividad_desc and len(r.actividad_desc) > 35 else f" – {r.actividad_desc}" if r.actividad_desc else "")
                        for r in acts_de_audit[:4]
                    )
                    st.caption(f"**Análisis Técnico** — {acts_label}")
                resumen_limpio = _re.sub(r'#{1,4}\s*', '', audit.resumen_ia)
                resumen_limpio = _re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', resumen_limpio)
                resumen_limpio = resumen_limpio.replace('\n', '<br>')
                st.markdown(
                    f'<div style="background:#f0f4fa;border-left:4px solid #1a3a6b;border-radius:6px;'
                    f'padding:14px 18px;max-height:200px;overflow-y:auto;font-size:0.82rem;'
                    f'line-height:1.6;color:#222;">{resumen_limpio}</div>',
                    unsafe_allow_html=True
                )
                st.markdown("")

    # Justificaciones por actividad — título incluye NAES y descripción
    with st.expander("📄 Ver justificaciones IA por actividad"):
        for i in all_items:
            r = i["resultado"]
            naes_label = f"NAES {r.naes}" if r.naes else ""
            desc_label = r.actividad_desc or ""
            st.markdown(f"**Análisis Técnico — {desc_label}** {('(' + naes_label + ')') if naes_label else ''}")
            st.write(r.justificacion or "Sin justificación registrada.")
            st.divider()

    # Reportes descargables
    archivos = []
    for audit in audits:
        archivos.extend(db.query(ArchivoGenerado).filter(ArchivoGenerado.auditoria_id == audit.id).all())
    if archivos:
        st.markdown("##### 📥 Reportes Generados")
        for arch in archivos:
            try:
                with open(arch.ruta_archivo, "rb") as f:
                    st.download_button(
                        f"Descargar {arch.tipo} — {arch.nombre_archivo}",
                        f.read(), arch.nombre_archivo,
                        key=f"dl_{arch.id}"
                    )
            except FileNotFoundError:
                st.warning(f"Archivo no encontrado: {arch.nombre_archivo}")

    # ── Validación humana ────────────────────────────────────────────────────
    _render_validacion(juris_code, all_items, db)

    # Precedentes — casos similares en la base de conocimiento
    naes_codes = list({i["resultado"].naes for i in all_items if i["resultado"].naes and i["resultado"].naes != "000000"})
    if naes_codes:
        with st.expander("🔍 Precedentes — casos similares en otros clientes"):
            try:
                from memory.case_history import CaseHistory
                from core.constants import JURISDICCIONES
                case_history = CaseHistory()
                cuits_actuales = {a.cuit for a in audits}
                provincia_name = JURISDICCIONES.get(juris_code, str(juris_code))

                precedentes = []
                for naes in naes_codes:
                    casos = case_history.find_similar(
                        actividades_desc="",
                        provincia_id=provincia_name,
                        naes_code=naes,
                        max_results=10,
                    )
                    for c in casos:
                        if c["cuit"] not in cuits_actuales:
                            precedentes.append(c)

                # Deduplicar por caso ID
                seen = set()
                precedentes_uniq = []
                for c in precedentes:
                    if c["id"] not in seen:
                        seen.add(c["id"])
                        precedentes_uniq.append(c)

                if not precedentes_uniq:
                    st.info("No se encontraron precedentes de otros clientes para esta actividad y jurisdicción. "
                            "Este será el primer caso de referencia.")
                else:
                    st.caption(f"{len(precedentes_uniq)} precedente(s) encontrado(s) — criterios similares aplicados a otros contribuyentes.")
                    def _firma_caso(c):
                        if not c.get("expert_validated"):
                            return "🤖 Solo IA"
                        analista = c.get("analista") or "—"
                        # El campo analista tiene formato "[Usuario (Equipo)] comentario"
                        # o simplemente el nombre del analista original
                        if analista.startswith("[") and "]" in analista:
                            firma = analista[1:analista.index("]")]
                        else:
                            firma = analista
                        return f"✅ {firma}"

                    df_prec = pd.DataFrame([{
                        "ID Caso":       c["id"],
                        "CUIT":          c["cuit"],
                        "Período":       c.get("periodo", "—"),
                        "NAES":          c.get("naes_code", "—"),
                        "Actividad":     (c.get("actividades_desc") or "—")[:60],
                        "Alíc. (%)":     c.get("final_alicuota") or c.get("alicuota_determinada"),
                        "Normativa":     f"{c.get('norma_citada','—')} | {c.get('articulo_citado','—')}",
                        "Criterio":      _firma_caso(c),
                    } for c in precedentes_uniq])
                    st.dataframe(
                        df_prec, use_container_width=True,
                        column_config={
                            "ID Caso":   st.column_config.TextColumn("ID Caso", help="Identificador único del caso en la base de conocimiento."),
                            "CUIT":      st.column_config.TextColumn("CUIT", help="CUIT del contribuyente del caso precedente."),
                            "Período":   st.column_config.TextColumn("Período", help="Ejercicio fiscal del caso precedente."),
                            "NAES":      st.column_config.TextColumn("NAES", help="Código de actividad del caso precedente."),
                            "Actividad": st.column_config.TextColumn("Actividad", width="large", help="Descripción de la actividad analizada en el caso precedente."),
                            "Alíc. (%)": st.column_config.NumberColumn("Alíc. (%)", format="%.2f", help="Alícuota determinada en ese caso precedente. Útil para validar consistencia de criterio."),
                            "Normativa": st.column_config.TextColumn("Normativa", help="Norma y artículo citados en el caso precedente."),
                            "Criterio":  st.column_config.TextColumn("Criterio", help="Indica quién validó el criterio: el especialista y equipo que lo revisó, o si es solo dictamen IA sin validación humana."),
                        }
                    )
            except Exception as e:
                st.warning(f"No se pudo consultar la base de precedentes: {e}")

    # Acciones avanzadas
    if st.checkbox("⚙️ Acciones Avanzadas", key=f"adv_juris_{juris_code}"):
        if st.button("🗑️ Eliminar auditorías de esta jurisdicción", use_container_width=True, key=f"del_juris_{juris_code}"):
            for audit in audits:
                db.query(ArchivoGenerado).filter(ArchivoGenerado.auditoria_id == audit.id).delete()
                db.query(ResultadoActividad).filter(ResultadoActividad.auditoria_id == audit.id).delete()
                db.query(Auditoria).filter(Auditoria.id == audit.id).delete()
            db.commit()
            st.session_state.pop("hist_jurisdiccion", None)
            st.success("Auditorías eliminadas.")
            st.rerun()


def _render_todas_jurisdicciones(por_jurisdiccion, db):
    """Tabla completa con todas las jurisdicciones y sus alícuotas."""
    from core.constants import JURISDICCIONES

    st.markdown("### 📊 Análisis Completo — Todas las Jurisdicciones")

    rows = []
    for juris_code in sorted(por_jurisdiccion.keys()):
        nombre = JURISDICCIONES.get(juris_code, f"Jurisdicción {juris_code}")
        for audit in sorted(por_jurisdiccion[juris_code], key=lambda a: a.id):
            resultados = db.query(ResultadoActividad).filter(ResultadoActividad.auditoria_id == audit.id).all()
            for r in resultados:
                _v = getattr(r, "alicuota_validada", None)
                rows.append({
                    "Cod.":                  juris_code,
                    "Jurisdicción":          nombre,
                    "Actividad":             r.actividad_desc or "—",
                    "NAES":                  r.naes or "—",
                    "Alíc. IA (%)":          r.alicuota_ia or r.alicuota_sugerida,
                    "Alíc. Definitiva (%)":  float(_v) if _v is not None else float("nan"),
                    "Estado":                audit.estado or "—",
                    "Normativa":             r.normativa_ref or "—",
                })

    if not rows:
        st.warning("No hay actividades para mostrar.")
        return

    df = pd.DataFrame(rows)
    st.dataframe(
        df, use_container_width=True,
        column_config={
            "Cod.": st.column_config.NumberColumn(
                "Cod.",
                help="Código numérico de la jurisdicción provincial según el convenio multilateral "
                     "(901 = CABA, 902 = Buenos Aires, etc.)."
            ),
            "Jurisdicción": st.column_config.TextColumn(
                "Jurisdicción",
                help="Nombre de la provincia o jurisdicción fiscal auditada."
            ),
            "Actividad": st.column_config.TextColumn(
                "Actividad", width="large",
                help="Descripción de la actividad económica según el nomenclador NAES "
                     "(Nomenclador de Actividades Económicas del Sistema Federal de Recaudación) "
                     "tal como figura en la normativa provincial."
            ),
            "NAES": st.column_config.TextColumn(
                "NAES",
                help="Código numérico del Nomenclador de Actividades Económicas del Sistema "
                     "Federal de Recaudación (NAES), vigente desde 2018 en reemplazo del CUACM. "
                     "Identifica unívocamente la actividad económica a nivel nacional para la "
                     "liquidación de Ingresos Brutos bajo el Convenio Multilateral."
            ),
            "Alíc. IA (%)": st.column_config.NumberColumn(
                "Alíc. IA (%)", format="%.2f",
                help="Tasa determinada por el Agente IA para esta actividad. Incorpora la alícuota "
                     "base de la normativa, reducción por tramo de volumen y situación especial. "
                     "Es el dictamen inicial pendiente de validación por el especialista."
            ),
            "Alíc. Definitiva (%)": st.column_config.NumberColumn(
                "Alíc. Definitiva (%)", format="%.2f",
                help="Alícuota confirmada por el especialista. Si aceptó el criterio IA, coincide "
                     "con la Alíc. IA. Si lo modificó, refleja su propio criterio técnico. "
                     "Aparece vacío (—) mientras la actividad no haya sido validada."
            ),
            "Estado": st.column_config.TextColumn(
                "Estado",
                help="Estado del procesamiento: COMPLETADO (análisis exitoso), "
                     "ERROR (fallo durante el análisis), PROCESANDO (en curso)."
            ),
            "Normativa": st.column_config.TextColumn(
                "Normativa", width="medium",
                help="Ley, decreto o resolución que sustenta la alícuota IA, con el artículo "
                     "específico recuperado por el motor RAG al momento del análisis. "
                     "El valor se actualiza con cada reprocesamiento: con la normativa CABA "
                     "indexada, las actividades de CABA mostrarán sus artículos propios "
                     "(Ley 6927) en lugar de los de BsAs."
            ),
        }
    )
    st.caption(f"Total: {len(rows)} actividad(es) en {len(por_jurisdiccion)} jurisdicción(es) con datos.")


def view_historial():
    from core.constants import JURISDICCIONES
    from collections import defaultdict

    st.markdown('<h1>Historial de Auditorías</h1>', unsafe_allow_html=True)

    db = SessionLocal()
    auditorias = db.query(Auditoria).order_by(Auditoria.id.desc()).all()

    if not auditorias:
        st.info("No hay auditorías registradas aún.")
        db.close()
        return

    por_cuit = defaultdict(list)
    for a in auditorias:
        por_cuit[a.cuit].append(a)

    # ══════════════════════════════════════════════════════════════════════════
    # PASO 1 — Selector de Cliente
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("#### 👤 Paso 1 — Seleccione un cliente")
    st.caption("Puede escribir el CUIT para filtrar rápidamente.")

    cuits_ordenados = sorted(por_cuit.keys())
    cuit_options = {
        cuit: f"🏢  {cuit}   ·   {len(por_cuit[cuit])} registro(s)  ·  "
              f"Períodos: {', '.join(sorted({a.periodo for a in por_cuit[cuit]}, reverse=True))}"
        for cuit in cuits_ordenados
    }

    selected_cuit = st.selectbox(
        "Seleccione cliente (CUIT):",
        options=cuits_ordenados,
        format_func=lambda c: cuit_options[c],
        key="hist_cuit_select",
        label_visibility="collapsed",
    )

    # Resetear estado hijo cuando cambia el cliente
    if st.session_state.get("hist_cuit_prev") != selected_cuit:
        st.session_state.hist_cuit_prev = selected_cuit
        for k in ["hist_periodo_select", "hist_jurisdiccion", "hist_periodo_prev"]:
            st.session_state.pop(k, None)

    audits_cliente = [a for a in auditorias if a.cuit == selected_cuit]
    periodos_cliente = sorted({a.periodo for a in audits_cliente}, reverse=True)
    juris_cliente = len({a.provincia_id for a in audits_cliente if a.provincia_id})

    st.markdown(
        f'<div style="background:#f0f4fa;border-radius:8px;padding:10px 16px;margin:8px 0 16px 0;display:flex;gap:32px;align-items:center;">'
        f'<div><span style="font-size:0.75rem;color:#666;">CUIT</span><br><span style="font-weight:700;color:#001e40;font-size:1rem;">{selected_cuit}</span></div>'
        f'<div><span style="font-size:0.75rem;color:#666;">Períodos</span><br><span style="font-weight:600;color:#001e40;">{" · ".join(periodos_cliente)}</span></div>'
        f'<div><span style="font-size:0.75rem;color:#666;">Jurisdicciones</span><br><span style="font-weight:600;color:#001e40;">{juris_cliente}</span></div>'
        f'<div><span style="font-size:0.75rem;color:#666;">Total registros</span><br><span style="font-weight:600;color:#001e40;">{len(audits_cliente)}</span></div>'
        f'</div>',
        unsafe_allow_html=True
    )
    st.divider()

    # ══════════════════════════════════════════════════════════════════════════
    # PASO 2 — Selector de Período
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("#### 📅 Paso 2 — Seleccione el período")

    por_periodo = defaultdict(list)
    for a in audits_cliente:
        por_periodo[a.periodo].append(a)

    periodo_options = {}
    for p in periodos_cliente:
        n = len(por_periodo[p])
        juris_count = len({a.provincia_id for a in por_periodo[p] if a.provincia_id})
        periodo_options[p] = f"📅  Período {p}   ·   {n} registro(s)   ·   {juris_count} jurisdicción(es)"

    selected_periodo = st.selectbox(
        "Seleccione período:",
        options=periodos_cliente,
        format_func=lambda p: periodo_options[p],
        key="hist_periodo_select",
        label_visibility="collapsed",
    )

    # Resetear jurisdicción cuando cambia el período
    if st.session_state.get("hist_periodo_prev") != selected_periodo:
        st.session_state.hist_periodo_prev = selected_periodo
        st.session_state.pop("hist_jurisdiccion", None)

    # Agrupar auditorías del período por jurisdicción
    audits_periodo = por_periodo[selected_periodo]
    por_jurisdiccion = defaultdict(list)
    for a in audits_periodo:
        if a.provincia_id:
            por_jurisdiccion[a.provincia_id].append(a)
    active_codes = set(por_jurisdiccion.keys())

    st.divider()

    # ══════════════════════════════════════════════════════════════════════════
    # PASO 3 — Panel de Jurisdicciones (Opción C: 5×5 + TODAS)
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("#### 🗺️ Paso 3 — Seleccione una jurisdicción")

    selected_juris = st.session_state.get("hist_jurisdiccion", None)

    if selected_juris and selected_juris != "TODAS":
        nombre_sel = JURISDICCIONES.get(selected_juris, str(selected_juris))
        st.caption(f"▶ Mostrando: **{selected_juris} · {nombre_sel}**  —  haga clic en otra jurisdicción para cambiar.")
    elif selected_juris == "TODAS":
        st.caption("▶ Mostrando análisis completo de todas las jurisdicciones.")

    # 24 jurisdicciones + TODAS = 25 ítems → 5 filas × 5 columnas
    COLS = 5
    all_codes = list(JURISDICCIONES.keys())   # 901–924
    items = all_codes + ["TODAS"]             # 25 ítems

    for row_start in range(0, 25, COLS):
        row_items = items[row_start:row_start + COLS]
        cols = st.columns(COLS)
        for col_idx, item in enumerate(row_items):
            with cols[col_idx]:
                if item == "TODAS":
                    is_sel = (selected_juris == "TODAS")
                    lbl = "▶ TODAS" if is_sel else "🌐 TODAS"
                    if st.button(lbl, key="juris_TODAS", use_container_width=True, type="primary"):
                        st.session_state.hist_jurisdiccion = "TODAS"
                        st.rerun()
                else:
                    code = item
                    has_data = code in active_codes
                    is_sel = (selected_juris == code)
                    n = len(por_jurisdiccion.get(code, []))
                    if is_sel:
                        lbl = f"▶ {code}"
                    elif has_data:
                        lbl = f"✅ {code}"
                    else:
                        lbl = str(code)
                    tip = f"{JURISDICCIONES[code]}" + (f" — {n} reg." if has_data else " — sin datos")
                    if has_data:
                        if st.button(lbl, key=f"juris_{code}", use_container_width=True, help=tip):
                            st.session_state.hist_jurisdiccion = code
                            st.rerun()
                    else:
                        st.button(lbl, key=f"juris_{code}", use_container_width=True,
                                  disabled=True, help=tip)

    st.divider()

    # ══════════════════════════════════════════════════════════════════════════
    # PASO 4 — Detalle
    # ══════════════════════════════════════════════════════════════════════════
    if selected_juris is None:
        st.info("👆 Seleccione una jurisdicción del panel (✅ = tiene datos) o use **🌐 TODAS** para ver el análisis completo.")
    elif selected_juris == "TODAS":
        log_actividad(db, "HISTORIAL_CONSULTADO",
            detalle=f"Vista TODAS las jurisdicciones | Período: {selected_periodo} | CUIT: {selected_cuit}")
        _render_todas_jurisdicciones(por_jurisdiccion, db)
    else:
        juris_audits = por_jurisdiccion.get(selected_juris, [])
        if juris_audits:
            log_actividad(db, "HISTORIAL_CONSULTADO",
                cuit=selected_cuit, periodo=selected_periodo, jurisdiccion_id=selected_juris,
                detalle=f"Jurisdicción {selected_juris} · {selected_cuit} · {selected_periodo}")
            _render_jurisdiccion_detail(selected_juris, juris_audits, db)
        else:
            st.warning("No hay datos para esta jurisdicción en el período seleccionado.")

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

def view_actividad():
    st.markdown('<h1 style="margin-top:0;">Actividad & Métricas</h1>', unsafe_allow_html=True)
    st.markdown("<p style='color:#666;margin-bottom:1.5rem'>Registro de acciones por usuario y equipo.</p>", unsafe_allow_html=True)

    db = SessionLocal()
    logs = db.query(ActivityLog).order_by(ActivityLog.timestamp.desc()).all()
    db.close()

    if not logs:
        st.info("Aún no hay actividad registrada.")
        return

    df_log = pd.DataFrame([{
        "timestamp":    l.timestamp,
        "usuario":      l.usuario or "—",
        "equipo":       l.equipo or "—",
        "accion":       l.accion or "—",
        "cuit":         l.cuit or "—",
        "periodo":      l.periodo or "—",
        "jurisdiccion": l.jurisdiccion_id or "—",
        "detalle":      l.detalle or "—",
    } for l in logs])

    # ── Métricas generales ────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    total_consultas   = df_log[df_log["accion"].isin(["CONSULTA_INICIADA","CONSULTA_COMPLETADA"])]["accion"].value_counts().get("CONSULTA_COMPLETADA", 0)
    total_validadas   = df_log[df_log["accion"] == "VALIDACION_ACEPTADA"].shape[0]
    total_modificadas = df_log[df_log["accion"] == "VALIDACION_MODIFICADA"].shape[0]
    usuarios_activos  = df_log["usuario"].nunique()

    col1.metric("Consultas completadas", total_consultas)
    col2.metric("Validaciones aceptadas", total_validadas)
    col3.metric("Criterios modificados", total_modificadas, help="Veces que un especialista cambió el criterio IA")
    col4.metric("Usuarios activos", usuarios_activos)

    st.divider()

    # ── Actividad por acción ──────────────────────────────────────────────────
    col_graf1, col_graf2 = st.columns(2)

    with col_graf1:
        st.markdown("##### Acciones por tipo")
        accion_labels = {
            "CONSULTA_INICIADA":    "Consultas iniciadas",
            "CONSULTA_COMPLETADA":  "Consultas completadas",
            "CONSULTA_ERROR":       "Errores",
            "VALIDACION_ACEPTADA":  "Validaciones aceptadas",
            "VALIDACION_MODIFICADA":"Criterios modificados",
            "HISTORIAL_CONSULTADO": "Consultas de historial",
        }
        conteo = df_log["accion"].value_counts().rename(index=accion_labels)
        st.bar_chart(conteo)

    with col_graf2:
        st.markdown("##### Acciones por usuario")
        por_usuario = df_log.groupby(["usuario","equipo"])["accion"].count().reset_index()
        por_usuario.columns = ["Usuario", "Equipo", "Total acciones"]
        st.dataframe(por_usuario, use_container_width=True, hide_index=True,
            column_config={
                "Usuario": st.column_config.TextColumn("Usuario", help="Nombre del especialista que realizó la acción."),
                "Equipo":  st.column_config.TextColumn("Equipo", help="Estudio o equipo al que pertenece el usuario."),
                "Total acciones": st.column_config.NumberColumn("Total acciones"),
            })

    st.caption(f"Total en el sistema: {len(df_log)} acción(es) registrada(s).")


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

    # ── Actividad & Métricas ─────────────────────────────────────────────────
    st.divider()
    st.markdown("### 📈 Actividad & Métricas")

    db_log = SessionLocal()
    logs = db_log.query(ActivityLog).order_by(ActivityLog.timestamp.desc()).all()
    db_log.close()

    if not logs:
        st.info("Aún no hay actividad registrada.")
    else:
        accion_labels = {
            "CONSULTA_INICIADA":    "Consultas iniciadas",
            "CONSULTA_COMPLETADA":  "Consultas completadas",
            "CONSULTA_ERROR":       "Errores",
            "VALIDACION_ACEPTADA":  "Validaciones aceptadas",
            "VALIDACION_MODIFICADA":"Criterios modificados",
            "HISTORIAL_CONSULTADO": "Consultas de historial",
        }
        df_log = pd.DataFrame([{
            "timestamp":    l.timestamp,
            "usuario":      l.usuario or "—",
            "equipo":       l.equipo or "—",
            "accion":       l.accion or "—",
            "cuit":         l.cuit or "—",
            "periodo":      l.periodo or "—",
            "jurisdiccion": l.jurisdiccion_id or "—",
            "detalle":      l.detalle or "—",
        } for l in logs])

        # Métricas
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Consultas", df_log[df_log["accion"] == "CONSULTA_COMPLETADA"].shape[0])
        col2.metric("Validaciones aceptadas", df_log[df_log["accion"] == "VALIDACION_ACEPTADA"].shape[0])
        col3.metric("Criterios modificados",  df_log[df_log["accion"] == "VALIDACION_MODIFICADA"].shape[0])
        col4.metric("Usuarios activos", df_log["usuario"].nunique())

        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.markdown("**Acciones por tipo**")
            st.bar_chart(df_log["accion"].value_counts().rename(index=accion_labels))
        with col_g2:
            st.markdown("**Acciones por usuario / equipo**")
            por_u = df_log.groupby(["usuario","equipo"])["accion"].count().reset_index()
            por_u.columns = ["Usuario","Equipo","Total"]
            st.dataframe(por_u, use_container_width=True, hide_index=True)

        # Log filtrable
        st.markdown("**Log de actividad**")
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            fu = st.selectbox("Usuario:", ["Todos"] + sorted(df_log["usuario"].unique().tolist()), key="cfg_log_u")
        with col_f2:
            fe = st.selectbox("Equipo:",  ["Todos"] + sorted(df_log["equipo"].unique().tolist()),  key="cfg_log_e")
        with col_f3:
            fa = st.selectbox("Acción:",  ["Todas"]  + sorted(df_log["accion"].unique().tolist()),
                format_func=lambda x: accion_labels.get(x, x) if x != "Todas" else "Todas", key="cfg_log_a")

        df_f = df_log.copy()
        if fu != "Todos": df_f = df_f[df_f["usuario"] == fu]
        if fe != "Todos": df_f = df_f[df_f["equipo"]  == fe]
        if fa != "Todas": df_f = df_f[df_f["accion"]  == fa]

        df_f = df_f.copy()
        df_f["timestamp"] = pd.to_datetime(df_f["timestamp"]).dt.strftime("%d/%m/%Y %H:%M")
        df_f["accion"] = df_f["accion"].map(lambda x: accion_labels.get(x, x))
        df_f = df_f.rename(columns={
            "timestamp":"Fecha/Hora","usuario":"Usuario","equipo":"Equipo",
            "accion":"Acción","cuit":"CUIT","periodo":"Período",
            "jurisdiccion":"Jurisdicción","detalle":"Detalle"
        })
        st.dataframe(df_f, use_container_width=True, hide_index=True,
            column_config={"Detalle": st.column_config.TextColumn("Detalle", width="large")})
        st.caption(f"{len(df_f)} registro(s) mostrado(s) — {len(df_log)} total.")


# --- RENDER ---
draw_header()

with st.sidebar:
    _logo_b64 = get_base64_logo("logo_ll_digital")
    if _logo_b64:
        st.markdown(
            f'<div style="padding:8px 0 12px 0;"><img src="{_logo_b64}" style="width:80%;max-width:160px;object-fit:contain;"></div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown("## 🔍 IIBB Tax Audit LL")

    nav_items = [
        ("📤 Carga de Datos",          "Carga de Datos"),
        ("📊 Historial de Auditorías", "Historial de Auditorías"),
        ("📈 Actividad & Métricas",    "Actividad & Métricas"),
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
elif selected_menu == "Actividad & Métricas":
    view_actividad()
elif selected_menu == "Guía de Uso":
    view_guia()
elif selected_menu == "Configuración":
    view_configuracion()
