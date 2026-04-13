"""
core/agent.py — Orquestador principal del Agente IIBB (Versión Pydantic Estandarizada)

Implementa la lógica de auditoría usando validación estricta de esquemas.
"""

from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field
import re

from rich.console import Console
from config import agent_cfg
from core.rag_engine import RAGEngine
from core.tax_calculator import TaxCalculator, AlicuotaResult
from core.audit_module import AuditModule, AuditoriaResult
from memory.case_history import CaseHistory
from prompts.system_prompt import SYSTEM_PROMPT, build_analysis_prompt
from output.formatter import format_resultado
import logging

# Configuración de Logging Detallado
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
log_file = "agente_debug.log"
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setFormatter(log_formatter)

logger = logging.getLogger("AgenteIIBB")
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(file_handler)

console = Console()

class ActividadInput(BaseModel):
    """Sub-modelo estandarizado para una actividad económica."""
    desc: str = Field(..., min_length=3)        # Descripción NAES/ARCA (normativa)
    desc_real: Optional[str] = None             # Descripción real del contribuyente
    naes: Optional[str] = None

class AgentInput(BaseModel):
    """Schema de input principal con validación de datos sensibles."""
    cuit: str = Field(..., pattern=r"^\d{2}-\d{8}-\d{1}$")
    periodo: str = Field(..., description="Ejercicio fiscal analizado (ej: 2026)")
    volumen_ventas_anual: float = Field(..., gt=0)
    actividades: List[ActividadInput] = Field(..., min_length=1)
    provincia_id: str
    alicuota_periodo_anterior: Optional[float] = None
    situacion_especial: Optional[str] = Field(None, description="Situación o contexto especial del cliente (texto libre)")
    analista: Optional[str] = None

class AgentOutput(BaseModel):
    """Output consolidado del análisis multiactividad."""
    input: AgentInput
    resultados_por_actividad: List[AlicuotaResult]
    auditoria: Optional[AuditoriaResult] = None
    justificacion_llm: str
    resumen_ejecutivo: str = Field(..., description="Resumen de un párrafo para el Excel")
    caso_id: str
    output_texto: str

