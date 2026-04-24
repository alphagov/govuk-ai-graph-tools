import fsspec
import json
import logging
import os
import re
from typing import Dict, Any
from werkzeug.exceptions import BadRequest

logger = logging.getLogger(__name__)

ONTOLOGY_RUN_PATH_PATTERN = r'(?P<domain_name>[a-zA-Z0-9_-]+)/(?P<run>run-\d+-\d+)'
S3_BUCKET_NAME = "govuk-ai-accelerator-data-integration"
GRAPH_TOOLS_PATH_S3 = f"{S3_BUCKET_NAME}/graph_tools/"

def load_json_file(file_path: str) -> Dict[str, Any]:
    with fsspec.open(file_path, "r") as f:
        return json.load(f)

def visualiser_graph_file_path(source_path: str | None) -> str:
    if source_path:
        domain_name, run_id = extract_path_parts(source_path)
        filename = f"s3://{GRAPH_TOOLS_PATH_S3}{domain_name}/{run_id}/graphNode.json"
        logger.info(f"Loading graph data from: '{filename}'")
    else:
        filename = "graph-viewmodel.json"
        logger.info('Loading default example graph data for viewmodel endpoint...')
    return filename

def extract_path_parts(path: str) -> tuple[str, str]:
    match = re.fullmatch(ONTOLOGY_RUN_PATH_PATTERN, path)
    if not match:
        logger.warning(f"Invalid 'source_path' format: '{path}'")
        raise BadRequest(f"Invalid 'source_path' format: '{path}'")

    domain_name = match.group('domain_name')
    run_id = match.group('run')
    return domain_name, run_id

def available_visualisations():
    fs = fsspec.filesystem("s3")
    items = []

    try:
        domain_paths = fs.ls(f"s3://{GRAPH_TOOLS_PATH_S3}", detail=False)

        for domain_path in domain_paths:
            domain_name = domain_path[len(f"{GRAPH_TOOLS_PATH_S3}"):]

            run_paths = fs.ls(f"s3://{GRAPH_TOOLS_PATH_S3}{domain_name}/", detail=False)

            for run_path in run_paths:
                run_id = run_path[len(f"{GRAPH_TOOLS_PATH_S3}{domain_name}/"):]

                if not run_id.startswith("run-"):
                    continue

                source_path = f"{domain_name}/{run_id}"
                items.append({"source_path": source_path})
    except FileNotFoundError as e:
        logger.exception(f"Error listing visualisations from S3.")

    return items
