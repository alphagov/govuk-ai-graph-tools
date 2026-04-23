import fsspec
import json
import logging
import os
from typing import Dict, Any

logger = logging.getLogger(__name__)


def load_json_file(file_path: str) -> Dict[str, Any]:
    """Utility function to load JSON data from a file."""
    with fsspec.open(file_path, "r") as f:
        return json.load(f)


def load_graph(file_path: str) -> Dict[str, Any]:
    """Loads the graph viewmodel JSON for the frontend."""
    return load_json_file(file_path)
