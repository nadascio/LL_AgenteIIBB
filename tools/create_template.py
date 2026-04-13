import pandas as pd
import xlsxwriter
import os

def create_premium_template():
    filename = 'Plantilla_Auditoria_LL_Premium.xlsx'
    
    # 1. Definir columnas y sus notas explicativas
    columns = [
        "Cuit", "Periodo", "Condicion_IVA", "Volumen de Venta", 
        "Desc_Actividad_NAES", "Codigo_NAES", "Des_Actividad_Real", 
        "Alicuota_Anterior", "Codigo_Jurisdiccion", "Situacion_Especial"
    ]
    
    notes = {
        "Cuit": "Ingrese el CUIT sin guiones (ej: 30111111111).",
        "Periodo": "Ingrese el mes y año (AAAA-MM).",
        "Condicion_IVA": "RI: Responsable Inscripto\nMT: Monotributista\nEX: Exento",
        "Volumen de Venta": "Monto neto de facturación para este período/jurisdicción.",
        "Desc_Actividad_NAES": "Descripción oficial según el nomenclador NAES de AFIP.",
        "Codigo_NAES": "Código numérico de 6 dígitos de la actividad.",
        "Des_Actividad_Real": "IMPORTANTE: Describa con sus palabras qué hace el cliente realmente. Esto ayuda a la IA a detectar exenciones.",
        "Alicuota_Anterior": "Alícuota aplicada en la última declaración (ej: 3.5).",
        "Codigo_Jurisdiccion": "901: CABA\n902: Buenos Aires\n903: Catamarca\n904: Córdoba\n905: Corrientes\n906: Chaco\n907: Chubut\n908: Entre Ríos\n909: Formosa\n910: Jujuy\n911: La Pampa\n912: La Rioja\n913: Mendoza\n914: Misiones\n915: Neuquén\n916: Río Negro\n917: Salta\n918: San Juan\n919: San Luis\n920: Santa Cruz\n921: Santa Fe\n922: Santiago del Estero\n923: Tierra del Fuego\n924: Tucumán",
        "Situacion_Especial": "Notas sobre exenciones, artículos de ley o situaciones atípicas."
    }
    
    # 2. Crear el archivo Excel con XlsxWriter
    workbook = xlsxwriter.Workbook(filename)
    worksheet = workbook.add_worksheet("Datos Auditoría")
    
    # Formatos
    header_fmt = workbook.add_format({
        'bold': True, 
        'bg_color': '#1D3557', 
        'font_color': 'white',
        'border': 1
    })
    
    # 3. Escribir encabezados y notas
    for col_num, header in enumerate(columns):
        worksheet.write(0, col_num, header, header_fmt)
        if header in notes:
            worksheet.write_comment(0, col_num, notes[header], {'width': 250, 'height': 150})
            
    # Ajustar ancho de columnas
    worksheet.set_column(0, len(columns)-1, 20)
    
    # Agregar datos de ejemplo
    example_data = [
        "30-71452638-9", "2026-01", "RI", 1500000.0, 
        "Servicios de consultoría informática", "620100", 
        "Desarrollo de software y exportación de servicios a España", 
        1.5, 902, "Empresa PyME con certificado vigente"
    ]
    for col_num, val in enumerate(example_data):
        worksheet.write(1, col_num, val)

    workbook.close()
    print(f"✅ Plantilla Premium generada: {filename}")

if __name__ == "__main__":
    create_premium_template()
