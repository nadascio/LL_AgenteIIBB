"""
normativas/bsas/loader.py — Cargador de normativas para Buenos Aires

Modo FIXTURE: carga datos hardcodeados desde JSON (no requiere PDFs).
Modo PDF: parsea y segmenta PDFs por artículo/párrafo (Hito 2+).
"""

import json
import re
from pathlib import Path
from typing import Any

FIXTURES_DIR = Path(__file__).parent / "fixtures"
RAW_DIR = Path(__file__).parent / "raw"


class NormativaLoader:
    """Carga y expone las normativas de la provincia de Buenos Aires."""

    def __init__(self, use_fixtures: bool = True):
        self.use_fixtures = use_fixtures
        self._data: dict[str, Any] = {}
        self._loaded = False

    def load(self) -> None:
        if self._loaded:
            return
        
        real_md_path = RAW_DIR / "normativa_real_bsas.md"
        
        if not self.use_fixtures and real_md_path.exists():
            self._load_from_markdown(real_md_path)
        else:
            if not self.use_fixtures:
                print(f"[LOADER] Archivo real no encontrado en {real_md_path}. Usando fixtures.")
            self._load_fixtures()
            
        self._loaded = True

    def _load_from_markdown(self, path: Path) -> None:
        """Parsea el Markdown generado para extraer la data estructurada."""
        print(f"[LOADER] Cargando normativa real desde {path.name}")
        
        actividades = []
        tramos_escala = []
        
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            
            # Extraer Tramos (Escala de Ingresos)
            tramos_matches = re.finditer(r"- \*\*Tramo (\d+)\*\*: Hasta \$([\d\.,]+)", content)
            for m in tramos_matches:
                tramos_escala.append({
                    "numero": int(m.group(1)),
                    "limite_anual": float(m.group(2).replace(",", "").replace(".", "")) / 100 if "." in m.group(2) else float(m.group(2).replace(",", ""))
                })
            
            # Extraer Tabla de Alícuotas
            # Buscamos filas: | Código | Actividad | Base | T1 | ... |
            table_rows = re.findall(r"\| (\d+) \| (.*?) \| (.*?) \| (.*?) \| (.*?) \| (.*?) \| (.*?) \| (.*?) \| (.*?) \| (.*?) \|", content)
            for row in table_rows:
                # Limpiar porcentajes 0,75% -> 0.75
                def clean_pct(val):
                    val = val.strip().replace("%", "").replace(",", ".")
                    try: return float(val)
                    except: return 0.0

                actividades.append({
                    "naes": row[0],
                    "descripcion": row[1].strip(),
                    "alicuota_base": clean_pct(row[2]),
                    "tramos_reduccion": {
                        1: clean_pct(row[3]),
                        2: clean_pct(row[4]),
                        3: clean_pct(row[5]),
                        4: clean_pct(row[6]),
                        5: clean_pct(row[7]),
                        6: clean_pct(row[8]),
                        7: clean_pct(row[9])
                    },
                    "norma_ref": "Ley Impositiva 2026 (BA)",
                    "articulo": "20",
                    "notas": ""
                })

        self._data = {
            "actividades": actividades,
            "tramos_escala": sorted(tramos_escala, key=lambda x: x['limite_anual']),
            "_meta": {
                "norma_base": "Ley Impositiva 2026",
                "jurisdiccion": "Buenos Aires",
                "fuente": "Errepar"
            }
        }

    def get_actividades(self) -> list[dict]:
        """Retorna la lista de actividades con sus alícuotas."""
        return self._data.get("actividades", [])

    def get_escalas_volumen(self) -> dict:
        """
        Retorna las escalas de modificación por volumen de ventas.
        Mapea los tramos reales al formato que espera el TaxCalculator.
        """
        tramos = self._data.get("tramos_escala", [])
        return {"categorias": tramos}

    def get_beneficios_especiales(self) -> list[dict]:
        """Retorna los beneficios/exenciones especiales por tag."""
        return self._data.get("beneficios_especiales", [])

    def get_meta(self) -> dict:
        """Retorna metadatos de la normativa (norma base, decreto, etc.)."""
        return self._data.get("_meta", {})

    def get_all_as_text_chunks(self) -> list[dict]:
        """
        Convierte toda la normativa en chunks de texto para indexar en ChromaDB.
        Incluye porcentajes por tramo para mayor precisión del LLM.
        """
        chunks = []
        meta = self.get_meta()

        for act in self.get_actividades():
            tramos_text = ", ".join([f"T{k}: {v}%" for k, v in act.get('tramos_reduccion', {}).items()])
            text = (
                f"Actividad NAES {act['naes']}: {act['descripcion']}. "
                f"Alícuota base: {act['alicuota_base']}%. "
                f"Tasas reducidas por tramo de ingresos: {tramos_text}. "
                f"Norma: {act['norma_ref']}. "
                f"Artículo: {act['articulo']}."
            )
            chunks.append({
                "id": f"bsas_naes_{act['naes']}",
                "text": text,
                "metadata": {
                    "provincia": "bsas",
                    "tipo": "actividad",
                    "naes": act["naes"],
                    "alicuota_base": act["alicuota_base"],
                    "articulo": act["articulo"],
                    "norma_ref": act["norma_ref"],
                    "jurisdiccion": "bsas"
                }
            })

        tramos = self._data.get("tramos_escala", [])
        for t in tramos:
            text = f"Escala de ingresos IIBB BSAS - Tramo {t['numero']}: ingresos hasta ${t['limite_anual']:,.0f}."
            chunks.append({
                "id": f"bsas_tramo_{t['numero']}",
                "text": text,
                "metadata": {
                    "provincia": "bsas",
                    "tipo": "escala_volumen",
                    "tramo": t["numero"],
                    "limite": t["limite_anual"]
                }
            })

        return chunks
