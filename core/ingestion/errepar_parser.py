import os
import re
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional

class ErreparParser:
    """
    Parser genérico para procesar archivos HTML de normativas provinciales
    provenientes de Errepar/Erreius.
    """

    def __init__(self, html_path: str):
        self.html_path = html_path
        self.soup = None
        self.tramos = []
        self.alicuotas = []
        self.provincia = "Desconocida"

    def load(self):
        """Carga y limpia el HTML."""
        if not os.path.exists(self.html_path):
            raise FileNotFoundError(f"No se encontró el archivo: {self.html_path}")
        
        with open(self.html_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            self.soup = BeautifulSoup(content, 'lxml')
        
        # Intentar detectar provincia desde el titulo
        title = self.soup.find('title')
        if title:
            self.provincia = title.get_text().strip()

    def extract_tramos(self) -> List[Dict[str, Any]]:
        """
        Extrae la definición de los tramos de facturación (límites de ingresos).
        Busca patrones como 'Tramo 1: cuando el total de ingresos no supere la suma de $...'
        """
        tramos = []
        # Buscar párrafos que contengan 'Tramo' y montos en pesos
        paragraphs = self.soup.find_all('p')
        for p in paragraphs:
            text = p.get_text().strip()
            if "Tramo" in text and "$" in text:
                # Regex para encontrar el número de tramo y el monto
                match_tramo = re.search(r"Tramo\s+(\d+)", text, re.I)
                match_monto = re.search(r"\$\s*([\d\.]+)", text)
                
                if match_tramo and match_monto:
                    numero = int(match_tramo.group(1))
                    monto_str = match_monto.group(1).replace(".", "")
                    try:
                        monto = float(monto_str)
                        tramos.append({
                            "numero": numero,
                            "limite_anual": monto,
                            "descripcion": text
                        })
                    except ValueError:
                        continue
        
        self.tramos = sorted(tramos, key=lambda x: x['numero'])
        return self.tramos

    def extract_alicuotas(self) -> List[Dict[str, Any]]:
        """
        Extrae las tablas de alícuotas.
        Busca tablas que contengan códigos numéricos de actividad (NAES/NAIIB).
        """
        alicuotas = []
        tables = self.soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            if len(rows) < 2: continue
            
            # Detectar cabecera (columnas de tramos)
            headers = [td.get_text().strip() for td in rows[0].find_all(['td', 'th'])]
            
            for row in rows[1:]:
                cols = [td.get_text().strip() for td in row.find_all('td')]
                if not cols or len(cols) < 3: continue
                
                # Un código NAES suele ser una cadena numérica de 4 a 6 dígitos
                codigo = cols[0].replace("\xa0", "").strip()
                # A veces el código está en la segunda columna si la primera es vacía
                if not codigo and len(cols) > 1:
                    codigo = cols[1].replace("\xa0", "").strip()
                
                if re.match(r"^\d+$", codigo):
                    # Es una fila de actividad
                    descripcion = cols[2] if len(cols) > 2 else ""
                    alicuota_base = cols[3] if len(cols) > 3 else "0%"
                    
                    # Extraer alícuotas por tramo si existen
                    tramos_val = {}
                    for i in range(4, len(cols)):
                        if i-3 <= 7: # Hasta 7 tramos usualmente
                            tramos_val[f"tramo_{i-3}"] = cols[i]
                    
                    alicuotas.append({
                        "codigo": codigo,
                        "descripcion": descripcion,
                        "alicuota_base": alicuota_base,
                        "tramos": tramos_val
                    })
        
        self.alicuotas = alicuotas
        return alicuotas

    def to_markdown(self) -> str:
        """Genera una representación en Markdown optimizada para RAG."""
        md = [f"# Normativa IIBB - {self.provincia}\n"]
        
        if self.tramos:
            md.append("## Escala de Ingresos (Tramos)\n")
            for t in self.tramos:
                md.append(f"- **Tramo {t['numero']}**: Hasta ${t['limite_anual']:,.2f}")
            md.append("\n")
        
        if self.alicuotas:
            md.append("## Tabla de Alícuotas por Actividad\n")
            md.append("| Código | Actividad | Base | T1 | T2 | T3 | T4 | T5 | T6 | T7 |")
            md.append("|--------|-----------|------|----|----|----|----|----|----|----|")
            for a in self.alicuotas:
                t = a['tramos']
                row = [
                    a['codigo'],
                    a['descripcion'][:60],
                    a['alicuota_base'],
                    t.get('tramo_1', '-'),
                    t.get('tramo_2', '-'),
                    t.get('tramo_3', '-'),
                    t.get('tramo_4', '-'),
                    t.get('tramo_5', '-'),
                    t.get('tramo_6', '-'),
                    t.get('tramo_7', '-')
                ]
                md.append(f"| {' | '.join(row)} |")
        
        return "\n".join(md)

if __name__ == "__main__":
    # Test rápido
    parser = ErreparParser("normativas/bsas/raw/Buenos aires.html")
    parser.load()
    parser.extract_tramos()
    parser.extract_alicuotas()
    print(parser.to_markdown()[:1000] + "...")
