"""
nlp_processor.py
================
NLP processing module – placeholder.
CSCE 5200 – Group 7

Planned implementation
----------------------
* spaCy-based entity extraction (product, brand, quantity, unit, store).
* Query expansion via WordNet synonyms and nutritional aliases.
* Query intent classification (cheapest / healthiest / store-specific).

TODO: Implement QueryParser, EntityExtractor, and QueryExpander classes.
"""

from __future__ import annotations


def parse_query(raw_query: str) -> dict:
    """Parse a natural-language shopping query into structured fields.

    Parameters
    ----------
    raw_query : str
        E.g. ``"cheapest jasmine rice under $5 at Walmart"``.

    Returns
    -------
    dict
        Structured representation with keys: product, store, budget,
        preference. **Not yet implemented.**
    """
    raise NotImplementedError("Query parsing – coming in Sprint 2.")


def expand_query(tokens: list[str]) -> list[str]:
    """Expand query tokens with synonyms and related terms.

    **Not yet implemented.**
    """
    raise NotImplementedError("Query expansion – coming in Sprint 2.")
