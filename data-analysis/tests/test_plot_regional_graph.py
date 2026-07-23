import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "plot_regional_graph.py"
SPEC = importlib.util.spec_from_file_location("plot_regional_graph", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_build_graph_preserves_qubo_instance_topology():
    instance = MODULE.load_instance(
        Path(__file__).parents[2] / "power-core" / "artifacts" / "regional_instance.json"
    )

    graph = MODULE.build_graph(instance)

    assert graph.number_of_nodes() == 6
    assert graph.number_of_edges() == 5
    assert graph["SUB-01"]["SUB-07"]["weight"] == 230.0


def test_plot_graph_writes_png(tmp_path):
    instance = MODULE.load_instance(
        Path(__file__).parents[2] / "power-core" / "artifacts" / "regional_instance.json"
    )
    output = tmp_path / "regional_graph.png"

    MODULE.plot_graph(instance, output)

    assert output.exists()
    assert output.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
