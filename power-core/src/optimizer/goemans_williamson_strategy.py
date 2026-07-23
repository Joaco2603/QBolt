"""SolverStrategy adapter for the Goemans-Williamson Max-Cut optimizer."""

from __future__ import annotations

from numbers import Integral
from typing import Mapping

from src.run_solver import SolverRunRequest, SolverRunResult

from .goemans_williamson import (
    DEFAULT_ROUNDS,
    DEFAULT_SOLVER,
    GoemansWilliamsonError,
    cut_weight,
    solve_goemans_williamson,
)


_ALLOWED_OPTIONS = frozenset({"rounds", "solver"})


class GoemansWilliamsonStrategy:
    """Normalize Goemans-Williamson execution for the shared solver runner."""

    id = "goemans-williamson"

    def solve(self, request: SolverRunRequest) -> SolverRunResult:
        """Execute one request and return a normalized, observable result."""

        options = dict(request.options)
        validation_error = self._validate_options(options)
        if validation_error is not None:
            return self._failed_result(
                request,
                code="invalid_options",
                message=validation_error,
            )

        rounds = options.get("rounds", DEFAULT_ROUNDS)
        solver = options.get("solver", DEFAULT_SOLVER)
        assert isinstance(rounds, Integral) and not isinstance(rounds, bool)
        assert isinstance(solver, str)

        try:
            optimizer_result = solve_goemans_williamson(
                request.graph,
                seed=request.seed,
                rounds=int(rounds),
                solver=solver,
            )
            partition = self._normalize_partition(
                request,
                optimizer_result.positive_partition,
                optimizer_result.negative_partition,
            )
            normalized_cut = cut_weight(
                request.graph,
                set(optimizer_result.positive_partition),
            )
        except GoemansWilliamsonError as error:
            return self._failed_result(
                request,
                code="solver_error",
                message=str(error),
                metadata={"rounds": int(rounds), "solver": solver},
            )

        return SolverRunResult(
            optimizer_id=self.id,
            status="succeeded",
            partition=partition,
            cut_value=normalized_cut,
            seed=request.seed,
            metadata={
                "rounds": optimizer_result.rounds,
                "winning_round": optimizer_result.winning_round,
                "solver": optimizer_result.solver,
                "solver_status": optimizer_result.solver_status,
                "solver_options": dict(optimizer_result.solver_options),
                "sdp_value": optimizer_result.sdp_value,
            },
        )

    @staticmethod
    def _validate_options(options: Mapping[str, object]) -> str | None:
        unknown = sorted(set(options) - _ALLOWED_OPTIONS)
        if unknown:
            return f"unknown Goemans-Williamson options: {', '.join(unknown)}"

        rounds = options.get("rounds", DEFAULT_ROUNDS)
        if (
            isinstance(rounds, bool)
            or not isinstance(rounds, Integral)
            or rounds <= 0
        ):
            return "rounds must be a positive integer"

        solver = options.get("solver", DEFAULT_SOLVER)
        if not isinstance(solver, str) or not solver.strip():
            return "solver must be a non-blank string"
        return None

    @staticmethod
    def _normalize_partition(
        request: SolverRunRequest,
        positive_partition: tuple[str, ...],
        negative_partition: tuple[str, ...],
    ) -> dict[str, int]:
        positive = set(positive_partition)
        negative = set(negative_partition)
        expected = set(request.graph.nodes)
        if positive & negative or positive | negative != expected:
            raise GoemansWilliamsonError(
                "optimizer returned incomplete or overlapping partitions"
            )
        return {
            node: 1 if node in positive else 0
            for node in request.graph.nodes
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
