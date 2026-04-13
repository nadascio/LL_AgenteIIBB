"""
batch_processor.py — Motor de Procesamiento Masivo Senior (Word + Excel Detallado)

Genera informes formales (.docx) y resúmenes ejecutivos detallados (.xlsx).
"""

import pandas as pd
from datetime import datetime
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.progress import Progress

from core.agent import IIBBAgent, AgentInput, ActividadInput
from output.word_generator import generar_informe_word

console = Console()

def run_batch_audit(excel_path: str):
    # 1. Preparar Entorno
    agent = IIBBAgent()
    agent.initialize()
    
    input_file = Path(excel_path)
    if not input_file.exists():
        console.print(f"[red]Error: No se encontró el archivo {excel_path}[/red]")
        return

    # 2. Crear carpeta de salida
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(f"resultados/batch_{timestamp}")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 3. Leer y Validar
    df = pd.read_excel(input_file)
    df.columns = [c.lower().strip() for c in df.columns]
    
    # Agrupar por CUIT y Periodo para tratar al cliente como una unidad
    groups = df.groupby(['cuit', 'periodo'])
    console.print(f"[bold cyan]Cargados {len(df)} registros. Identificados {len(groups)} clientes únicos.[/bold cyan]")

    full_activity_results = []
    summary_results = []
    
    with Progress() as progress:
        task = progress.add_task("[green]Auditando clientes...", total=len(groups))
        
        for (cuit, periodo), group_df in groups:
            cuit_str = str(cuit)
            try:
                # 1. Recolectar todas las actividades del grupo
                act_list = []
                for _, row in group_df.iterrows():
                    act_str = str(row.get('actividades', ''))
                    act_descs = [a.strip() for a in act_str.split(';') if a.strip()]
                    
                    naes_str = str(row.get('naes', '')) if pd.notna(row.get('naes')) else ""
                    naes_codes = [n.strip() for n in naes_str.split(';') if n.strip()]
                    
                    for i, desc in enumerate(act_descs):
                        naes = naes_codes[i] if i < len(naes_codes) else None
                        act_list.append(ActividadInput(desc=desc, naes=naes))

                # 2. Tomar datos generales del primer registro del cliente
                first_row = group_df.iloc[0]
                volumen = float(first_row.get('volumen', 0))
                situacion = str(first_row.get('situacion_especial', '')) if pd.notna(first_row.get('situacion_especial')) else None
                provincia = str(first_row.get('provincia', 'bsas'))
                
                in_data = AgentInput(
                    cuit=cuit_str,
                    periodo=str(periodo),
                    volumen_ventas_anual=volumen,
                    actividades=act_list,
                    provincia_id=provincia,
                    alicuota_periodo_anterior=float(first_row['alicuota_anterior']) if pd.notna(first_row.get('alicuota_anterior')) else None,
                    analista=str(first_row.get('analista', 'Auditor Fiscal Agente LL')),
                    situacion_especial=situacion
                )

                # 3. EJECUTAR ANÁLISIS UNIFICADO
                res = agent.analizar(in_data)
                
                # 4. GENERAR UN SOLO WORD POR CLIENTE
                cuit_clean = cuit_str.replace('-', '')
                word_path = output_dir / f"Informe_Fiscal_{cuit_clean}.docx"
                generar_informe_word(
                    cuit=in_data.cuit,
                    periodo=in_data.periodo,
                    provincia_id=in_data.provincia_id,
                    volumen_ventas_anual=in_data.volumen_ventas_anual,
                    resultados_calc=res.resultados_por_actividad,
                    justificacion_llm=res.justificacion_llm,
                    situacion_especial=in_data.situacion_especial,
                    output_path=str(word_path)
                )

                # 5. RECOLECTAR PARA EXCEL (Cada actividad es una fila, pero comparten el Resumen Ejecutivo)
                for r_act in res.resultados_por_actividad:
                    full_activity_results.append({
                        "CUIT": in_data.cuit,
                        "Periodo": in_data.periodo,
                        "Jurisdiccion": in_data.provincia_id.upper(),
                        "NAES": r_act.naes_encontrado,
                        "Actividad": r_act.actividad_desc_norma,
                        "Tasa Base": r_act.alicuota_base,
                        "Tasa Sugerida": r_act.alicuota_final,
                        "Justificacion Normativa": f"{r_act.norma_ref_actividad} - Art. {r_act.articulo_actividad}",
                        "Resumen Ejecutivo (Auditor LL)": res.resumen_ejecutivo, # NUEVO CAMPO LIMPIO PARA EXCEL
                        "Situacion Especial": situacion or "Ninguna"
                    })

                summary_results.append({
                    "CUIT": cuit_str,
                    "Status": "COMPLETADO",
                    "Actividades": len(act_list),
                    "Archivo Word": word_path.name
                })

            except Exception as e:
                console.print(f"[yellow]Error en CUIT {cuit_str}: {str(e)}[/yellow]")
                summary_results.append({
                    "CUIT": cuit_str,
                    "Status": "ERROR",
                    "Detalle": str(e)
                })
            
            progress.update(task, advance=1)

    # 4. Generar Resumen Detallado y Ejecutivo en un solo Excel
    if full_activity_results:
        resumen_path = output_dir / "resumen_auditoria_ejecutivo.xlsx"
        with pd.ExcelWriter(resumen_path, engine='openpyxl') as writer:
            pd.DataFrame(full_activity_results).to_excel(writer, sheet_name='Detalle_Actividades', index=False)
            pd.DataFrame(summary_results).to_excel(writer, sheet_name='Resumen_Casos', index=False)
            
        console.print(f"\n[bold green]✅ Excel Ejecutivo agrupado generado para {len(summary_results)} clientes.[/bold green]")

    # 5. Mostrar Tabla Final
    table = Table(title="RESULTADO AUDITORÍA UNIFICADA POR CLIENTE")
    table.add_column("CUIT", style="cyan")
    table.add_column("Estado", style="bold")
    table.add_column("Actividades", style="magenta")
    table.add_column("Informe Word", style="green")
    
    for s in summary_results:
        table.add_row(s["CUIT"], s["Status"], str(s.get("Actividades", 0)), s.get("Archivo Word", "N/A"))
    
    console.print(table)
    console.print(f"\n[bold blue]📁 Archivos profesionales en:[/bold blue] {output_dir.absolute()}")

if __name__ == "__main__":
    import sys
    excel_to_process = sys.argv[1] if len(sys.argv) > 1 else "plantilla_auditoria_iibb.xlsx"
    run_batch_audit(excel_to_process)
