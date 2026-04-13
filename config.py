"""
config.py — Configuracion central del Agente IIBB
Carga variables de entorno y expone settings tipados al resto del sistema.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Forzar UTF-8 en stdout/stderr para Windows (evita UnicodeEncodeError con rich)
# Envuelto en try/except porque reconfigure() solo existe en TextIOWrapper,
# no en TextIO generico (ej: cuando stdout esta redirigido a un pipe).
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')  # type: ignore[union-attr]
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')  # type: ignore[union-attr]
except Exception:
    pass

# Carga el .env desde la raíz del proyecto
BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")


class LLMConfig:
    backend: str = os.getenv("LLM_BACKEND", "openai")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3")


class EmbeddingsConfig:
    backend: str = os.getenv("EMBEDDINGS_BACKEND", "local")
    # Modelo local de sentence-transformers (multilingüe, funciona bien en español)
    local_model: str = "paraphrase-multilingual-MiniLM-L12-v2"


class PathsConfig:
    base: Path = BASE_DIR
    normativas: Path = BASE_DIR / "normativas"
    chroma_db: Path = BASE_DIR / "normativas" / ".chromadb"
    cases_db: Path = BASE_DIR / "memory" / "cases_db.json"
    data: Path = BASE_DIR / "data"


class DatabaseConfig:
    # Por defecto usa SQLite local, pero permite sobrescribir via env para Azure SQL
    uri: str = os.getenv("DATABASE_URI", f"sqlite:///{BASE_DIR}/data/auditoria_v5.db")


class AgentConfig:
    provincia_activa: str = os.getenv("PROVINCIA_ACTIVA", "bsas")
    use_fixtures: bool = os.getenv("USE_FIXTURES", "True").lower() == "true"
    verbose_chain: bool = os.getenv("VERBOSE_CHAIN", "True").lower() == "true"
    # Cuántos casos previos del historial mostrar como referencia
    max_history_references: int = 3
    # Cuántos chunks RAG recuperar por búsqueda
    rag_top_k: int = 5


# Instancias globales importables
llm_cfg = LLMConfig()
emb_cfg = EmbeddingsConfig()
paths_cfg = PathsConfig()
agent_cfg = AgentConfig()
db_cfg = DatabaseConfig()
