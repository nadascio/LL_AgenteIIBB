"""
output/formatter.py — Formateador de resultados fiscales (Soporte Multi-Actividad)

Genera la salida estructurada permitiendo visualizar múltiples actividades
en un solo reporte consolidado.
"""

from __future__ import annotations
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

console = Console()

def format_resultado(
    cuit: str,
    provincia_id: str,
    actividades_desc: str,
    volumen_ventas_anual: float,
    resultados_calc: list[any], # Lista de AlicuotaResult
    justificacion_llm: str,
    auditoria: dict | None = None,
    casos_similares: list[dict] | None = None,
    caso_id_registrado: str | None = None,
) -> str:
    """
    Genera el output final soportando múltiples actividades.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # ── Texto plano para exportación ──
    lineas = []
    lineas.append(f"RESULTADO DEL ANÁLISIS FISCAL CONSOLIDADO - CUIT {cuit}")
    lineas.append(f"Generado: {now}")
    lineas.append(f"Provincia: {provincia_id.upper()} | Volumen: ${volumen_ventas_anual:,.2f}")
    lineas.append("\n[ACTIVIDADES ANALIZADAS]")
    for r in resultados_calc:
        lineas.append(f"- {r.actividad_desc_norma} (NAES: {r.naes_encontrado}) -> {r.alicuota_final}%")
    
    lineas.append("\n[JUSTIFICACIÓN FISCAL]")
    lineas.append(justificacion_llm)
    
    if caso_id_registrado:
        lineas.append(f"\nCaso registrado: #{caso_id_registrado}")
    
    output_texto = "\n".join(lineas)

    # ── Renderizado Rich ──
    console.rule("[bold cyan]AGENTE IIBB — REPORTE CONSOLIDADO[/bold cyan]")
    
    # Tabla de Resultados
    table = Table(title="Detalle de Alícuotas por Actividad", box=box.ROUNDED, header_style="bold magenta")
    table.add_column("Código NAES", style="dim")
    table.add_column("Actividad Normativa")
    table.add_column("Tasa Base", justify="right")
    table.add_column("Tasa Final", justify="right", style="bold green")
    
    for r in resultados_calc:
        table.add_row(
            str(r.naes_encontrado),
            r.actividad_desc_norma[:50] + "...",
            f"{r.alicuota_base}%",
            f"{r.alicuota_final}%"
        )
    
    console.print(table)

    # Justificación
    console.print(Panel(
        justificacion_llm.strip(),
        title="[bold blue]Dictamen del Auditor Fiscal[/bold blue]",
        border_style="blue"
    ))

    if caso_id_registrado:
        console.print(f"\n[dim]ID de auditoría: [bold]#{caso_id_registrado}[/bold][/dim]")
    
    console.rule(style="dim")
    
    return output_texto
