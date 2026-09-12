"""
Pre-warm Script for CivicLens
Pre-downloads local neural models into the local HuggingFace cache:
1. sentence-transformers/all-MiniLM-L6-v2 (Embedding vector model)
2. cross-encoder/nli-deberta-v3-base (Local NLI verification cross-encoder)
"""

import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("civiclens.prewarm")

def prewarm():
    logger.info("--- Starting Local Model Cache Pre-warm ---")
    
    try:
        logger.info("1/2: Downloading & caching 'sentence-transformers/all-MiniLM-L6-v2'...")
        from sentence_transformers import SentenceTransformer
        _ = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Successfully loaded & cached all-MiniLM-L6-v2.")
    except Exception as e:
        logger.warning(f"Failed to pre-warm all-MiniLM-L6-v2: {e}")

    try:
        logger.info("2/2: Downloading & caching 'cross-encoder/nli-deberta-v3-base'...")
        from sentence_transformers import CrossEncoder
        _ = CrossEncoder("cross-encoder/nli-deberta-v3-base")
        logger.info("Successfully loaded & cached cross-encoder/nli-deberta-v3-base.")
    except Exception as e:
        logger.warning(f"Failed to pre-warm cross-encoder/nli-deberta-v3-base: {e}")

    logger.info("--- Model Pre-warm Finished ---")

if __name__ == "__main__":
    prewarm()
