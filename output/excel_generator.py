"""
output/excel_generator.py — Generador de Reportes Excel Corporativos LL
"""

import os
import xlsxwriter
from datetime import datetime
from typing import List, Dict, Any

def generate_excel_report(
    audit_data: Dict[str, Any],
    results: List[Dict[str, Any]],
    output_path: str
):
    """
    Genera un reporte Excel con estética Premium de Lisicki Litvin.
    """
    workbook = xlsxwriter.Workbook(output_path)
    worksheet = workbook.add_worksheet("Resumen de Auditoría")

    # --- DEFINICIÓN DE ESTILOS ---
    blue_ll = '#003366'  # Azul corporativo LL
    white = '#FFFFFF'
    light_gray = '#F2F2F2'

    header_format = workbook.add_format({
        'bold': True,
        'font_color': white,
        'bg_color': blue_ll,
        'border': 1,
        'align': 'center',
        'valign': 'vcenter',
        'font_name': 'Arial',
        'font_size': 12
    })

    sub_header_format = workbook.add_format({
        'bold': True,
        'bg_color': light_gray,
        'border': 1,
        'font_name': 'Arial'
    })

    cell_format = workbook.add_format({
        'border': 1,
        'font_name': 'Arial',
        'valign': 'vcenter'
    })

    percent_format = workbook.add_format({
        'border': 1,
        'num_format': '0.00%',
        'align': 'center',
        'valign': 'vcenter'
    })

    multiline_format = workbook.add_format({
        'border': 1,
        'text_wrap': True,
        'valign': 'top',
        'font_name': 'Arial',
        'font_size': 10
    })

    title_format = workbook.add_format({
        'bold': True,
        'font_size': 16,
        'font_color': blue_ll,
        'font_name': 'Arial'
    })

    # --- DISEÑO DEL CONTENIDO ---
    
    # Título y Logo (Simulado por texto)
    worksheet.merge_range('A1:F1', "INFORME TÉCNICO DE ALÍCUOTAS - LISICKI LITVIN", title_format)
    worksheet.write('A2', f"Fecha de Generación: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    
    # Datos del Cliente
    worksheet.write('A4', "DATOS DEL CONTRIBUYENTE", sub_header_format)
    worksheet.write('A5', "CUIT:", cell_format)
    worksheet.write('B5', audit_data.get('cuit', 'N/A'), cell_format)
    worksheet.write('A6', "Jurisdicción:", cell_format)
    worksheet.write('B6', audit_data.get('provincia', 'N/A'), cell_format)
    worksheet.write('A7', "Volumen Anual:", cell_format)
    worksheet.write('B7', audit_data.get('volumen', 0.0), workbook.add_format({'num_format': '$ #,##0.00', 'border': 1}))

    # Resumen Ejecutivo (IA)
    worksheet.merge_range('A9:F9', "RESUMEN EJECUTIVO (DICTAMEN IA)", header_format)
    resumen_raw = audit_data.get('resumen_ia', 'Sin resumen.')
    # Limpiar si es un error técnico crudo antes de escribirlo
    ERROR_KEYWORDS = ['RESOURCE_EXHAUSTED', 'NOT_FOUND', 'quotaMetric', 'Traceback', 'type.googleapis']
    if any(kw in str(resumen_raw) for kw in ERROR_KEYWORDS):
        resumen_limpio = "⚠️ Motor de IA no disponible al momento del procesamiento. Por favor, reprocese este contribuyente cuando la cuota de API esté disponible."
    else:
        resumen_limpio = resumen_raw
    worksheet.merge_range('A10:F13', resumen_limpio, multiline_format)

    # Tabla Comparativa de Alícuotas
    worksheet.write('A15', "DETALLE FEDERAL DE ACTIVIDADES Y ALÍCUOTAS", sub_header_format)
    
    headers = ["Jurisdicción", "Actividad", "NAES", "Alíc. Base", "Alíc. Sugerida (Tramo)", "DICTAMEN AGENTE LL", "Normativa Ref"]
    worksheet.set_column('A:A', 20)  # Jurisdicción
    worksheet.set_column('B:B', 40)  # Actividad
    worksheet.set_column('C:C', 10)  # NAES
    worksheet.set_column('D:F', 18)  # Alícuotas
    worksheet.set_column('G:G', 40)  # Normativa

    for col, header in enumerate(headers):
        worksheet.write(16, col, header, header_format)

    row = 17
    for res in results:
        worksheet.write(row, 0, audit_data.get('provincia', 'N/A'), cell_format)
        worksheet.write(row, 1, res.get('actividad_desc'), cell_format)
        worksheet.write(row, 2, res.get('naes'), cell_format)
        worksheet.write(row, 3, res.get('alicuota_base', 0.0) / 100, percent_format)
        worksheet.write(row, 4, res.get('alicuota_sugerida', 0.0) / 100, percent_format)
        
        # Resaltar la alícuota de la IA si es diferente a la sugerida
        ia_rate = res.get('alicuota_ia', 0.0)
        final_cell_format = percent_format
        if ia_rate != res.get('alicuota_sugerida', 0.0):
            final_cell_format = workbook.add_format({
                'border': 1, 'num_format': '0.00%', 'align': 'center', 
                'valign': 'vcenter', 'bg_color': '#E6F3FF', 'bold': True
            })
        
        worksheet.write(row, 5, ia_rate / 100, final_cell_format)
        worksheet.write(row, 6, res.get('normativa_ref'), multiline_format)
        row += 1

    # Nota al pie
    worksheet.write(row + 2, 0, "Este informe es generado por la plataforma Tax Audit AI v3.0 - Lisicki Litvin.", workbook.add_format({'italic': True, 'font_size': 9}))

    workbook.close()
    return output_path
