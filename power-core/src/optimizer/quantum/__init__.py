"""Quantum optimization primitives and backend adapters."""

from .ising import IsingModel
from .iceberg import (
    IcebergCompileConfig,
    IcebergCompiledProgram,
    IcebergCompiler,
    IcebergOperation,
    IcebergValidationError,
    PostselectionResult,
    postselect_counts,
)
from .qaoa import (
    LocalGuppySeleneBackend,
    MeasurementBatch,
    NexusBackend,
    QAOA,
    QAOABackend,
    QAOAProgram,
    QAOAResult,
)
from .qubo import (
    ConstraintBuilder,
    QuboModel,
    build_max_cut_qubo,
    cut_weight,
    recommended_penalty,
)
__all__ = [
    "ConstraintBuilder",
    "IcebergCompileConfig",
    "IcebergCompiledProgram",
    "IcebergCompiler",
    "IcebergOperation",
    "IcebergValidationError",
    "IsingModel",
    "LocalGuppySeleneBackend",
    "MeasurementBatch",
    "NexusBackend",
    "QAOA",
    "QAOABackend",
    "QAOAProgram",
    "QAOAResult",
    "QuboModel",
    "PostselectionResult",
    "build_max_cut_qubo",
    "cut_weight",
    "recommended_penalty",
    "postselect_counts",
]
