import asyncio
import hashlib
import json
import logging
import time
from enum import StrEnum
from typing import Optional

import fsspec

from src.visualiser_graph_generator import generate_graph, generate_output_path


logger = logging.getLogger(__name__)


class JobStatus(StrEnum):
    """Enumeration of possible job statuses."""

    ACCEPTED = "accepted"
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ALREADY_RUNNING = "already_running"


STATUS_ROOT = "s3://govuk-ai-accelerator-data-integration/graph_tools/job_statuses"


def get_status_metadata_path(job_id: str) -> str:
    """Returns the S3 path for a given job ID."""
    return f"{STATUS_ROOT}/{job_id}.json"


def update_job_status_metadata(job_id: str, status_metadata: dict):
    """Updates the job status in S3."""
    path = get_status_metadata_path(job_id)
    try:
        # Serialize to string first to ensure the JSON is valid before writing
        status_json = json.dumps(status_metadata, indent=4)
        with fsspec.open(path, "w") as f:
            f.write(status_json)
    except Exception as e:
        logger.error(f"Failed to update job status in S3 for job {job_id}: {str(e)}")


def read_job_status_metadata(job_id: str) -> dict | None:
    """Reads the job status from S3."""
    path = get_status_metadata_path(job_id)
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


def get_job_id_for_path(source_path: str) -> str:
    """Generates a predictable job_id based on a hash of the source_path."""
    return hashlib.sha256(source_path.encode()).hexdigest()


def get_active_job_status_metadata(job_id: str, timeout_hours: int = 24) -> Optional[dict]:
    """
    Returns the job status ONLY if it is currently active (pending/running)
    and has not exceeded the timeout. Returns None if the job is stale or not active.
    """
    status = read_job_status_metadata(job_id)
    if not status:
        return None

    if status.get("status") in [JobStatus.PENDING, JobStatus.RUNNING]:
        created_at = status.get("created_at", 0)
        is_stale = (time.time() - created_at) > (timeout_hours * 3600)

        if not is_stale:
            return status

    return None


async def background_run_extraction(
    job_id: str,
    input_path: str,
    output_path: str,
    status: dict,
    extractor_type: str = "s3",
    perform_indexing: bool = False,
):
    """Background task for graph generation and status tracking."""
    try:
        logger.info(
            f"Starting graph generation for {input_path} (Job: {job_id}, Type: {extractor_type})..."
        )
        status["status"] = JobStatus.RUNNING
        status["extractor_type"] = extractor_type
        status["perform_indexing"] = perform_indexing
        update_job_status_metadata(job_id, status)

        await generate_graph(
            input_path,
            output_path,
            extractor_type=extractor_type,
            perform_indexing=perform_indexing,
        )

        status["status"] = JobStatus.COMPLETED
        status["output_path"] = output_path
        status["completed_at"] = time.time()
        update_job_status_metadata(job_id, status)
        logger.info(f"Graph generation completed successfully for {output_path}")
    except Exception as e:
        logger.error(f"Background graph generation failed for job {job_id}: {str(e)}")
        status["status"] = JobStatus.FAILED
        status["error"] = str(e)
        update_job_status_metadata(job_id, status)


async def resume_interrupted_jobs():
    """Scans for jobs stuck in 'running' state and restarts them if they are fresh (<24h)."""
    logger.info("Scanning for interrupted jobs to resume...")
    fs = fsspec.filesystem("s3")

    try:
        # List all status files
        status_files = fs.glob(f"{STATUS_ROOT}/*.json")

        for file_path in status_files:
            job_id = file_path.split("/")[-1].replace(".json", "")
            status = read_job_status_metadata(job_id)

            if status and status.get("status") == JobStatus.RUNNING:
                created_at = status.get("created_at", 0)
                is_fresh = (time.time() - created_at) < (24 * 3600)

                if is_fresh:
                    source_path = status.get("source_path")
                    if source_path:
                        try:
                            input_path, output_path = generate_output_path(source_path)
                            logger.info(f"Resuming interrupted job {job_id} for {source_path}")
                            extractor_type = status.get("extractor_type", "s3")
                            perform_indexing = status.get("perform_indexing", False)
                            asyncio.create_task(
                                background_run_extraction(
                                    job_id,
                                    input_path,
                                    output_path,
                                    status,
                                    extractor_type=extractor_type,
                                    perform_indexing=perform_indexing,
                                )
                            )
                        except Exception as e:
                            logger.error(f"Failed to prepare resumption for job {job_id}: {str(e)}")
                else:
                    logger.info(f"Skipping stale interrupted job {job_id} (over 24h old)")
    except Exception as e:
        logger.error(f"Error during job resumption scan: {str(e)}")


async def start_extraction_job(
    source_path: str, extractor_type: str = "s3", perform_indexing: bool = False
) -> tuple[dict, int]:
    """
    Central logic for starting an extraction job.
    Returns a tuple of (response_metadata, status_code).
    """
    if not source_path:
        return {"error": "Missing 'source_path' query parameter"}, 400

    try:
        input_path, output_path = generate_output_path(source_path)

        # Use a distinct job ID for OpenSearch to avoid collisions with S3 sequential jobs
        path_for_id = source_path + "_os" if extractor_type == "opensearch" else source_path
        job_id = get_job_id_for_path(path_for_id)

        active_status = get_active_job_status_metadata(job_id)
        if active_status:
            logger.info(
                f"Duplicate request for {source_path}. Job {job_id} is already in progress."
            )
            return {
                "job_id": job_id,
                "status": JobStatus.ALREADY_RUNNING,
                "message": f"{extractor_type.upper()} job {job_id} is already in progress.",
                "output_path": output_path,
            }, 202

        initial_status = {
            "job_id": job_id,
            "status": JobStatus.PENDING,
            "source_path": source_path,
            "created_at": time.time(),
            "extractor_type": extractor_type,
            "perform_indexing": perform_indexing,
        }
        update_job_status_metadata(job_id, initial_status)

        asyncio.create_task(
            background_run_extraction(
                job_id,
                input_path,
                output_path,
                initial_status,
                extractor_type=extractor_type,
                perform_indexing=perform_indexing,
            )
        )

        return {
            "job_id": job_id,
            "status": JobStatus.ACCEPTED,
            "message": f"{extractor_type.upper()} graph generation started for {source_path}",
            "output_path": output_path,
        }, 202

    except Exception as e:
        logger.error(f"Error starting {extractor_type} background task: {str(e)}")
        return {"error": str(e)}, 500
