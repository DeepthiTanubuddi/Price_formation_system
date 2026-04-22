"""
recommender.py
--------------
Price-aware recommendation module — placeholder for Sprint 3.
CSCE 5200 - Group 7

What we plan to add here:
  - Unit-price ranking across stores for the same product
  - Budget-constrained basket optimization (greedy + dynamic programming)
  - Nutritional score weighting (Food Processing Score from GroceryDB)
  - Cross-store deal detection and alert generation

These functions are stubbed out below so the rest of the pipeline can import
this module without errors. Full implementations are coming in Sprint 3.
"""

from __future__ import annotations

import pandas as pd


def rank_by_unit_price(
    df: pd.DataFrame,
    product_query: str,
    top_k: int = 5,
) -> pd.DataFrame:
    """Return the cheapest matches for a product query, ranked by unit price.

    Not yet implemented — coming in Sprint 3.
    """
    raise NotImplementedError(
        "Unit-price ranking is not implemented yet — coming in Sprint 3."
    )


def optimise_basket(
    shopping_list: list[str],
    df: pd.DataFrame,
    budget: float | None = None,
) -> pd.DataFrame:
    """Return the optimal multi-store basket for a given shopping list.

    Not yet implemented — coming in Sprint 3.
    """
    raise NotImplementedError(
        "Basket optimization is not implemented yet — coming in Sprint 3."
    )
