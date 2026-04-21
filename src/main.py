"""
main.py
=======
Entry-point CLI for the IR & NLP-Based Price Formation System.
CSCE 5200 – Group 7

Usage
-----
    python -m src.main --query "cheapest jasmine rice" --budget 5.00
    python -m src.main --preprocess-only

TODO: Wire up the full pipeline (preprocessing → IR → NLP → recommender).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Local imports
from src.price_normalizer import build_pipeline

_RAW_DIR = Path(__file__).parent.parent / "data" / "raw"


def _collect_raw_csvs() -> list[str]:
    """Glob all CSVs from the raw data directory."""
    csvs = list(_RAW_DIR.glob("*.csv"))
    if not csvs:
        print(f"[ERROR] No CSV files found in {_RAW_DIR}.", file=sys.stderr)
        sys.exit(1)
    return [str(p) for p in csvs]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="IR & NLP-Based Price Formation System – CLI"
    )
    parser.add_argument(
        "--preprocess-only",
        action="store_true",
        help="Run only the preprocessing pipeline and exit.",
    )
    parser.add_argument("--query", type=str, default=None, help="Natural-language shopping query.")
    parser.add_argument("--budget", type=float, default=None, help="Maximum spend in USD.")
    parser.add_argument("--top-k", type=int, default=5, help="Number of results to return.")

    args = parser.parse_args(argv)

    # ── Preprocessing ───────────────────────────────────────────────────────
    filepaths = _collect_raw_csvs()
    df = build_pipeline(filepaths)

    if args.preprocess_only:
        print("Preprocessing complete.  Exiting.")
        return

    # ── Query Handling (Sprint 2+) ──────────────────────────────────────────
    if args.query is None:
        parser.print_help()
        return

    # TODO: integrate NLP + IR + recommender
    print(f"\nQuery: '{args.query}' – full recommendation engine coming in Sprint 2.")


if __name__ == "__main__":
    main()
