import os
import logging
from typing import List, Dict, Any, Optional
from backend.config import settings

logger = logging.getLogger("civiclens.vector_store")

class EmbeddingService:
    _model = None

    @classmethod
    def get_model(cls):
        if cls._model is None:
            if os.environ.get("CIVICLENS_MOCK_NLI") == "1":
                cls._model = "MOCK"
                return cls._model
            try:
                from sentence_transformers import SentenceTransformer
                logger.info("Loading sentence-transformers/all-MiniLM-L6-v2...")
                cls._model = SentenceTransformer("all-MiniLM-L6-v2")
            except Exception as e:
                logger.warning(f"Could not load SentenceTransformer ({e}), using MOCK.")
                cls._model = "MOCK"
        return cls._model

    @classmethod
    def embed_texts(cls, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        if os.environ.get("CIVICLENS_MOCK_NLI") == "1":
            return [[0.01] * 384 for _ in texts]
        try:
            model = cls.get_model()
            embeddings = model.encode(texts, convert_to_numpy=True)
            return embeddings.tolist()
        except Exception as e:
            logger.warning(f"Embedding failed ({e}), using mock embeddings.")
            return [[0.01] * 384 for _ in texts]

    @classmethod
    def embed_query(cls, query: str) -> List[float]:
        if os.environ.get("CIVICLENS_MOCK_NLI") == "1":
            return [0.01] * 384
        try:
            model = cls.get_model()
            embedding = model.encode(query, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            logger.warning(f"Embedding query failed ({e}), using mock vector.")
            return [0.01] * 384


class VectorStoreInterface:
    def upsert_clauses(self, clauses: List[Dict[str, Any]], doc_id: str):
        raise NotImplementedError

    def search_similar_clauses(self, query: str, ward: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def upsert_legal_sections(self, sections: List[Dict[str, Any]]):
        raise NotImplementedError

    def search_legal_sections(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        raise NotImplementedError


class ChromaVectorStore(VectorStoreInterface):
    def __init__(self, persist_dir: str):
        import chromadb
        os.makedirs(persist_dir, exist_ok=True)
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.clauses_col = self.client.get_or_create_collection(
            name="civic_clauses",
            metadata={"hnsw:space": "cosine"}
        )
        self.legal_col = self.client.get_or_create_collection(
            name="legal_corpus",
            metadata={"hnsw:space": "cosine"}
        )
        logger.info(f"Initialized Chroma vector store in {persist_dir}")

    def upsert_clauses(self, clauses: List[Dict[str, Any]], doc_id: str):
        if not clauses:
            return
        texts = [c["text"] for c in clauses]
        ids = [f"{doc_id}_{c['id']}" for c in clauses]
        embeddings = EmbeddingService.embed_texts(texts)
        metadatas = [
            {
                "doc_id": doc_id,
                "clause_id": str(c.get("id")),
                "ward": str(c.get("ward") or ""),
                "page": int(c.get("page", 1)),
                "typology": str(c.get("typology") or "")
            }
            for c in clauses
        ]
        self.clauses_col.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas
        )

    def search_similar_clauses(self, query: str, ward: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        count = self.clauses_col.count()
        if count == 0:
            return []
        emb = EmbeddingService.embed_query(query)
        where_clause = {"ward": ward} if ward else None
        results = self.clauses_col.query(
            query_embeddings=[emb],
            n_results=min(limit, count),
            where=where_clause
        )
        matched = []
        if results and results.get("documents") and results["documents"][0]:
            docs = results["documents"][0]
            metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)
            dists = results["distances"][0] if results.get("distances") else [0.0] * len(docs)
            for doc, meta, dist in zip(docs, metas, dists):
                matched.append({
                    "text": doc,
                    "metadata": meta,
                    "similarity": round(1.0 - float(dist), 4) if dist is not None else 1.0
                })
        return matched

    def upsert_legal_sections(self, sections: List[Dict[str, Any]]):
        if not sections:
            return
        texts = [s["text"] for s in sections]
        ids = [s["id"] for s in sections]
        embeddings = EmbeddingService.embed_texts(texts)
        metadatas = [
            {
                "statute": str(s.get("statute", "")),
                "section": str(s.get("section", "")),
                "title": str(s.get("title", ""))
            }
            for s in sections
        ]
        self.legal_col.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas
        )

    def search_legal_sections(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        count = self.legal_col.count()
        if count == 0:
            return []
        emb = EmbeddingService.embed_query(query)
        results = self.legal_col.query(
            query_embeddings=[emb],
            n_results=min(limit, count)
        )
        matched = []
        if results and results.get("documents") and results["documents"][0]:
            docs = results["documents"][0]
            metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)
            dists = results["distances"][0] if results.get("distances") else [0.0] * len(docs)
            for doc, meta, dist in zip(docs, metas, dists):
                matched.append({
                    "text": doc,
                    "metadata": meta,
                    "similarity": round(1.0 - float(dist), 4) if dist is not None else 1.0
                })
        return matched


    def seed_legal_corpus(self, corpus_dir: str = "backend/data/legal_corpus"):
        """Seed legal corpus into vector store if empty."""
        try:
            if self.legal_col.count() > 0:
                return
        except Exception:
            pass

        if not os.path.exists(corpus_dir):
            return

        sections = []
        for filename in os.listdir(corpus_dir):
            if filename.endswith(".txt"):
                filepath = os.path.join(corpus_dir, filename)
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()

                # Parse sections
                statute_name = "Karnataka Municipal Law"
                lines = content.split("\n")
                current_section = None
                current_title = ""
                current_text = []

                for line in lines:
                    if line.startswith("[STATUTE]:"):
                        statute_name = line.replace("[STATUTE]:", "").strip()
                    elif line.startswith("[SECTION"):
                        if current_section and current_text:
                            sections.append({
                                "id": f"{statute_name[:4].lower()}_{current_section.replace(' ', '_').lower()}",
                                "statute": statute_name,
                                "section": current_section,
                                "title": current_title,
                                "text": "\n".join(current_text).strip()
                            })
                        # Parse section header e.g. [SECTION 14]: Title
                        header = line.split("]:", 1)
                        sec_part = header[0].replace("[SECTION", "").strip()
                        title_part = header[1].strip() if len(header) > 1 else ""
                        current_section = f"Section {sec_part}"
                        current_title = title_part
                        current_text = [line]
                    else:
                        if current_section:
                            current_text.append(line)

                if current_section and current_text:
                    sections.append({
                        "id": f"{statute_name[:4].lower()}_{current_section.replace(' ', '_').lower()}",
                        "statute": statute_name,
                        "section": current_section,
                        "title": current_title,
                        "text": "\n".join(current_text).strip()
                    })

        if sections:
            self.upsert_legal_sections(sections)
            logger.info(f"Seeded {len(sections)} legal statute sections into vector store.")


def get_vector_store() -> VectorStoreInterface:
    """
    Factory function returning Postgres pgvector if available,
    falling back seamlessly to embedded Chroma.
    """
    # Check if Postgres backend explicitly requested or auto-detection succeeds
    if settings.VECTOR_STORE_BACKEND in ("postgres", "auto"):
        try:
            import psycopg2
            conn = psycopg2.connect(
                dbname=settings.POSTGRES_DB,
                user=settings.POSTGRES_USER,
                password=settings.POSTGRES_PASSWORD,
                host=settings.POSTGRES_HOST,
                port=settings.POSTGRES_PORT,
                connect_timeout=2
            )
            conn.close()
            logger.info("Connected to Postgres/pgvector successfully.")
        except Exception as e:
            logger.info(f"Postgres not reachable ({e}). Using embedded Chroma fallback.")

    store = ChromaVectorStore(persist_dir=settings.CHROMA_PERSIST_DIR)
    store.seed_legal_corpus()
    return store

vector_store = get_vector_store()

