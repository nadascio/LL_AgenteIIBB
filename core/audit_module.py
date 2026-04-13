"""
core/audit_module.py — Módulo de Auditoría Interanual

Compara alícuotas entre períodos y genera un análisis de la variación,
buscando en la normativa la explicación normativa del cambio.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from core.rag_engine import RAGEngine
from config import agent_cfg
from rich.console import Console

console = Console()


class VariacionTipo(str, Enum):
    IGUAL = "Igual"
    INCREMENTO = "Incremento"
    DESCENSO = "Descenso"


@dataclass
class AuditoriaResult:
    """Resultado del análisis de auditoría interanual."""
    alicuota_anterior: float
    alicuota_actual: float
    delta: float
    variacion_tipo: VariacionTipo
    explicacion_normativa: str
    contexto_rag: str  # Fragmentos normativos que explican el cambio
    confianza_explicacion: str  # "Alta" | "Media" | "Baja"


class AuditModule:
    """
    Módulo de auditoría interanual.
    
    Compara la alícuota del período anterior con la actual y busca
    en la normativa los cambios normativos que justifican la variación.
    """

    UMBRAL_DIFERENCIA = 0.01  # Diferencias menores a este valor se consideran "Igual"

    def __init__(self, rag_engine: RAGEngine):
        self.rag = rag_engine

    def analizar(
        self,
        alicuota_anterior: float,
        alicuota_actual: float,
        actividades_desc: str,
        naes_code: str | None = None,
    ) -> AuditoriaResult:
        """
        Ejecuta el análisis de auditoría interanual.
        
        Args:
            alicuota_anterior: Alícuota del período anterior (%).
            alicuota_actual: Alícuota determinada para el período actual (%).
            actividades_desc: Descripción de la actividad para búsqueda contextual.
            naes_code: Código NAES opcional para mejorar la búsqueda.
        
        Returns:
            AuditoriaResult con el análisis completo.
        """
        delta = round(alicuota_actual - alicuota_anterior, 4)
        variacion = self._determinar_variacion(delta)

        if agent_cfg.verbose_chain:
            console.print(
                f"[dim]🔍 Auditoría: {alicuota_anterior}% → {alicuota_actual}% "
                f"| Delta: {delta:+.4f}% ({variacion.value})[/dim]"
            )

        if variacion == VariacionTipo.IGUAL:
            return AuditoriaResult(
                alicuota_anterior=alicuota_anterior,
                alicuota_actual=alicuota_actual,
                delta=delta,
                variacion_tipo=variacion,
                explicacion_normativa="La alícuota se mantiene sin modificaciones respecto al período anterior.",
                contexto_rag="",
                confianza_explicacion="Alta",
            )

        # Hay variación: buscar explicación normativa
        contexto = self._buscar_explicacion_normativa(
            alicuota_anterior, alicuota_actual, delta, actividades_desc, naes_code
        )

        explicacion = self._generar_explicacion_preliminar(
            delta, variacion, alicuota_anterior, alicuota_actual
        )

        return AuditoriaResult(
            alicuota_anterior=alicuota_anterior,
            alicuota_actual=alicuota_actual,
            delta=delta,
            variacion_tipo=variacion,
            explicacion_normativa=explicacion,
            contexto_rag=contexto,
            confianza_explicacion="Media",
        )

    def _determinar_variacion(self, delta: float) -> VariacionTipo:
        if abs(delta) <= self.UMBRAL_DIFERENCIA:
            return VariacionTipo.IGUAL
        return VariacionTipo.INCREMENTO if delta > 0 else VariacionTipo.DESCENSO

    def _buscar_explicacion_normativa(
        self,
        alicuota_ant: float,
        alicuota_act: float,
        delta: float,
        actividades_desc: str,
        naes_code: str | None,
    ) -> str:
        """
        Realiza búsquedas específicas en la normativa para encontrar
        la causa del cambio (nueva ley, cambio de escala, pérdida de beneficio, etc.).
        """
        queries = []

        # Query 1: Cambio de escala de volumen
        queries.append("cambio de escala volumen ventas categoría contribuyente modificador alícuota")

        # Query 2: Modificaciones a la ley impositiva
        if delta > 0:
            queries.append(f"incremento alícuota {actividades_desc} ley impositiva modificación")
        else:
            queries.append(f"reducción alícuota {actividades_desc} beneficio exención")

        # Query 3: Actividad específica
        naes_str = f"NAES {naes_code}" if naes_code else actividades_desc
        queries.append(f"variación alícuota {naes_str}")

        # Ejecutar búsquedas y consolidar resultados únicos
        all_chunks = {}
        for query in queries:
            chunks = self.rag.search(query, top_k=3)
            for chunk in chunks:
                chunk_id = chunk["metadata"].get("naes") or chunk["metadata"].get("categoria") or chunk["text"][:50]
                if chunk_id not in all_chunks or chunk["relevance_score"] > all_chunks[chunk_id]["relevance_score"]:
                    all_chunks[chunk_id] = chunk

        if not all_chunks:
            return "No se encontraron fragmentos normativos que expliquen la variación."

        lines = ["Fragmentos normativos relevantes para la variación encontrada:\n"]
        for i, chunk in enumerate(list(all_chunks.values())[:5], 1):
            meta = chunk["metadata"]
            lines.append(
                f"[{i}] {chunk['text']}\n"
                f"    → Fuente: {meta.get('norma_ref', 'N/A')} | {meta.get('articulo', 'N/A')}"
            )

        return "\n\n".join(lines)

    def _generar_explicacion_preliminar(
        self,
        delta: float,
        variacion: VariacionTipo,
        alicuota_ant: float,
        alicuota_act: float,
    ) -> str:
        """
        Genera una explicación preliminar estructurada (será completada por el LLM).
        """
        accion = "aumentó" if variacion == VariacionTipo.INCREMENTO else "disminuyó"
        return (
            f"La alícuota {accion} de {alicuota_ant}% a {alicuota_act}% "
            f"(variación de {delta:+.2f} puntos porcentuales). "
            f"Las causas más probables son: cambio en la escala de volumen de facturación, "
            f"modificación en la Ley Impositiva Anual, o pérdida/adquisición de un beneficio especial. "
            f"Ver contexto normativo para el fundamento exacto."
        )
