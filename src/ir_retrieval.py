"""
ir_retrieval.py
---------------
Information Retrieval module — placeholder for Sprint 2.
CSCE 5200 - Group 7

What we plan to add here:
  - BM25 sparse retrieval using rank-bm25 (Robertson & Zaragoza, 2009)
  - Dense semantic retrieval using sentence-transformers (all-MiniLM-L6-v2)
  - Hybrid re-ranking via Reciprocal Rank Fusion (RRF)

These classes are stubbed out below so the rest of the pipeline can import
this module without errors. Full implementations are coming in Sprint 2.
"""

from __future__ import annotations

import pandas as pd


def build_bm25_index(df: pd.DataFrame):
    """Build a BM25 index from the preprocessed product DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain a product_name column (already cleaned).

    Returns
    -------
    object
        BM25Okapi instance (rank-bm25). Not yet implemented.
    """
    raise NotImplementedError(
        "BM25 index construction is not implemented yet — coming in Sprint 2."
    )


def dense_retrieve(query: str, df: pd.DataFrame, top_k: int = 10):
    """Retrieve products using sentence-transformer embeddings.

    Not yet implemented — coming in Sprint 2.
    """
    raise NotImplementedError(
        "Dense retrieval using sentence-transformers is not implemented yet — coming in Sprint 2."
    )
