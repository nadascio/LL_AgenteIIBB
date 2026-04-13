"""
core/tax_calculator.py — Lógica de cálculo de alícuotas

Aplica el razonamiento multi-etapa sobre los datos de la normativa:
1. Alícuota base por actividad NAES / descripción
2. Modificador por escala de volumen
3. Modificadores por condiciones especiales (tags)

Retorna un objeto de cálculo detallado que el agente usa como contexto.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field

from normativas.bsas.loader import NormativaLoader


@dataclass
class AlicuotaResult:
    """Resultado del cálculo de alícuota con todo el detalle del razonamiento."""
    # Actividad identificada
    naes_encontrado: str = ""
    actividad_desc_norma: str = ""
    alicuota_base: float = 0.0
    norma_ref_actividad: str = ""
    articulo_actividad: str = ""
    
    # Dictamen de la IA (Llenado por el Agente después)
    alicuota_ia: float = 0.0
    justificacion: str = ""

    # Escala de volumen
    categoria_volumen: str = ""
    modificador_volumen: float = 0.0
    norma_ref_escala: str = ""

    # Beneficios aplicados
    beneficios_aplicados: list[dict] = field(default_factory=list)
    reduccion_total_pct: float = 0.0

    # Resultado final
    alicuota_final: float = 0.0
    alicuota_ia: float = 0.0  # Determinado por el Agente LL

    # Warnings y notas
    justificacion: str = ""
    warnings: list[str] = field(default_factory=list)
    match_score: float = 0.0  # Similitud con la actividad más cercana (0-1)

    def calcular_final(self) -> None:
        """Aplica todos los modificadores y calcula la alícuota final."""
        alicuota = self.alicuota_base + self.modificador_volumen

        # Aplicar reducción porcentual de beneficios (el más favorable)
        if self.beneficios_aplicados:
            # Tomar el mayor beneficio (no se acumulan en la lógica fiscal PBA)
            max_reduccion = min(b["modificador_pct"] for b in self.beneficios_aplicados)  # min porque son negativos
            self.reduccion_total_pct = abs(max_reduccion)
            alicuota = alicuota * (1 + max_reduccion / 100)

        self.alicuota_final = round(max(0.0, alicuota), 4)


class TaxCalculator:
    """
    Calculador de alícuotas de IIBB para la provincia activa.
    Actualmente soporta Buenos Aires (fixture).
    """

    def __init__(self, provincia: str = "bsas", use_fixtures: bool = True):
        self.provincia = provincia
        self.loader = NormativaLoader(use_fixtures=use_fixtures)
        self.loader.load()

    def calcular(
        self,
        actividades_desc: str,
        volumen_ventas_anual: float,
        naes_code: str | None = None,
        situacion_especial: str | None = None,
    ) -> AlicuotaResult:
        """
        Ejecuta el cálculo completo de la alícuota usando la lógica de tramos reales.
        """
        result = AlicuotaResult()
        actividades = self.loader.get_actividades()

        # ── PASO 1: Identificar la actividad ─────────────────────────────────
        actividad = None
        if naes_code:
            actividad = self._find_by_naes(naes_code, actividades)
            if actividad: result.match_score = 1.0
        
        if not actividad:
            actividad, score = self._find_by_description(actividades_desc, actividades)
            result.match_score = score

        if not actividad:
            result.warnings.append("No se encontró una actividad equivalente. Requiere clasificación manual.")
            return result

        result.naes_encontrado = actividad["naes"]
        result.actividad_desc_norma = actividad["descripcion"]
        result.alicuota_base = actividad["alicuota_base"]
        result.norma_ref_actividad = actividad["norma_ref"]
        result.articulo_actividad = actividad["articulo"]

        # ── PASO 2: Determinar el tramo por volumen ─────────────────────────
        # En PBA real, tramo 7 es el mas bajo y T1 el mas alto.
        # Los limites en la normativa Errepar estan definidos como 'Hasta $X'.
        # Recorremos de menor a mayor.
        tramos_config = self.loader._data.get("tramos_escala", [])
        tramo_aplicable = 1 # Por defecto el mas alto si supera todo
        
        # Ordenamos tramos de menor a mayor limite para encontrar el primero que cumple
        sorted_tramos = sorted(tramos_config, key=lambda x: x['limite_anual'])
        for t in sorted_tramos:
            if volumen_ventas_anual <= t['limite_anual']:
                tramo_aplicable = t['numero']
                result.categoria_volumen = f"Tramo {tramo_aplicable}"
                break
        else:
            result.categoria_volumen = "Excede todos los tramos reducidos (General)"
            tramo_aplicable = 0 # 0 significa alicuota base

        # ── PASO 3: Aplicar alicuota del tramo ───────────────────────────────
        if tramo_aplicable > 0 and "tramos_reduccion" in actividad:
            alicuota_tramo = actividad["tramos_reduccion"].get(tramo_aplicable)
            if alicuota_tramo is not None:
                result.alicuota_final = alicuota_tramo
                result.warnings.append(f"Se aplicó tasa reducida por {result.categoria_volumen}.")
            else:
                result.alicuota_final = actividad["alicuota_base"]
        else:
            result.alicuota_final = actividad["alicuota_base"]

        # ── PASO 4: Aplicar beneficios por situación especial (si existen) ──
        # Aquí la IA ya analizó el texto, pero el calculador puede detectar keywords
        if situacion_especial:
            # (Lógica simplificada para POC)
            pass

        return result

    def _find_by_naes(self, naes_code: str, actividades: list[dict]) -> dict | None:
        """Búsqueda exacta por código NAES."""
        return next((a for a in actividades if a["naes"] == naes_code), None)

    def _find_by_description(
        self,
        descripcion: str,
        actividades: list[dict]
    ) -> tuple[dict | None, float]:
        """
        Búsqueda por similitud de descripción usando SequenceMatcher.
        Retorna (actividad_más_cercana, score).
        """
        if not actividades:
            return None, 0.0

        desc_lower = descripcion.lower()
        best_match = None
        best_score = 0.0

        for act in actividades:
            # Comparar con la descripción de la normativa
            score = difflib.SequenceMatcher(
                None, desc_lower, act["descripcion"].lower()
            ).ratio()

            # Bonus si palabras clave están en ambas descripciones
            words_input = set(desc_lower.split())
            words_norm = set(act["descripcion"].lower().split())
            overlap = len(words_input & words_norm) / max(len(words_input | words_norm), 1)
            combined_score = (score * 0.6) + (overlap * 0.4)

            if combined_score > best_score:
                best_score = combined_score
                best_match = act

        return best_match, round(best_score, 4)

    def _get_escala(
        self,
        volumen: float,
        categorias: list[dict]
    ) -> tuple[str, float, str]:
        """
        Determina la categoría de volumen aplicable y su modificador.
        Retorna (nombre_categoria, modificador_puntos, norma_ref).
        """
        for cat in categorias:
            vol_desde = cat.get("volumen_desde", 0)
            vol_hasta = cat.get("volumen_hasta", float("inf"))
            if vol_desde <= volumen <= vol_hasta:
                return cat["categoria"], cat["modificador"], cat["norma_ref"]

        # Fallback a la primera categoría si no hay match
        if categorias:
            cat = categorias[0]
            return cat["categoria"], cat["modificador"], cat["norma_ref"]

        return "No determinada", 0.0, ""
