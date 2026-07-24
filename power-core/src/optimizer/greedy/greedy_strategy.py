"""SolverStrategy adapter for the greedy weighted Max-Cut baseline."""

from __future__ import annotations

from typing import Mapping

from src.run_solver import SolverRunRequest, SolverRunResult

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


_ALLOWED_OPTIONS: frozenset[str] = frozenset()


class GreedyStrategy:
    """Normalize greedy execution for the shared solver runner."""

    id = "greedy"

    def solve(self, request: SolverRunRequest) -> SolverRunResult:
        """Execute one request and return a normalized, observable result."""

        options = dict(request.options)
        unknown = sorted(set(options) - _ALLOWED_OPTIONS)
        if unknown:
            return self._failed_result(
                request,
                code="invalid_options",
                message=f"unknown greedy options: {', '.join(unknown)}",
            )

        try:
            optimizer_result = solve_greedy(request.graph, seed=request.seed)
            partition = self._normalize_partition(request, optimizer_result)
            normalized_cut = cut_value(
                request.graph,
                set(optimizer_result.partition_zero),
            )
        except GreedyError as error:
            return self._failed_result(
                request,
                code="solver_error",
                message=str(error),
                metadata=self._base_metadata(),
            )

        metadata = self._base_metadata()
        metadata.update(
            {
                "node_order": optimizer_result.node_order,
                "total_edge_weight": optimizer_result.total_edge_weight,
            }
        )
        return SolverRunResult(
            optimizer_id=self.id,
            status="succeeded",
            partition=partition,
            cut_value=normalized_cut,
            seed=request.seed,
            metadata=metadata,
        )

    @staticmethod
    def _normalize_partition(
        request: SolverRunRequest,
        result: GreedyResult,
    ) -> dict[str, int]:
        zero = set(result.partition_zero)
        one = set(result.partition_one)
        expected = set(request.graph.nodes)
        if zero & one or zero | one != expected:
            raise GreedyError("optimizer returned incomplete or overlapping partitions")
        return {node: 0 if node in zero else 1 for node in request.graph.nodes}

    @staticmethod
    def _base_metadata() -> dict[str, object]:
        return {
            "algorithm": ALGORITHM,
            "algorithm_version": ALGORITHM_VERSION,
            "approximation_guarantee": APPROXIMATION_GUARANTEE,
            "ordering_policy": ORDERING_POLICY,
            "tie_break_policy": TIE_BREAK_POLICY,
        }

    @classmethod
    def _failed_result(
        cls,
        request: SolverRunRequest,
        *,
        code: str,
        message: str,
        metadata: Mapping[str, object] | None = None,
    ) -> SolverRunResult:
        return SolverRunResult(
            optimizer_id=cls.id,
            status="failed",
            partition=None,
            cut_value=None,
            seed=request.seed,
            metadata={} if metadata is None else metadata,
            error={"code": code, "message": message},
        )
