#!/usr/bin/env python3
"""Risk-based mutation testing gate for critical-tier modules (Chapter 9 & 22)."""

CRITICAL_TIER_TARGETS = (
    "src/crawler/package/validation/data_contract.py",
    "src/crawler/package/parser/",
    "src/crawler/package/ml/",
)


def evaluate_mutation_score(killed: int, total: int, min_score: float = 0.8) -> bool:
    """Evaluate aggregated mutation score against threshold (Chapter 24.5)."""
    if total <= 0:
        return False
    return (killed / total) >= min_score
