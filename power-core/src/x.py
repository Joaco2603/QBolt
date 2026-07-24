"""Small manual Nexus smoke runner retained for local debugging."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import networkx as nx


POWER_CORE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = POWER_CORE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def main() -> None:
    import qnexus as qnx
    from optimizer.quantum import IsingModel, NexusBackend, QAOA
    from optimizer.quantum.qubo import build_max_cut_qubo

    artifact_path = POWER_CORE_ROOT / "artifacts" / "regional_instance.json"
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    graph = nx.Graph()
    graph.add_nodes_from(node["id"] for node in artifact["nodes"])
    graph.add_weighted_edges_from(
        (edge["source"], edge["target"], edge["weight"])
        for edge in artifact["edges"]
    )

    qnx.login()
    project = qnx.projects.get_or_create(name="Quantum Power QAOA")
    qnx.context.set_active_project(project)
    if not qnx.quotas.check_quota(name="simulation"):
        raise RuntimeError("No simulation quota available")

    ising = IsingModel.from_qubo(build_max_cut_qubo(graph))
    result = QAOA(layers=1, starts=5, seed=7, max_parallel_starts=5).run_cloud(
        ising,
        session=qnx,
        backend=NexusBackend(qnx, project=project, timeout=3600, max_cost=10.0),
        shots=2,
    )
    print("Best bitstring:", result.bitstring)
    print("Spin assignment:", result.spins)
    print("Energy:", result.energy)
    print("Counts:", result.counts)
    print("Probabilities:", result.probabilities)
    print("Optimizer status:", result.optimizer_status)
    print("Optimizer success:", result.optimizer_success)
    print("Backend:", result.backend)


if __name__ == "__main__":
    main()
