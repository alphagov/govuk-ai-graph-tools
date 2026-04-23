import json
import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def load_json_file(file_path: str) -> Dict[str, Any]:
    """Utility function to load JSON data from a file."""
    if not os.path.exists(file_path):
        logger.error(f"File {file_path} not found.")
        return {}
    with open(file_path, "r") as f:
        return json.load(f)


def load_graph(file_path: str) -> Dict[str, Any]:
    """Loads the graph viewmodel JSON for the frontend."""
    return load_json_file(file_path)
