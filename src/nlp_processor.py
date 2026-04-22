"""
nlp_processor.py
----------------
Natural Language Processing module — placeholder for Sprint 2.
CSCE 5200 - Group 7

What we plan to add here:
  - spaCy-based entity extraction (product, brand, quantity, unit, store)
  - Query expansion using WordNet synonyms and nutritional aliases
  - Query intent classification (cheapest / healthiest / store-specific)

These functions are stubbed out below so the rest of the pipeline can import
this module without errors. Full implementations are coming in Sprint 2.
"""

from __future__ import annotations


def parse_query(raw_query: str) -> dict:
    """Parse a natural-language shopping query into structured fields.

    Parameters
    ----------
    raw_query : str
        e.g. "cheapest jasmine rice under $5 at Walmart"

    Returns
    -------
    dict
        Structured fields: product, store, budget, preference.
        Not yet implemented — coming in Sprint 2.
    """
    raise NotImplementedError(
        "Query parsing is not implemented yet — coming in Sprint 2."
    )


def expand_query(tokens: list[str]) -> list[str]:
    """Expand query tokens with synonyms and related terms.

    Not yet implemented — coming in Sprint 2.
    """
    raise NotImplementedError(
        "Query expansion is not implemented yet — coming in Sprint 2."
    )
