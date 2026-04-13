import pandas as pd
from pathlib import Path

def crear_plantilla():
    # Columnas EXACTAS de la versión Premium LL
    columnas = [
        "Cuit", "Periodo", "Condicion_IVA", "Volumen de Venta", 
        "Desc_Actividad_NAES", "Codigo_NAES", "Des_Actividad_Real", 
        "Alicuota_Anterior", "Codigo_Jurisdiccion", "Situacion_Especial"
    ]
    
    # Ejemplo con datos reales de la captura
    ejemplo = {
        "Cuit": ["30-71452638-9"],
        "Periodo": ["2026"],
        "Condicion_IVA": ["RI"],
        "Volumen de Venta": [1500000],
        "Desc_Actividad_NAES": ["Servicios de consultoría informática"],
        "Codigo_NAES": [620100],
        "Des_Actividad_Real": ["Desarrollo de software y exportación de servicios a España"],
        "Alicuota_Anterior": [1.5],
        "Codigo_Jurisdiccion": [902],
        "Situacion_Especial": ["Empresa PyME con certificado vigente"]
    }
    
    df = pd.DataFrame(ejemplo)
    
    output_path = Path("Plantilla_Auditoria_Modelo.xlsx")
    df.to_excel(output_path, index=False)
    
    print(f"Plantilla PREMIUM generada en: {output_path.absolute()}")

if __name__ == "__main__":
    crear_plantilla()
