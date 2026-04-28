import os
from collections import defaultdict

from src.models.graph_models import GraphInput
from src.visualiser_graph_generator import build_node_structure
from src.visualiser_graph_loader import load_json_file, visualiser_graph_file_path

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "test-domain-01", "run-01-1", "graph.json"
)


def test_load_json_file_from_local_fixture():
    data = load_json_file(FIXTURE_PATH)

    assert "domain" in data
    assert "schema_version" in data
    assert "entities" in data
    assert data["domain"] == "test-domain-01"


def test_fixture_is_valid_graph_input():
    data = load_json_file(FIXTURE_PATH)

    graph = GraphInput.model_validate(data)

    assert len(graph.entities) > 0


def test_fixture_relationships_are_loaded_with_type():
    data = load_json_file(FIXTURE_PATH)

    graph = GraphInput.model_validate(data)

    assert len(graph.relationships) > 0
    assert all(r.type for r in graph.relationships)


def test_visualiser_graph_file_path_constructs_s3_url():
    path = visualiser_graph_file_path("test-domain-01/run-01-1")

    assert path == "s3://govuk-ai-accelerator-data-integration/graph_tools/test-domain-01/run-01-1/graphNode.json"


def test_local_fixture_loads_independently_of_s3_path():
    data = load_json_file(FIXTURE_PATH)

    assert data is not None
    assert isinstance(data, dict)


def test_graph_output_relationships_contain_required_fields():
    data = load_json_file(FIXTURE_PATH)
    graph = GraphInput.model_validate(data)
    empty_results = defaultdict(lambda: defaultdict(list))

    output = build_node_structure(graph.entities, empty_results, graph.relationships)
    dumped = output.model_dump(exclude_none=True)

    assert len(dumped["relationships"]) > 0
    for rel in dumped["relationships"]:
        assert "type" in rel
        assert "from_" in rel
        assert "to" in rel


def test_relationship_edges_reference_existing_nodes():
    data = load_json_file(FIXTURE_PATH)
    graph = GraphInput.model_validate(data)
    empty_results = defaultdict(lambda: defaultdict(list))

    output = build_node_structure(graph.entities, empty_results, graph.relationships)
    dumped = output.model_dump(exclude_none=True)

    node_ids = {n["data"]["id"] for n in dumped["nodes"]}
    relationship_edges = [e for e in dumped["edges"] if e["data"].get("edge_type") == "relationship"]

    assert len(relationship_edges) > 0
    for edge in relationship_edges:
        assert edge["data"]["source"] in node_ids, f"source {edge['data']['source']} not in nodes"
        assert edge["data"]["target"] in node_ids, f"target {edge['data']['target']} not in nodes"
