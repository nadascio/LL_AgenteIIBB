"""
main.py — Entry Point del Agente de Ingresos Brutos (Soporte Multi-Actividad)

CLI interactivo para clasificación y auditoría fiscal provincial.
Soporta múltiples actividades por contribuyente.
"""

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.prompt import Prompt, FloatPrompt, Confirm
from rich.panel import Panel

BANNER = """
================================================
  AGENTE IIBB - Clasificacion y Auditoria Fiscal
  Ingresos Brutos Provinciales
  [ Hito 1 POC - v0.1.0 ]
================================================
"""

console = Console()

PROVINCIAS_SOPORTADAS = {
    "bsas": "Buenos Aires",
}

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Agente IIBB — Clasificación y Auditoría Fiscal",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--cuit", help="CUIT del contribuyente (ej: 30-12345678-1)")
    # Cambiamos a action="append" para soportar múltiples actividades
    parser.add_argument("--actividad", action="append", help="Descripción de la actividad económica (repetible)")
    parser.add_argument("--naes", action="append", help="Código NAES (repetible, debe coincidir en orden con actividad)")
    
    parser.add_argument("--provincia", choices=list(PROVINCIAS_SOPORTADAS.keys()), help="Código de provincia (ej: bsas)")
    parser.add_argument("--volumen", type=float, help="Volumen de ventas anual en pesos")
    parser.add_argument("--alicuota-anterior", type=float, dest="alicuota_anterior", help="Alícuota anterior (%%)")
    parser.add_argument("--tags", nargs="+", help="Tags especiales (ej: PyME)")
    parser.add_argument("--analista", help="Nombre del analista")
    parser.add_argument("--reindex", action="store_true", help="Forzar reindexado")
    parser.add_argument("--historial", action="store_true", help="Ver historial")
    return parser.parse_args()

def interactive_input(args: argparse.Namespace) -> dict:
    console.print()
    cuit = args.cuit or Prompt.ask("[cyan]CUIT del contribuyente[/cyan]", default="30-12345678-1")

    # Manejo de múltiples actividades
    lista_actividades = []
    
    if args.actividad:
        # Si se pasaron por CLI
        for i, desc in enumerate(args.actividad):
            naes = args.naes[i] if args.naes and i < len(args.naes) else None
            lista_actividades.append({"desc": desc, "naes": naes})
    else:
        # Modo interactivo - Loop de actividades
        while True:
            desc = Prompt.ask(f"[cyan]Descripción de actividad #{len(lista_actividades)+1}[/cyan]")
            naes_input = Prompt.ask(f"[dim]Código NAES para esta actividad (Enter para omitir)[/dim]", default="")
            naes = naes_input if naes_input.strip() else None
            
            lista_actividades.append({"desc": desc, "naes": naes})
            
            if not Confirm.ask("¿Deseás ingresar otra actividad para este cliente?", default=False):
                break

    provincia = args.provincia
    if not provincia:
        opciones = " | ".join([f"[bold]{k}[/bold]={v}" for k, v in PROVINCIAS_SOPORTADAS.items()])
        console.print(f"  Provincias disponibles: {opciones}")
        provincia = Prompt.ask("[cyan]Provincia[/cyan]", choices=list(PROVINCIAS_SOPORTADAS.keys()), default="bsas")

    volumen = args.volumen or FloatPrompt.ask("[cyan]Volumen de ventas anual TOTAL ($)[/cyan]", default=5000000.0)

    # Opcionales
    alicuota_anterior = args.alicuota_anterior
    if alicuota_anterior is None:
        if Confirm.ask("[dim]¿Tenés la alícuota del período anterior? (auditoría)[/dim]", default=False):
            alicuota_anterior = FloatPrompt.ask("[cyan]Alícuota período anterior (%)[/cyan]")

    tags = args.tags
    if tags is None:
        tags_input = Prompt.ask("[dim]Condiciones especiales (ej: PyME, o Enter para omitir)[/dim]", default="")
        tags = [t.strip() for t in tags_input.split(",") if t.strip()] if tags_input.strip() else None

    return {
        "cuit": cuit,
        "actividades": lista_actividades,
        "provincia_id": provincia,
        "volumen_ventas_anual": volumen,
        "alicuota_periodo_anterior": alicuota_anterior,
        "tags_condicion": tags,
        "analista": args.analista,
    }

