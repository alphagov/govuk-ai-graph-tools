import json
import logging
import fsspec

logger = logging.getLogger(__name__)

STATUS_ROOT = "s3://govuk-ai-accelerator-data-integration/graph_tools/job_statuses"

def get_status_path(job_id: str) -> str:
    """Returns the S3 path for a given job ID."""
    return f"{STATUS_ROOT}/{job_id}.json"

def update_job_status(job_id: str, status_data: dict):
    """Updates the job status in S3."""
    path = get_status_path(job_id)
    try:
        # Serialize to string first to ensure the JSON is valid before writing
        status_json = json.dumps(status_data, indent=4)
        with fsspec.open(path, "w") as f:
            f.write(status_json)
    except Exception as e:
        logger.error(f"Failed to update job status in S3 for job {job_id}: {str(e)}")

def read_job_status(job_id: str) -> dict:
    """Reads the job status from S3."""
    path = get_status_path(job_id)
    fs = fsspec.filesystem("s3")
    if not fs.exists(path):
        return None
    try:
        with fsspec.open(path, "r") as f:
            content = f.read()
            return json.loads(content)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse job status JSON from S3 for job {job_id}: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Failed to read job status from S3 for job {job_id}: {str(e)}")
        return None