class IIBBAgent:
    """
    Agente principal de Ingresos Brutos.
    Orquesta la auditoría de múltiples actividades simultáneas.
    """

    def __init__(self):
        self.rag = RAGEngine(provincia=agent_cfg.provincia_activa)
        self.calculator = TaxCalculator(
            provincia=agent_cfg.provincia_activa,
            use_fixtures=agent_cfg.use_fixtures
        )
        self.history = CaseHistory()
        self._llm = None
        self._initialized = False

    def _build_llm(self):
        """Factory de LLM segun el backend configurado en .env."""
        from config import llm_cfg as _cfg
        backend = _cfg.backend.lower()
        console.print(f"[bold cyan]LLM Backend: {backend.upper()} | Modelo: {getattr(_cfg, backend + '_model', '?')}[/bold cyan]")
        
        if backend == "gemini":
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=_cfg.gemini_model,
                google_api_key=_cfg.gemini_api_key,
                temperature=0.2
            )
        elif backend == "ollama":
            from langchain_community.chat_models import ChatOllama
            return ChatOllama(
                model=_cfg.ollama_model,
                base_url=_cfg.ollama_base_url,
                temperature=0.2
            )
        elif backend == "openai":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=_cfg.openai_model,
                api_key=_cfg.openai_api_key,
                temperature=0.2
            )
        elif backend == "anthropic":
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=_cfg.anthropic_model,
                anthropic_api_key=_cfg.anthropic_api_key,
                temperature=0.2
            )
        else:
            raise ValueError(f"Backend de LLM desconocido: '{backend}'. Usa 'gemini', 'ollama', 'openai' o 'anthropic'.")

    def initialize(self, force_reindex: bool = False) -> None:
        if self._initialized:
            return
        self.rag.initialize(force_reindex=force_reindex)
        self._llm = self._build_llm()
        self._initialized = True

    def reset_llm(self) -> None:
        """Reinicia el LLM para que tome la nueva config del .env. Util tras cambiar backend desde la UI."""
        from config import llm_cfg as _cfg
        _cfg.reload()
        self._llm = self._build_llm()

    def analizar(self, inputs: AgentInput) -> AgentOutput:
        """
        Realiza el análisis fiscal completo para múltiples actividades.
        """
        if not self._initialized:
            self.initialize()

        from config import llm_cfg as _cfg
        backend = _cfg.backend.lower()
        model_name = getattr(_cfg, f"{backend}_model", "desconocido")

        resultados_calc = []
        contextos_legales = []
        
        # PASO 1: Procesar cada actividad individualmente
        for i, act in enumerate(inputs.actividades):
            console.print(f"[bold blue]PASO {i+1}: Analizando '{act.desc[:30]}...'[/bold blue]")
            
            # Recuperar normativa vía RAG — combina NAES + descripción ARCA + descripción real
            rag_parts = []
            if act.naes:
                rag_parts.append(f"NAES {act.naes}")
            if act.desc:
                rag_parts.append(act.desc)
            if act.desc_real and act.desc_real != act.desc:
                rag_parts.append(act.desc_real)
            rag_query = " ".join(rag_parts) if rag_parts else "alicuota actividad"
            contexto = self.rag.search_as_context(rag_query)
            contextos_legales.append(contexto)
            
            # Calcular alícuota técnica (Validador estructural)
            res_calc = self.calculator.calcular(
                actividades_desc=act.desc,
                volumen_ventas_anual=inputs.volumen_ventas_anual,
                naes_code=act.naes,
                situacion_especial=inputs.situacion_especial
            )
            resultados_calc.append(res_calc)

        # PASO 2: Recuperar historial similar para debate
        casos_similares = self.history.find_similar(
            actividades_desc=inputs.actividades[0].desc,
            provincia_id=inputs.provincia_id,
            naes_code=inputs.actividades[0].naes
        )
        context_historial = self.history.format_as_context(casos_similares)

        # PASO 3: Construcción de Prompt Consolidado
        full_normativa = "\n\n".join(contextos_legales)
        primer_res = resultados_calc[0] if resultados_calc else None
        # Consolidar warnings del calculador para avisarle al LLM
        calc_warnings = []
        for res in resultados_calc:
            calc_warnings.extend(res.warnings)
        # Construir lista estructurada de actividades para el prompt
        actividades_prompt = []
        for i, act in enumerate(inputs.actividades, 1):
            actividades_prompt.append({
                "numero": i,
                "naes": act.naes or "A determinar",
                "desc_naes": act.desc,
                "desc_real": act.desc_real or act.desc,
            })

        prompt = build_analysis_prompt(
            cuit=inputs.cuit,
            actividades=actividades_prompt,
            volumen_ventas_anual=inputs.volumen_ventas_anual,
            provincia_id=inputs.provincia_id,
            alicuota_periodo_anterior=inputs.alicuota_periodo_anterior,
            situacion_especial=inputs.situacion_especial,
            context_normativa=full_normativa,
            context_historial=context_historial,
            tramo_info=primer_res.categoria_volumen if primer_res else "",
            alicuota_tecnica=primer_res.alicuota_final if primer_res else None,
            calc_warnings=calc_warnings,
        )

        # PASO 4: Invocación al LLM (con retry automático para rate limits)
        try:
            import time as _time
            _max_retries = 3
            _response = None
            for _attempt in range(_max_retries):
                try:
                    logger.info(f"--- NUEVA CONSULTA LLM ({backend.upper()}) ---")
                    logger.info(f"MODELO: {getattr(_cfg, backend + '_model', '?')}")
                    logger.info(f"PROMPT ENVIADO:\n{prompt}\n")

                    _response = self._llm.invoke([
                        ("system", SYSTEM_PROMPT),
                        ("human", prompt)
                    ])
                    
                    logger.info(f"RESPUESTA RECIBIDA:\n{_response.content}\n")
                    logger.info("------------------------------------------")
                    break  # Éxito — salir del loop
                except Exception as _retry_err:
                    _err_str = str(_retry_err).lower()
                    if ("429" in _err_str or "quota" in _err_str or "resource_exhausted" in _err_str) and _attempt < _max_retries - 1:
                        _wait = 30 * (_attempt + 1)
                        console.print(f"[yellow]⏳ Rate limit detectado. Reintentando en {_wait}s (intento {_attempt+2}/{_max_retries})...[/yellow]")
                        _time.sleep(_wait)
                    else:
                        raise  # Propagar si no es 429 o si ya agotamos reintentos
            if _response is None:
                raise Exception("No se pudo obtener respuesta del modelo tras los reintentos.")
            response = _response
            full_content = response.content
            # Asegurar que sea string
            if isinstance(full_content, list):
                full_content = "\n".join([str(p.get("text", p) if isinstance(p, dict) else p) for p in full_content])
            
            # Extracción de resumen y dictamen
            resumen_pattern = r"\[RESUMEN EJECUTIVO PARA EXCEL:(.*?)\]"
            match = re.search(resumen_pattern, full_content, re.DOTALL)
            
            if match:
                resumen = match.group(1).strip()
                # Quitamos la etiqueta de resumen para la justificación larga
                justificacion = full_content.replace(match.group(0), "").strip()
            else:
                # El LLM no usó el tag — usamos el contenido completo como resumen
                resumen = full_content.strip()
                justificacion = full_content

            # Extracción del dictamen numérico IA para cada actividad
            ia_rates_raw = re.findall(r"\[ALICUOTA_IA:\s*(.*?)\]", full_content)
            for idx, rate_raw in enumerate(ia_rates_raw):
                if idx < len(resultados_calc):
                    try:
                        clean_rate = re.sub(r"[^\d\.,]", "", rate_raw)
                        rate_normalizado = clean_rate.replace(",", ".")
                        if rate_normalizado:
                            resultados_calc[idx].alicuota_ia = float(rate_normalizado)
                    except: pass

            # Fallback: si el LLM no devolvió el tag [ALICUOTA_IA], usar la alícuota técnica calculada
            for res in resultados_calc:
                if res.alicuota_ia == 0.0 and res.alicuota_final > 0.0:
                    res.alicuota_ia = res.alicuota_final

            # Extracción de justificaciones individuales por actividad
            for i in range(len(resultados_calc)):
                just_act_pattern = rf"\[JUSTIFICACION_ACT_{i+1}:\s*(.*?)\]"
                match_just = re.search(just_act_pattern, full_content, re.DOTALL)
                if match_just:
                    resultados_calc[i].justificacion = match_just.group(1).strip()
                elif i == 0 and len(resultados_calc) == 1:
                    # Fallback si solo hay una actividad y no puso la etiqueta numerada
                    resultados_calc[i].justificacion = justificacion
            
            # Limpiamos las etiquetas internas de IA de la justificación final para que no sea repetitivo
            justificacion = re.sub(r"\[ALICUOTA_IA:.*?\]", "", justificacion).strip()

        except Exception as e:
            import traceback
            error_msg = traceback.format_exc()
            console.print(f"[bold red]ERROR EN EL AGENTE:[/bold red]\n{error_msg}")
            logger.error(f"ERROR EN EL AGENTE: {str(e)}\n{error_msg}")
            
            # Clasificar el error para dar un mensaje claro e informativo
            err_str = str(e).lower()
            from config import llm_cfg as _cfg
            backend = _cfg.backend.lower()
            model_name = getattr(_cfg, f"{backend}_model", "desconocido")
            
            if "404" in err_str or "not_found" in err_str:
                tipo = "❌ Modelo de IA no encontrado"
                detalle = f"El modelo '{model_name}' no existe o no está disponible en el backend '{backend.upper()}'. Revisá tu configuración en la pestaña ⚙️ Configuración."
            elif "403" in err_str or "permission" in err_str or "api_key_invalid" in err_str:
                tipo = "🔑 Error de Autenticación"
                detalle = f"La API Key configurada para {backend.upper()} no tiene permisos o es inválida."
            elif "429" in err_str or "quota" in err_str or "resource_exhausted" in err_str:
                tipo = "⚠️ Límite de cuota excedido"
                detalle = f"Se agotó la cuota gratuita de {backend.upper()} para el modelo {model_name}. Esperá unos minutos o cambiá a Ollama (Local)."
            elif "timeout" in err_str or "deadline" in err_str:
                tipo = "⏱️ Tiempo de espera agotado"
                detalle = f"El backend {backend.upper()} tardó demasiado en responder. Si usás Ollama, asegurate de tener buena conexión o RAM disponible."
            else:
                tipo = "⚠️ Error en el Motor de IA"
                detalle = str(e)
            
            error_final_msg = f"{tipo}: {detalle}"
            # Lanzamos la excepción para que el Processor la capture y marque el estado ERROR en la DB.
            raise Exception(error_final_msg)

        # PASO 5: Auditoría Interanual
        auditoria_res = None
        if inputs.alicuota_periodo_anterior is not None and resultados_calc:
            auditor = AuditModule(rag_engine=self.rag)
            auditoria_res = auditor.analizar(
                alicuota_actual=resultados_calc[0].alicuota_final,
                alicuota_anterior=inputs.alicuota_periodo_anterior,
                actividades_desc="; ".join([a.desc for a in inputs.actividades]),
                naes_code=inputs.actividades[0].naes
            )

        # PASO 6: Registro en el Historial
        primer_resultado = resultados_calc[0] if resultados_calc else AlicuotaResult()
        caso_id = self.history.register_case(
            cuit=inputs.cuit,
            provincia_id=inputs.provincia_id,
            actividades_desc="; ".join([a.desc for a in inputs.actividades]),
            volumen_ventas_anual=inputs.volumen_ventas_anual,
            alicuota_determinada=primer_resultado.alicuota_final,
            norma_citada=primer_resultado.norma_ref_actividad,
            articulo_citado=primer_resultado.articulo_actividad,
            naes_code=inputs.actividades[0].naes,
            situacion_especial=inputs.situacion_especial,
            analista=inputs.analista,
            razonamiento_resumen=resumen[:500]
        )

        output_txt = format_resultado(
            cuit=inputs.cuit,
            provincia_id=inputs.provincia_id,
            actividades_desc="; ".join([a.desc for a in inputs.actividades]),
            volumen_ventas_anual=inputs.volumen_ventas_anual,
            resultados_calc=resultados_calc,
            justificacion_llm=justificacion,
            auditoria=auditoria_res,
            caso_id_registrado=caso_id
        )

        return AgentOutput(
            input=inputs,
            resultados_por_actividad=resultados_calc,
            auditoria=auditoria_res,
            justificacion_llm=justificacion,
            resumen_ejecutivo=resumen,
            caso_id=caso_id,
            output_texto=output_txt
        )

