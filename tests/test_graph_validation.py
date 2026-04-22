import pytest
from src.models.graph_models import GraphInput, GraphOutput
from src.visualiser_graph_generator import slugify

def test_graph_input_validation():
    data = {
        "entities": [
            {
                "id": "e1",
                "canonical_key": "test_entity",
                "label": "Test Entity",
                "aliases": [{"name": "alias1"}, {"name": "alias2"}],
                "properties": {"sourceUrls": "s3://bucket/key"}
            }
        ]
    }
    validated = GraphInput.model_validate(data)
    assert len(validated.entities) == 1
    assert validated.entities[0].id == "e1"

def test_graph_input_invalid():
    data = {
        "entities": [
            {
                "id": "e1",
                # missing canonical_key
                "label": "Test Entity"
            }
        ]
    }
    with pytest.raises(Exception):
        GraphInput.model_validate(data)

def test_slugify():
    assert slugify("Hello World!") == "hello_world"
    assert slugify("Test-123") == "test_123"

def test_graph_output_validation():
    data = {
        "nodes": [
            {
                "data": {
                    "id": "e1",
                    "label": "Entity 1",
                    "type": "entity"
                }
            }
        ],
        "edges": [
            {
                "data": {
                    "source": "e1",
                    "target": "a1",
                    "label": "Alias"
                }
            }
        ]
    }
    validated = GraphOutput.model_validate(data)
    assert len(validated.nodes) == 1
    assert validated.nodes[0].data.id == "e1"
