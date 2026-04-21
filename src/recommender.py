"""
recommender.py
==============
Price-aware recommendation module – placeholder.
CSCE 5200 – Group 7

Planned implementation
----------------------
* Unit-price ranking across stores for the same product.
* Budget-constrained basket optimisation (greedy + dynamic programming).
* Nutritional score weighting (Food Processing Score from GroceryDB).
* Cross-store deal detection and alert generation.

TODO: Implement PriceRanker, BasketOptimiser, and DealDetector classes.
"""

from __future__ import annotations

import pandas as pd


def rank_by_unit_price(
    df: pd.DataFrame,
    product_query: str,
    top_k: int = 5,
) -> pd.DataFrame:
    """Return the cheapest matches for a product query, ranked by unit price.

    **Not yet implemented.**
    """
    raise NotImplementedError("Price ranking – coming in Sprint 3.")


def optimise_basket(
    shopping_list: list[str],
    df: pd.DataFrame,
    budget: float | None = None,
) -> pd.DataFrame:
    """Return the optimal multi-store basket for a given shopping list.

    **Not yet implemented.**
    """
    raise NotImplementedError("Basket optimisation – coming in Sprint 3.")
