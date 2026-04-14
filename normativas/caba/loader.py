"""
normativas/caba/loader.py — Cargador de normativas para Ciudad Autónoma de Buenos Aires

Parsea el HTML oficial de la Ley Impositiva CABA (Ley 6927) para extraer
las alícuotas de IIBB por actividad NAES.

Estructura del HTML:
  - Tablas con una sola alícuota: 3 cols (Código NAES | Descripción | Alícuota%)
  - Tablas con alícuota dual por tramo de facturación: 4 cols
      fila 1: encabezado de tramos (≤ umbral | > umbral)
      fila 2+: datos con dos tasas

Tramos de facturación en CABA (Ley 6927):
  - Umbral 1 (pequeños):  $ 364.000.000 anuales  (Art. 5 Anexo I)
  - Umbral 2 (grandes):   $2.004.000.000 anuales (Arts. 5-11 Anexo I y Art. 2)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

RAW_DIR = Path(__file__).parent / "raw"
HTML_FILE = RAW_DIR / "Capital Federal.html"

# Mapeo de índice de tabla HTML → metadatos normativos
# (tabla_idx, es_dual, umbral_M, articulo, norma_ref, descripcion_seccion)
_TABLE_MAP = [
    # idx  dual   umbral_M   articulo           norma_ref
    (2,   False, None,      "Art. 1",           "Ley Impositiva CABA 6927",   "Producción primaria y minera"),
    (4,   False, None,      "Art. 2",           "Ley Impositiva CABA 6927",   "Industria y manufactura"),
    (5,   True,  2004.0,    "Anexo I",          "Ley Impositiva CABA 6927",   "Electricidad, gas y agua"),
    (6,   False, None,      "Art. 4",           "Ley Impositiva CABA 6927",   "Construcción"),
    (7,   True,  364.0,     "Anexo I Art. 5",   "Ley Impositiva CABA 6927",   "Comercio y servicios - pequeños contribuyentes"),
    (8,   True,  2004.0,    "Anexo I Art. 6",   "Ley Impositiva CABA 6927",   "Grandes contribuyentes - actividades especiales"),
    (9,   False, None,      "Art. 7",           "Ley Impositiva CABA 6927",   "Transporte"),
    (10,  True,  2004.0,    "Art. 8",           "Ley Impositiva CABA 6927",   "Comunicaciones"),
    (11,  True,  2004.0,    "Art. 9",           "Ley Impositiva CABA 6927",   "Servicios generales"),
    (12,  True,  2004.0,    "Art. 10",          "Ley Impositiva CABA 6927",   "Servicios profesionales y veterinarios"),
    (13,  True,  2004.0,    "Art. 11",          "Ley Impositiva CABA 6927",   "Servicios ambientales y otros"),
]

# Tramos de facturación CABA para compatibilidad con TaxCalculator / escalas_volumen
_TRAMOS_CABA = [
    {"numero": 1, "limite_anual": 364_000_000,   "categoria": "Pequeño",  "modificador": 0},
    {"numero": 2, "limite_anual": 2_004_000_000,  "categoria": "Mediano",  "modificador": 0},
    {"numero": 3, "limite_anual": float("inf"),   "categoria": "Grande",   "modificador": 0},
]


def _parse_pct(val: str) -> float:
    """Convierte '3,00%' o '3.00%' a 3.0 (float)."""
    val = val.strip().replace("%", "").replace(",", ".")
    val = re.sub(r"[^\d\.]", "", val)
    try:
        return float(val)
    except ValueError:
        return 0.0


class NormativaLoader:
    """Carga y expone las normativas de la Ciudad Autónoma de Buenos Aires (CABA)."""

    def __init__(self, use_fixtures: bool = False):
        # CABA siempre parsea desde el HTML — no hay fixtures separados
        self._data: dict[str, Any] = {}
        self._loaded = False

    def load(self) -> None:
        if self._loaded:
            return
        self._load_from_html(HTML_FILE)
        self._loaded = True

    def _load_from_html(self, path: Path) -> None:
        """Parsea el HTML oficial de la Ley 6927 y construye la estructura interna."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            raise ImportError(
                "beautifulsoup4 no está instalado. Ejecutá: pip install beautifulsoup4"
            )

        print(f"[LOADER CABA] Cargando normativa desde {path.name}")
        html = path.read_text(encoding="utf-8", errors="ignore")
        soup = BeautifulSoup(html, "html.parser")
        all_tables = soup.find_all("table")

        actividades: list[dict] = []

        for (t_idx, es_dual, umbral_m, articulo, norma_ref, seccion) in _TABLE_MAP:
            if t_idx >= len(all_tables):
                print(f"[LOADER CABA] WARN: tabla índice {t_idx} no encontrada en el HTML.")
                continue

            table = all_tables[t_idx]
            rows = table.find_all("tr")

            if es_dual:
                # Fila 0: encabezado de columnas (Código NAES | Descripción | Alícuota)
                # Fila 1: sub-encabezado de tramos (≤ umbral | > umbral)
                # Fila 2+: datos con 4 celdas (naes, desc, alíc_baja, alíc_alta)
                data_rows = rows[2:]
                for row in data_rows:
                    cells = [td.get_text(strip=True) for td in row.find_all(["th", "td"])]
                    if len(cells) < 4:
                        continue
                    naes = re.sub(r"\D", "", cells[0])
                    if not naes or len(naes) < 5:
                        continue
                    desc = cells[1].strip()
                    alicuota_baja = _parse_pct(cells[2])   # tramo ≤ umbral
                    alicuota_alta = _parse_pct(cells[3])   # tramo > umbral

                    actividades.append({
                        "naes": naes,
                        "descripcion": desc,
                        "alicuota_base": alicuota_baja,       # tasa base (tramo bajo)
                        "tramos_reduccion": {
                            1: alicuota_baja,                 # ≤ umbral_M
                            2: alicuota_alta,                 # > umbral_M
                        },
                        "umbral_tramo_m": umbral_m,           # en millones
                        "norma_ref": norma_ref,
                        "articulo": articulo,
                        "seccion": seccion,
                        "notas": (
                            f"Tasa reducida para facturación ≤ ${umbral_m:,.0f} M: {alicuota_baja}%. "
                            f"Tasa estándar para facturación > ${umbral_m:,.0f} M: {alicuota_alta}%."
                        ) if umbral_m else "",
                    })
            else:
                # Fila 0: encabezado (Código NAES | Descripción | Alícuota)
                # Fila 1+: datos con 3 celdas
                data_rows = rows[1:]
                for row in data_rows:
                    cells = [td.get_text(strip=True) for td in row.find_all(["th", "td"])]
                    if len(cells) < 3:
                        continue
                    naes = re.sub(r"\D", "", cells[0])
                    if not naes or len(naes) < 5:
                        continue
                    desc = cells[1].strip()
                    alicuota = _parse_pct(cells[2])

                    actividades.append({
                        "naes": naes,
                        "descripcion": desc,
                        "alicuota_base": alicuota,
                        "tramos_reduccion": {1: alicuota},
                        "umbral_tramo_m": None,
                        "norma_ref": norma_ref,
                        "articulo": articulo,
                        "seccion": seccion,
                        "notas": "",
                    })

        print(f"[LOADER CABA] {len(actividades)} actividades cargadas.")
        self._data = {
            "actividades": actividades,
            "tramos_escala": _TRAMOS_CABA,
            "_meta": {
                "norma_base": "Ley Impositiva CABA 6927",
                "jurisdiccion": "Ciudad Autónoma de Buenos Aires",
                "fuente": "AGIP / Gobierno CABA",
            },
        }

    # ─── Interfaz pública (compatible con bsas/loader.py) ────────────────────

    def get_actividades(self) -> list[dict]:
        """Retorna la lista de actividades con sus alícuotas."""
        return self._data.get("actividades", [])

    def get_escalas_volumen(self) -> dict:
        """
        Retorna las escalas de modificación por volumen de ventas.
        Formato compatible con TaxCalculator.
        """
        tramos = self._data.get("tramos_escala", [])
        return {"categorias": tramos}

    def get_beneficios_especiales(self) -> list[dict]:
        """Retorna beneficios/exenciones especiales (CABA: Art. 1 tiene alícuota 0%)."""
        return [
            a for a in self.get_actividades() if a.get("alicuota_base", 1.0) == 0.0
        ]

    def get_meta(self) -> dict:
        """Retorna metadatos de la normativa."""
        return self._data.get("_meta", {})

    def get_all_as_text_chunks(self) -> list[dict]:
        """
        Convierte toda la normativa en chunks de texto para indexar en ChromaDB.
        Incluye tramos por facturación cuando aplica.
        """
        chunks = []

        for act in self.get_actividades():
            umbral = act.get("umbral_tramo_m")
            tramos = act.get("tramos_reduccion", {})

            if umbral and len(tramos) == 2:
                tramo_txt = (
                    f"Para facturación ≤ ${umbral:,.0f} M: {tramos.get(1, 0)}%. "
                    f"Para facturación > ${umbral:,.0f} M: {tramos.get(2, 0)}%."
                )
            else:
                tramo_txt = f"Alícuota única: {act['alicuota_base']}%."

            text = (
                f"Actividad NAES {act['naes']}: {act['descripcion']}. "
                f"Sección: {act.get('seccion', '')}. "
                f"{tramo_txt} "
                f"Norma: {act['norma_ref']}. "
                f"Artículo: {act['articulo']}. "
                f"Jurisdicción: Ciudad Autónoma de Buenos Aires (CABA)."
            )
            if act.get("notas"):
                text += f" Nota: {act['notas']}"

            chunks.append({
                "id": f"caba_naes_{act['naes']}",
                "text": text,
                "metadata": {
                    "provincia": "caba",
                    "tipo": "actividad",
                    "naes": act["naes"],
                    "alicuota_base": act["alicuota_base"],
                    "articulo": act["articulo"],
                    "norma_ref": act["norma_ref"],
                    "jurisdiccion": "caba",
                    "seccion": act.get("seccion", ""),
                },
            })

        # Chunks de tramos de facturación
        for t in _TRAMOS_CABA:
            limite = t["limite_anual"]
            limite_txt = f"${limite:,.0f}" if limite != float("inf") else "sin límite"
            text = (
                f"Escala de ingresos IIBB CABA - Tramo {t['numero']} ({t['categoria']}): "
                f"facturación anual hasta {limite_txt}. "
                f"Normativa: Ley Impositiva CABA 6927."
            )
            chunks.append({
                "id": f"caba_tramo_{t['numero']}",
                "text": text,
                "metadata": {
                    "provincia": "caba",
                    "tipo": "escala_volumen",
                    "tramo": t["numero"],
                    "limite": limite if limite != float("inf") else 9_999_999_999,
                },
            })

        # Chunk de contexto normativo general CABA
        chunks.append({
            "id": "caba_contexto_general",
            "text": (
                "Ciudad Autónoma de Buenos Aires (CABA) - Ingresos Brutos (IIBB). "
                "Ley Impositiva 6927. Administra AGIP (Administración Gubernamental de Ingresos Públicos). "
                "Tramos de facturación: Pequeños contribuyentes (≤ $364 M), "
                "Medianos (≤ $2.004 M), Grandes (> $2.004 M). "
                "Alícuotas van del 0% (producción primaria) al 5% (servicios generales grandes contribuyentes). "
                "Industria manufacturera: 1% (Art. 2). Construcción: 2% (Art. 4). Transporte: 2% (Art. 7)."
            ),
            "metadata": {
                "provincia": "caba",
                "tipo": "contexto_general",
                "norma_ref": "Ley Impositiva CABA 6927",
                "articulo": "General",
                "jurisdiccion": "caba",
            },
        })

        return chunks
