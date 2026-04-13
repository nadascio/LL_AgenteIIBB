import pandas as pd
from pathlib import Path

def crear_plantilla():
    # Definir las columnas estándar corporativas corregidas
    columnas = [
        "cuit", 
        "periodo",
        "volumen", 
        "actividades", 
        "naes",
        "alicuota_anterior",
        "provincia", 
        "analista",
        "situacion_especial"
    ]
    
    # Ejemplo completo
    ejemplo = {
        "cuit": ["30-11111111-1", "33-22222222-3"],
        "periodo": ["2026", "2026"],
        "volumen": [5000000, 1500000],
        "actividades": ["Matanza de ganado bovino; Venta de carne", "Servicios de consultoria"],
        "naes": ["101011; 472130", "749000"],
        "alicuota_anterior": [0.0, 3.5],
        "provincia": ["bsas", "bsas"],
        "analista": ["Nahuel", "Nahuel"],
        "situacion_especial": ["Beneficio industrial Art. 20 - Empresa con planta en zona promocionada", "Exento por Ley XXX - Situación de exportación de servicios pura"]
    }
    
    df = pd.DataFrame(ejemplo)
    
    output_path = Path("plantilla_auditoria_iibb.xlsx")
    df.to_excel(output_path, index=False)
    
    print(f"Planilla maestra ACTUALIZADA en: {output_path.absolute()}")

if __name__ == "__main__":
    crear_plantilla()
