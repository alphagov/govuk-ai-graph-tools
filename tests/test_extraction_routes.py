from unittest.mock import patch

import pytest

from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@patch("app.start_extraction_job")
def test_extract_route_success(mock_start_job, client):
    mock_start_job.return_value = ({"job_id": "test_job"}, 202)

    response = client.get("/extract?source_path=test/path")

    assert response.status_code == 202
    assert response.json == {"job_id": "test_job"}
    mock_start_job.assert_called_once_with("test/path", extractor_type="s3")


@patch("app.start_extraction_job")
def test_extract_os_route_success(mock_start_job, client):
    mock_start_job.return_value = ({"job_id": "test_job_os"}, 202)

    response = client.get("/extract-os?source_path=test/path&index=true")

    assert response.status_code == 202
    assert response.json == {"job_id": "test_job_os"}
    mock_start_job.assert_called_once_with(
        "test/path", extractor_type="opensearch", perform_indexing=True
    )


@patch("app.start_extraction_job")
def test_extract_route_missing_param(mock_start_job, client):
    mock_start_job.return_value = ({"error": "Missing 'source_path' query parameter"}, 400)

    response = client.get("/extract")

    assert response.status_code == 400
    assert "error" in response.json
