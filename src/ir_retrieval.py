"""
ir_retrieval.py
===============
Information Retrieval module – placeholder.
CSCE 5200 – Group 7

Planned implementation
----------------------
* BM25 sparse retrieval using ``rank-bm25`` (Robertson & Zaragoza, 2009).
* Dense semantic retrieval using ``sentence-transformers``
  (all-MiniLM-L6-v2 or similar).
* Hybrid re-ranking via Reciprocal Rank Fusion (RRF).

TODO: Implement BM25Index, DenseRetriever, and HybridRetriever classes.
"""

from __future__ import annotations

import pandas as pd


def build_bm25_index(df: pd.DataFrame):
    """Build a BM25 index from the preprocessed product DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain a ``product_name`` column (already cleaned).

    Returns
    -------
    object
        BM25Okapi instance (rank-bm25).  **Not yet implemented.**
    """
    raise NotImplementedError("BM25 index construction – coming in Sprint 2.")


def dense_retrieve(query: str, df: pd.DataFrame, top_k: int = 10):
    """Retrieve products using sentence-transformer embeddings.

    **Not yet implemented.**
    """
    raise NotImplementedError("Dense retrieval – coming in Sprint 2.")
