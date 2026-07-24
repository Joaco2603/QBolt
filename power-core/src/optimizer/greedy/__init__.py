"""Greedy approximation baseline for weighted Max-Cut."""

from .greedy import (
    ALGORITHM,
    ALGORITHM_VERSION,
    APPROXIMATION_GUARANTEE,
    ORDERING_POLICY,
    TIE_BREAK_POLICY,
    GreedyError,
    GreedyResult,
    cut_value,
    solve_greedy,
)
from .greedy_strategy import GreedyStrategy

__all__ = [
    "ALGORITHM",
    "ALGORITHM_VERSION",
    "APPROXIMATION_GUARANTEE",
    "GreedyError",
    "GreedyResult",
    "GreedyStrategy",
    "ORDERING_POLICY",
    "TIE_BREAK_POLICY",
    "cut_value",
    "solve_greedy",
]
