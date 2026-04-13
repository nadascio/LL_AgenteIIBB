"""
core/constants.py — Constantes globales y utilidades de formato.
"""

JURISDICCIONES = {
    901: "CABA", 902: "Buenos Aires", 903: "Catamarca", 904: "Córdoba",
    905: "Corrientes", 906: "Chaco", 907: "Chubut", 908: "Entre Ríos",
    909: "Formosa", 910: "Jujuy", 911: "La Pampa", 912: "La Rioja",
    913: "Mendoza", 914: "Misiones", 915: "Neuquén", 916: "Río Negro",
    917: "Salta", 918: "San Juan", 919: "San Luis", 920: "Santa Cruz",
    921: "Santa Fe", 922: "Santiago del Estero", 923: "Tierra del Fuego",
    924: "Tucumán"
}

def format_percentage(val):
    """Convierte 5.0 a '5,00%'"""
    try:
        return f"{float(val):.2f}".replace(".", ",") + "%"
    except:
        return "0,00%"
