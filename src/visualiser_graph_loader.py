import json
import logging
import re
from typing import Any, Dict

import fsspec
from werkzeug.exceptions import BadRequest


logger = logging.getLogger(__name__)

ONTOLOGY_RUN_PATH_PATTERN = r"(?P<domain_name>[a-zA-Z0-9_-]+)/(?P<run_id>run-\d+-\d+)"
S3_BUCKET_NAME = "govuk-ai-accelerator-data-integration"
GRAPH_TOOLS_S3_PATH = f"{S3_BUCKET_NAME}/graph_tools/"


def load_json_file(file_path: str) -> Dict[str, Any]:
    with fsspec.open(file_path, "r") as f:
        return json.load(f)


def visualiser_graph_file_path(run_path: str | None) -> str:
    if run_path:
        domain_name, run_id = extract_path_parts(run_path)
        filename = f"s3://{GRAPH_TOOLS_S3_PATH}{domain_name}/{run_id}/graphNode.json"
        logger.info(f"Loading graph data from: '{filename}'")
    else:
        filename = "graph-viewmodel.json"
        logger.info("Loading default example graph data for viewmodel endpoint...")
    return filename


def visualisation_graph_data(run_path: str | None) -> Dict[str, Any]:
    graph_filepath = visualiser_graph_file_path(run_path)
    graph_data = load_json_file(graph_filepath)
    return graph_data


def extract_path_parts(path: str) -> tuple[str, str]:
    match = re.fullmatch(ONTOLOGY_RUN_PATH_PATTERN, path)
    if not match:
        logger.warning(f"Invalid run_path format: '{path}'")
        raise BadRequest(f"Invalid 'run_path' format: '{path}'")

    domain_name = match.group("domain_name")
    run_id = match.group("run_id")
    return domain_name, run_id


def available_visualisations():
    fs = fsspec.filesystem("s3")
    items = []

    try:
        domain_s3_paths = fs.ls(f"s3://{GRAPH_TOOLS_S3_PATH}", detail=False)

        for domain_s3_path in domain_s3_paths:
            domain_name = domain_s3_path[len(f"{GRAPH_TOOLS_S3_PATH}") :]

            run_s3_paths = fs.ls(f"s3://{GRAPH_TOOLS_S3_PATH}{domain_name}/", detail=False)

            for run_s3_path in run_s3_paths:
                run_id = run_s3_path[len(f"{GRAPH_TOOLS_S3_PATH}{domain_name}/") :]

                if not run_id.startswith("run-"):
                    continue

                run_path = f"{domain_name}/{run_id}"
                items.append({"run_path": run_path})
    except FileNotFoundError:
        logger.exception("Error listing visualisations from S3.")

    return items
