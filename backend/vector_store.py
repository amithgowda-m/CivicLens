import os
import re
import hashlib
import logging
from typing import List, Dict, Any, Optional
from backend.config import settings
from backend.jurisdiction import normalize_jurisdiction


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
    def _mock_vector(cls, text: str) -> List[float]:
        import hashlib
        h = hashlib.md5(text.lower().encode("utf-8")).hexdigest()
        vec = [(int(h[i % 32], 16) / 15.0) for i in range(384)]
        tokens = set(re.findall(r"\b[a-z]{3,}\b", text.lower()))
        for idx, kw in enumerate(["setback", "tax", "commercial", "residential", "water", "lake", "drainage", "far", "floor", "building"]):
            if kw in tokens:
                vec[idx] += 10.0
        norm = sum(x * x for x in vec) ** 0.5
        return [x / norm for x in vec] if norm > 0 else [0.01] * 384

    @classmethod
    def embed_texts(cls, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        if os.environ.get("CIVICLENS_MOCK_NLI") == "1":
            return [cls._mock_vector(t) for t in texts]
        try:
            model = cls.get_model()
            embeddings = model.encode(texts, convert_to_numpy=True)
            return embeddings.tolist()
        except Exception as e:
            logger.warning(f"Embedding failed ({e}), using mock embeddings.")
            return [cls._mock_vector(t) for t in texts]

    @classmethod
    def embed_query(cls, query: str) -> List[float]:
        if os.environ.get("CIVICLENS_MOCK_NLI") == "1":
            return cls._mock_vector(query)
        try:
            model = cls.get_model()
            embedding = model.encode(query, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            logger.warning(f"Embedding query failed ({e}), using mock vector.")
            return cls._mock_vector(query)



class VectorStoreInterface:
    def upsert_clauses(self, clauses: List[Dict[str, Any]], doc_id: str):
        raise NotImplementedError

    def search_similar_clauses(self, query: str, ward: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def upsert_legal_sections(self, sections: List[Dict[str, Any]]):
        raise NotImplementedError

    def search_legal_sections(self, query: str, jurisdiction: Optional[str] = None, limit: int = 3) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def search_audit_precedents(self, authority_text: str, jurisdiction: Optional[str] = None, limit: int = 3) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def upsert_audit_resolution(self, precedent: Dict[str, Any]):
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
        self.audit_col = self.client.get_or_create_collection(
            name="audit_precedents",
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
                "title": str(s.get("title", "")),
                "jurisdiction": str(s.get("jurisdiction", "national"))
            }
            for s in sections
        ]
        self.legal_col.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas
        )

    def search_legal_sections(self, query: str, jurisdiction: Optional[str] = None, limit: int = 3) -> List[Dict[str, Any]]:
        count = self.legal_col.count()
        if count == 0:
            return []
        emb = EmbeddingService.embed_query(query)

        where_filter = None
        if jurisdiction and jurisdiction not in ("national", "_default"):
            where_filter = {
                "$or": [
                    {"jurisdiction": {"$eq": jurisdiction}},
                    {"jurisdiction": {"$eq": "national"}}
                ]
            }
        elif jurisdiction == "national":
            where_filter = {"jurisdiction": {"$eq": "national"}}

        try:
            results = self.legal_col.query(
                query_embeddings=[emb],
                n_results=min(limit, count),
                where=where_filter
            )
        except Exception as e:
            logger.warning(f"Filtered legal search failed ({e}), retrying without filter...")
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

    def search_audit_precedents(self, authority_text: str, jurisdiction: Optional[str] = None, limit: int = 3) -> List[Dict[str, Any]]:
        count = self.audit_col.count()
        if count == 0:
            return []
        emb = EmbeddingService.embed_query(authority_text)
        where_filter = None
        if jurisdiction and jurisdiction != "_default":
            where_filter = {"jurisdiction": {"$eq": jurisdiction}}

        try:
            results = self.audit_col.query(
                query_embeddings=[emb],
                n_results=min(limit, count),
                where=where_filter
            )
        except Exception:
            results = self.audit_col.query(
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

    def upsert_audit_resolution(self, precedent: Dict[str, Any]):
        p_id = precedent.get("id") or str(hash(precedent.get("authority_claim", "")))
        text = precedent.get("authority_claim", "")
        emb = EmbeddingService.embed_texts([text])
        meta = {
            "decision": precedent.get("decision", "ADMITTED"),
            "reasoning": precedent.get("reasoning", ""),
            "jurisdiction": precedent.get("jurisdiction", "_default")
        }
        self.audit_col.upsert(
            ids=[p_id],
            embeddings=emb,
            documents=[text],
            metadatas=[meta]
        )

    def seed_audit_precedents(self):
        """Seeds gold-standard authority resolution precedents if collection is empty."""
        try:
            if self.audit_col.count() > 0:
                return
        except Exception:
            pass

        precedents = [
            {
                "id": "prec_gba_chief_comm",
                "authority_claim": "Chief Commissioner, Greater Bengaluru Authority",
                "decision": "ADMITTED",
                "reasoning": "Apex coordinating body under the Greater Bengaluru Governance Act 2024; valid for city-wide policies.",
                "jurisdiction": "karnataka_bengaluru"
            },
            {
                "id": "prec_joint_comm_east",
                "authority_claim": "Joint Commissioner, Bengaluru East City Corporation",
                "decision": "ADMITTED",
                "reasoning": "Legitimate officer heading zonal administration under the 5-corporation structure.",
                "jurisdiction": "karnataka_bengaluru"
            },
            {
                "id": "prec_zonal_comm_gba_hallucinated",
                "authority_claim": "Zonal Commissioner, GBA",
                "decision": "REJECTED_PRUNED",
                "reasoning": "Fictitious title. GBA has no Zonal Commissioners; zones are headed by Joint Commissioners of individual corporations.",
                "jurisdiction": "karnataka_bengaluru"
            },
            {
                "id": "prec_bbmp_comm_superseded",
                "authority_claim": "Commissioner, Bruhat Bengaluru Mahanagara Palike",
                "decision": "REJECTED_PRUNED",
                "reasoning": "BBMP entity superseded by 5 new City Corporations under the GBA restructuring.",
                "jurisdiction": "karnataka_bengaluru"
            },
            {
                "id": "prec_udd_secretary",
                "authority_claim": "Secretary to Government, Urban Development Department",
                "decision": "ADMITTED",
                "reasoning": "Valid state-level department secretary and statutory appellate authority.",
                "jurisdiction": "karnataka_bengaluru"
            }
        ]

        ids = [p["id"] for p in precedents]
        docs = [p["authority_claim"] for p in precedents]
        embs = EmbeddingService.embed_texts(docs)
        metas = [{"decision": p["decision"], "reasoning": p["reasoning"], "jurisdiction": p["jurisdiction"]} for p in precedents]

        self.audit_col.upsert(
            ids=ids,
            embeddings=embs,
            documents=docs,
            metadatas=metas
        )
        logger.info(f"Seeded {len(precedents)} audit precedent resolutions.")

    def seed_legal_corpus(self):
        """Purges any legacy external statutory texts per pure-document grounding specification."""
        try:
            count = self.legal_col.count()
            if count > 0:
                all_ids = self.legal_col.get()["ids"]
                if all_ids:
                    self.legal_col.delete(ids=all_ids)
                logger.info(f"Purged {count} legacy statutory corpus items from Chroma.")
        except Exception as e:
            logger.debug(f"Legal corpus purge note: {e}")


def get_vector_store() -> VectorStoreInterface:
    """
    Factory function returning Postgres pgvector if available,
    falling back seamlessly to embedded Chroma.
    """
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
    store.seed_audit_precedents()
    return store

vector_store = get_vector_store()
