"""
core/rag_engine.py — Motor RAG para normativas fiscales

Indexa los artículos de la normativa en ChromaDB usando embeddings
multilingual y permite búsqueda semántica por actividad/alícuota.
"""

from __future__ import annotations

import chromadb
from chromadb.config import Settings
from rich.console import Console

from config import agent_cfg, emb_cfg, paths_cfg

console = Console()


def _get_embedding_function():
    """Factory para la función de embeddings (local o OpenAI)."""
    if emb_cfg.backend == "local":
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        return SentenceTransformerEmbeddingFunction(model_name=emb_cfg.local_model)
    else:
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
        from config import llm_cfg
        return OpenAIEmbeddingFunction(
            api_key=llm_cfg.openai_api_key,
            model_name="text-embedding-3-small"
        )


class RAGEngine:
    """
    Motor de recuperación semántica sobre normativas provinciales.
    
    Uso:
        engine = RAGEngine(provincia="bsas")
        engine.initialize()
        resultados = engine.search("venta minorista de ropa", top_k=5)
    """

    def __init__(self, provincia: str | None = None):
        self.provincia = provincia or agent_cfg.provincia_activa
        self._client: chromadb.ClientAPI | None = None
        self._collection: chromadb.Collection | None = None
        self._initialized = False

    def initialize(self, force_reindex: bool = False) -> None:
        """Inicializa ChromaDB y carga/crea el índice de normativas."""
        # Asegurar que el directorio existe
        paths_cfg.chroma_db.mkdir(parents=True, exist_ok=True)

        embedding_fn = _get_embedding_function()

        self._client = chromadb.PersistentClient(
            path=str(paths_cfg.chroma_db),
            settings=Settings(anonymized_telemetry=False)
        )

        collection_name = f"normativas_{self.provincia}"

        # Verificar si ya existe el índice
        existing = [c.name for c in self._client.list_collections()]

        if collection_name in existing and not force_reindex:
            self._collection = self._client.get_collection(
                name=collection_name,
                embedding_function=embedding_fn
            )
            count = self._collection.count()
            # Si el indice existe pero esta vacio (fallo previo), re-indexar
            if count == 0:
                self._client.delete_collection(collection_name)
                self._collection = self._client.create_collection(
                    name=collection_name,
                    embedding_function=embedding_fn,
                    metadata={"hnsw:space": "cosine"}
                )
                self._index_normativas()
            elif agent_cfg.verbose_chain:
                console.print(
                    f"[dim]RAG: Indice '{collection_name}' cargado ({count} documentos)[/dim]"
                )
        else:
            if collection_name in existing:
                self._client.delete_collection(collection_name)
            self._collection = self._client.create_collection(
                name=collection_name,
                embedding_function=embedding_fn,
                metadata={"hnsw:space": "cosine"}
            )
            self._index_normativas()

        self._initialized = True

    def _index_normativas(self) -> None:
        """Carga y indexa las normativas de la provincia activa."""
        console.print(f"[yellow]RAG: Indexando normativas de {self.provincia.upper()}...[/yellow]")

        loader = self._get_loader()
        loader.load()
        chunks = loader.get_all_as_text_chunks()

        if not chunks:
            console.print("[red]WARN RAG: No se encontraron chunks para indexar.[/red]")
            return

        ids = [c["id"] for c in chunks]
        texts = [c["text"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]

        # Convertir todos los valores de metadata a strings/números (ChromaDB requirement)
        for meta in metadatas:
            for k, v in meta.items():
                if not isinstance(v, (str, int, float, bool)):
                    meta[k] = str(v)

        self._collection.add(documents=texts, ids=ids, metadatas=metadatas)
        console.print(f"[green]RAG: {len(chunks)} fragmentos indexados correctamente.[/green]")

    def _get_loader(self):
        """Retorna el loader correcto según la provincia activa."""
        if self.provincia == "bsas":
            from normativas.bsas.loader import NormativaLoader
            return NormativaLoader(use_fixtures=agent_cfg.use_fixtures)
        else:
            raise NotImplementedError(
                f"Provincia '{self.provincia}' no soportada aún. "
                f"Hito 2+ cubrirá más jurisdicciones."
            )

    def search(
        self,
        query: str,
        top_k: int | None = None,
        tipo_filter: str | None = None,
    ) -> list[dict]:
        """
        Búsqueda semántica en la normativa indexada.
        
        Args:
            query: Descripción natural de la actividad o consulta fiscal.
            top_k: Número de resultados a retornar.
            tipo_filter: Filtrar por tipo de documento ("actividad", "escala_volumen", "beneficio").
        
        Returns:
            Lista de chunks relevantes con texto, metadata y score de distancia.
        """
        if not self._initialized:
            raise RuntimeError("RAGEngine no inicializado. Llamar a .initialize() primero.")

        total = self._collection.count()
        if total == 0:
            return []

        k = top_k or agent_cfg.rag_top_k
        n = min(k, total)

        where = {"provincia": self.provincia}
        if tipo_filter:
            # ChromaDB requiere operador $and para multiples filtros
            where = {"$and": [{"provincia": self.provincia}, {"tipo": tipo_filter}]}

        results = self._collection.query(
            query_texts=[query],
            n_results=n,
            where=where,
            include=["documents", "metadatas", "distances"]
        )

        chunks = []
        if results["documents"] and results["documents"][0]:
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0]
            ):
                chunks.append({
                    "text": doc,
                    "metadata": meta,
                    "relevance_score": round(1 - dist, 4)  # Convertir distancia coseno a similitud
                })

        return chunks

    def search_as_context(
        self,
        query: str,
        top_k: int | None = None,
        tipo_filter: str | None = None,
    ) -> str:
        """
        Retorna los resultados de búsqueda formateados como texto de contexto
        para incluir en el prompt del LLM.
        """
        chunks = self.search(query, top_k=top_k, tipo_filter=tipo_filter)
        if not chunks:
            return "No se encontraron fragmentos normativos relevantes."

        lines = []
        for i, chunk in enumerate(chunks, 1):
            score = chunk["relevance_score"]
            meta = chunk["metadata"]
            lines.append(
                f"[Fragmento {i}] (Relevancia: {score:.0%})\n"
                f"{chunk['text']}\n"
                f"[Fuente: {meta.get('norma_ref', 'N/A')} | "
                f"Artículo: {meta.get('articulo', 'N/A')}]"
            )

        return "\n\n".join(lines)
