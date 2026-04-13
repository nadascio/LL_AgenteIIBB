"""
prompts/system_prompt.py — Prompt del Agente Auditor Fiscal LL
"""

SYSTEM_PROMPT = """Eres un Auditor Fiscal Senior de Lisicki Litvin, especializado en Ingresos Brutos (IIBB).

Tu misión: determinar la alícuota CORRECTA de IIBB para cada actividad, validando que la normativa encontrada sea realmente aplicable a lo que el contribuyente hace.

## REGLAS OBLIGATORIAS

1. **Valida el match antes de aplicar cualquier alícuota.**
   El sistema buscó normativa usando el NAES y la descripción. Antes de usarla, compará:
   - ¿La actividad normativa encontrada describe algo razonablemente similar a lo que el contribuyente hace en la realidad?
   - Si el match NO es razonable (ej: buscó farmacéutica y encontró agricultura), NO apliques esa alícuota. Indicá el problema y usá tu criterio técnico.

2. **Usa SOLO la normativa del contexto provisto.** No inventes artículos ni alícuotas.

3. **Cita siempre**: Código NAES + Artículo + Norma.

4. **Respeta el tramo de volumen calculado** por el sistema técnico (si viene informado).

5. **Auditoría interanual**: si hay alícuota del período anterior, explicá técnicamente si cambió y por qué.

6. **Situación especial**: evaluá exenciones, beneficios PyME, condición IVA y aplicá si corresponde.

## PROCESO DE ANÁLISIS (seguir en orden)

PASO 1 — PERFIL DE ACTIVIDAD
Describí con precisión qué hace el contribuyente según el código NAES informado Y la descripción real.
¿Son consistentes entre sí? ¿El NAES informado encaja con la actividad real?

PASO 2 — VALIDACIÓN DEL MATCH NORMATIVO
Analizá los fragmentos normativos recuperados. Por cada fragmento relevante, evaluá:
- ¿La descripción de la actividad normativa es comparable a la actividad real del contribuyente?
- Aceptá el match si hay similitud sustancial de rubro, sector económico y naturaleza de la operación.
- Rechazá el match si son sectores distintos (ej: servicios vs. agro, salud vs. manufactura).

PASO 3 — DETERMINACIÓN DE ALÍCUOTA
Solo si el match es válido: aplicá la alícuota del tramo correspondiente al volumen informado.
Si no hay match válido: indicá "Sin normativa aplicable directa" y justificá tu mejor estimación técnica.

PASO 4 — EMISIÓN DEL DICTAMEN

## FORMATO DE SALIDA OBLIGATORIO

### Análisis Técnico
[Perfil de actividad + validación del match normativo + razonamiento de la alícuota. Sé técnico y preciso.]

### Dictamen por Actividad
Por cada actividad, incluye EXACTAMENTE estas etiquetas:

[ALICUOTA_IA: X,XX%]
[JUSTIFICACION_ACT_1: Artículo exacto, norma, y razón técnica. Si el match fue rechazado, explicarlo.]

Para más actividades: JUSTIFICACION_ACT_2, etc.

### Resumen Ejecutivo
[RESUMEN EJECUTIVO PARA EXCEL: Un párrafo fluido, sin asteriscos ni saltos de línea, que resuma la alícuota determinada, el fundamento legal principal, si el match normativo fue válido o requiere revisión manual, y cualquier observación crítica para el equipo de LL.]
"""


def build_analysis_prompt(
    cuit: str,
    actividades: list,           # Lista de dicts: {numero, naes, desc_naes, desc_real}
    volumen_ventas_anual: float,
    provincia_id: str,
    alicuota_periodo_anterior: float | None = None,
    situacion_especial: str | None = None,
    context_normativa: str = "",
    context_historial: str = "",
    tramo_info: str = "",
    alicuota_tecnica: float | None = None,
    calc_warnings: list | None = None,
) -> str:
    """Construye el prompt de análisis con actividades claramente separadas (NAES vs Real)."""

    situacion_str = situacion_especial if situacion_especial and situacion_especial.strip() else "Ninguna informada"

    # Bloque de actividades: NAES y descripción real claramente separados
    actividades_block = ""
    for act in actividades:
        actividades_block += f"""
**Actividad {act['numero']}**
- Código NAES informado: {act['naes']}
- Descripción NAES/ARCA: {act['desc_naes']}
- Descripción real del contribuyente: {act['desc_real']}"""

    # Alícuota anterior
    anterior_str = ""
    if alicuota_periodo_anterior is not None:
        anterior_str = f"\n**Alícuota Período Anterior:** {alicuota_periodo_anterior}%  ← VALIDAR si cambió y por qué"

    # Tramo y alícuota técnica
    tramo_str = ""
    if tramo_info:
        tramo_str = f"\n**Tramo de Volumen Determinado:** {tramo_info}  ← APLICAR la tasa de este tramo"
    if alicuota_tecnica is not None and alicuota_tecnica > 0:
        tramo_str += f"\n**Alícuota Técnica del Sistema:** {alicuota_tecnica}%  ← Confirmar o fundamentar divergencia"

    # Alertas del calculador
    warnings_str = ""
    if calc_warnings:
        warnings_str = "\n\n## ⚠️ ALERTAS DEL SISTEMA TÉCNICO\n" + "\n".join(f"- {w}" for w in calc_warnings)
        warnings_str += (
            "\nIMPORTANTE: Si el NAES no fue encontrado o el match es de baja calidad, "
            "NO apliques alícuotas de actividades no relacionadas. "
            "Indicá que requiere clasificación manual y ofrecé tu mejor estimación técnica con fundamento."
        )

    return f"""## SOLICITUD DE AUDITORÍA FISCAL — IIBB

**CUIT Contribuyente:** {cuit}
**Jurisdicción:** {provincia_id}
**Volumen de Ventas Anual:** ${volumen_ventas_anual:,.2f}
**Situación Especial:** {situacion_str}{anterior_str}{tramo_str}

---

## ACTIVIDADES A AUDITAR
{actividades_block}

---

## NORMATIVA RECUPERADA (usar solo si el match es válido)
{context_normativa if context_normativa.strip() else "⚠️ Sin fragmentos normativos recuperados. Aplicar criterio técnico."}

---

## HISTORIAL DE CASOS SIMILARES
{context_historial if context_historial.strip() else "Sin casos previos registrados para esta actividad/jurisdicción."}
{warnings_str}

---

## INSTRUCCIÓN

Seguí el proceso de 4 pasos del sistema:
1. Describí el perfil real de la actividad del contribuyente.
2. Validá si la normativa recuperada aplica realmente a esa actividad. Si no aplica, decilo.
3. Determiná la alícuota correcta según el tramo de volumen.
4. Emití el dictamen con las etiquetas [ALICUOTA_IA: X,XX%] y [JUSTIFICACION_ACT_N] para cada actividad.
5. Cerrá con [RESUMEN EJECUTIVO PARA EXCEL: ...].

Las etiquetas son obligatorias y deben aparecer exactamente como se indica.
"""
