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
