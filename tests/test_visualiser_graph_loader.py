from unittest.mock import MagicMock, patch

import pytest
from werkzeug.exceptions import BadRequest

from src.visualiser_graph_loader import available_visualisations, visualiser_graph_file_path


class TestVisualiserGraphFilePath:
    def test_returns_s3_path_for_valid_run_path(self):
        result = visualiser_graph_file_path("my-domain/run-2025-001")

        assert (
            result
            == "s3://govuk-ai-accelerator-data-integration/graph_tools/my-domain/run-2025-001/graphNode.json"
        )

    def test_raises_bad_request_for_invalid_run_path_format(self):
        with pytest.raises(BadRequest):
            visualiser_graph_file_path("not-a-valid-path")


class TestAvailableVisualisations:
    """Tests for the available_visualisations function."""

    @patch("src.visualiser_graph_loader.fsspec.filesystem")
    def test_returns_list_of_visualisations(self, mock_filesystem):
        mock_fs = MagicMock()
        mock_filesystem.return_value = mock_fs

        # Mock the S3 directory structure:
        # - graph_tools/
        #   - domain-a/
        #     - run-2024-001/
        #   - domain-b/
        #     - run-2024-002/
        #     - run-2024-003/
        mock_fs.ls.side_effect = [
            [
                "govuk-ai-accelerator-data-integration/graph_tools/domain-a",
                "govuk-ai-accelerator-data-integration/graph_tools/domain-b",
            ],
            ["govuk-ai-accelerator-data-integration/graph_tools/domain-a/run-2024-001"],
            [
                "govuk-ai-accelerator-data-integration/graph_tools/domain-b/run-2024-002",
                "govuk-ai-accelerator-data-integration/graph_tools/domain-b/run-2024-003",
            ],
        ]

        result = available_visualisations()

        assert isinstance(result, list)
        assert len(result) == 3
        assert {"run_path": "domain-a/run-2024-001"} in result
        assert {"run_path": "domain-b/run-2024-002"} in result
        assert {"run_path": "domain-b/run-2024-003"} in result

    @patch("src.visualiser_graph_loader.fsspec.filesystem")
    def test_filters_out_non_run_directories(self, mock_filesystem):
        mock_fs = MagicMock()
        mock_filesystem.return_value = mock_fs

        mock_fs.ls.side_effect = [
            ["govuk-ai-accelerator-data-integration/graph_tools/domain-a"],
            [
                "govuk-ai-accelerator-data-integration/graph_tools/domain-a/run-2024-001",
                "govuk-ai-accelerator-data-integration/graph_tools/domain-a/temp",
                "govuk-ai-accelerator-data-integration/graph_tools/domain-a/output",
            ],
        ]

        result = available_visualisations()

        assert len(result) == 1
        assert result[0] == {"run_path": "domain-a/run-2024-001"}

    @patch("src.visualiser_graph_loader.fsspec.filesystem")
    def test_returns_empty_list_when_no_visualisations(self, mock_filesystem):
        mock_fs = MagicMock()
        mock_filesystem.return_value = mock_fs
        mock_fs.ls.return_value = []

        result = available_visualisations()

        assert result == []

    @patch("src.visualiser_graph_loader.fsspec.filesystem")
    def test_returns_empty_list_on_file_not_found_error(self, mock_filesystem):
        mock_fs = MagicMock()
        mock_filesystem.return_value = mock_fs
        mock_fs.ls.side_effect = FileNotFoundError("Bucket not found")

        result = available_visualisations()

        assert result == []

    @patch("src.visualiser_graph_loader.fsspec.filesystem")
    def test_handles_nested_directories_correctly(self, mock_filesystem):
        mock_fs = MagicMock()
        mock_filesystem.return_value = mock_fs

        mock_fs.ls.side_effect = [
            ["govuk-ai-accelerator-data-integration/graph_tools/my-domain"],
            ["govuk-ai-accelerator-data-integration/graph_tools/my-domain/run-2025-001"],
        ]

        result = available_visualisations()

        assert len(result) == 1
        assert result[0]["run_path"] == "my-domain/run-2025-001"
