import os

from src.models.graph_models import GraphInput
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