def main():
    console.print(f"[bold cyan]{BANNER}[/bold cyan]")
    args = parse_args()

    if args.historial:
        from memory.case_history import CaseHistory
        # Mostrar historial simplificado (lógica previa)
        return

    if args.reindex:
        console.print("[yellow][REINDEX] Iniciando re-indexacion...[/yellow]")
        from core.agent import IIBBAgent
        agent = IIBBAgent()
        agent.initialize(force_reindex=True)
        if not args.cuit and not args.actividad: return

    inputs = interactive_input(args)

    # Resumen de lo ingresado
    resumen_acts = "\n".join([f"  - {a['desc']} (NAES: {a['naes'] or '?'})" for a in inputs['actividades']])
    
    console.print(
        Panel(
            f"[bold]Provincia:[/bold] {PROVINCIAS_SOPORTADAS[inputs['provincia_id']]}\n"
            f"[bold]CUIT:[/bold] {inputs['cuit']}\n"
            f"[bold]Actividades:[/bold]\n{resumen_acts}\n"
            f"[bold]Volumen Total:[/bold] ${inputs['volumen_ventas_anual']:,.2f}\n"
            f"[bold]Tags:[/bold] {', '.join(inputs['tags_condicion'] or []) or '—'}",
            title="[bold] Parametros del Analisis Multiactividad [/bold]",
            border_style="dim"
        )
    )

    if not Confirm.ask("\n¿Ejecutar análisis consolidado?", default=True):
        return

    from core.agent import IIBBAgent, AgentInput
    agent = IIBBAgent()
    
    agent_input = AgentInput(
        cuit=inputs["cuit"],
        volumen_ventas_anual=inputs["volumen_ventas_anual"],
        actividades=inputs["actividades"],
        provincia_id=inputs["provincia_id"],
        alicuota_periodo_anterior=inputs.get("alicuota_periodo_anterior"),
        tags_condicion=inputs.get("tags_condicion"),
        analista=inputs.get("analista"),
    )

    result = agent.analizar(agent_input)

    # ── VALIDACIÓN DEL EXPERTO (NUEVO) ──
    console.print("\n")
    console.rule("[bold yellow]📥 VALIDACIÓN DEL AUDITOR[/bold yellow]")
    console.print("[dim]Elegí una opción para nutrir la base de conocimiento del equipo:[/dim]")
    console.print("  [bold]V[/bold] - Validar: Confirmar que el criterio es correcto.")
    console.print("  [bold]C[/bold] - Corregir: Criterio erróneo. Ingresar alícuota/norma manual.")
    console.print("  [bold]O[/bold] - Observar: El criterio es OK, pero quiero agregar una nota técnica.")
    console.print("  [bold]N[/bold] - Omitir: Finalizar sin registrar validación.")
    
    opcion = Prompt.ask("\n¿Qué acción deseas tomar?", choices=["v", "c", "o", "n"], default="v").lower()

    if opcion == "v":
        agent.history.update_validation(result.caso_id, expert_validated=True, expert_comments="Validado y confirmado por auditor.")
        console.print("[green]✔ Caso validado con éxito.[/green]")
    
    elif opcion == "o":
        comentario = Prompt.ask("[cyan]Ingresá tu observación técnica[/cyan]")
        agent.history.update_validation(result.caso_id, expert_validated=True, expert_comments=comentario)
        console.print("[green]✔ Observación registrada.[/green]")
        
    elif opcion == "c":
        nueva_ali = FloatPrompt.ask("[red]Ingresá la alícuota correcta (%)[/red]")
        nueva_norma = Prompt.ask("[red]Ingresá el sustento normativo/articulo[/red]")
        comentario = Prompt.ask("[cyan]Motivo de la corrección (para futuros análisis)[/cyan]")
        agent.history.update_validation(
            result.caso_id, 
            expert_validated=True, 
            expert_comments=comentario,
            final_alicuota=nueva_ali,
            manual_norma=nueva_norma
        )
        console.print("[yellow]⚠ Criterio corregido y registrado como VERDAD para el futuro.[/yellow]")

    elif opcion == "n":
        console.print("[dim]Análisis finalizado sin validación adicional.[/dim]")

    if Confirm.ask("\n¿Guardar reporte final en archivo .txt?", default=False):
        output_dir = Path("resultados")
        output_dir.mkdir(exist_ok=True)
        filename = f"resultado_{inputs['cuit'].replace('-', '')}_{result.caso_id}.txt"
        (output_dir / filename).write_text(result.output_texto, encoding="utf-8")
        console.print(f"[green]Reporte guardado en: {output_dir / filename}[/green]")

if __name__ == "__main__":
    main()
