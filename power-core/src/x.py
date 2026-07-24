import json
import networkx as nx

from optimizer.quantum import (
    IsingModel,
    LocalGuppySeleneBackend,
    NexusBackend,
    QAOA,
)
import qnexus as qnx

qnx.login()

project = qnx.projects.get_or_create(name="Quantum Power QAOA")
qnx.context.set_active_project(project)
if not qnx.quotas.check_quota(name="simulation"):
    raise RuntimeError("No simulation quota available")
from optimizer.quantum.index import build_max_cut_qubo

with open("../artifacts/regional_instance.json") as file:
    artifact = json.load(file)

graph = nx.Graph()
graph.add_nodes_from(node["id"] for node in artifact["nodes"])
graph.add_weighted_edges_from(
    (edge["source"], edge["target"], edge["weight"])
    for edge in artifact["edges"]
)

qubo = build_max_cut_qubo(graph)
ising = IsingModel.from_qubo(qubo)

backend = NexusBackend(
    qnx,
    project=project,
    timeout=3600,
    max_cost=10.0,
)

result = QAOA(layers=1, starts=5, seed=7,max_parallel_starts=5).run_cloud(
    ising,
    session=qnx,
    backend=backend,
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
