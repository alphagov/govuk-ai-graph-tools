import asyncio
import logging
import os

from asgiref.wsgi import WsgiToAsgi
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import BadRequest

from src.utils import (
    read_job_status,
    resume_interrupted_jobs,
    start_extraction_job,
)
from src.visualiser_graph_loader import (
    extract_path_parts,
    load_json_file,
    visualiser_graph_file_path,
)


load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)

    @app.route("/graph", methods=["GET"])
    def graph_page():
        """Serve the Cytoscape graph viewer page."""
        source_path_param = request.args.get("source_path")

        # Validate the source_path format
        if source_path_param:
            extract_path_parts(source_path_param)

        return render_template("graph.html", source_path=source_path_param or "")

    @app.route("/graph-viewmodel", methods=["GET"])
    async def graph_viewmodel():
        """Serve the graph data as JSON for the frontend."""
        try:
            source_path_param = request.args.get("source_path")

            graph_filepath = visualiser_graph_file_path(source_path_param)

            graph_data = load_json_file(graph_filepath)

            logger.info("Graph data loaded successfully.")
            return jsonify(graph_data), 200
        except Exception as e:
            app.logger.error(f"Error loading graph data: {str(e)}")
            return jsonify({"error": "Error loading graph data."}), 500

    @app.route("/healthcheck/ready", methods=["GET"])
    def health_check():
        """Simple health check endpoint."""
        return "Application OK", 200

    @app.route("/extract", methods=["GET"])
    async def extract_quotes():
        """
        Endpoint that runs the Cytoscape graph generation logic based on graph.json.
        """
        source_path = request.args.get("source_path") or ""
        data, status_code = await start_extraction_job(source_path, extractor_type="s3")
        return jsonify(data), status_code

    @app.route("/extract-os", methods=["GET"])
    async def extract_quotes_os():
        """
        Endpoint that runs the extraction using OpenSearch.
        """
        source_path = request.args.get("source_path") or ""
        perform_indexing = request.args.get("index", "false").lower() == "true"
        data, status_code = await start_extraction_job(
            source_path, extractor_type="opensearch", perform_indexing=perform_indexing
        )
        return jsonify(data), status_code

    @app.route("/status/<job_id>", methods=["GET"])
    def get_status(job_id):
        """Check the status of a background job from S3."""
        status_info = read_job_status(job_id)
        if not status_info:
            return jsonify({"error": "Job ID not found"}), 404
        return jsonify(status_info), 200

    @app.errorhandler(BadRequest)
    def handle_bad_request(e):
        return jsonify({"error": e.description}), 400

    return app


class LifespanMiddleware:
    """ASGI middleware to handle startup and shutdown events."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    # Trigger resumption when the event loop is officially running
                    logger.info("ASGI startup: triggering job resumption scan...")
                    asyncio.create_task(resume_interrupted_jobs())
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
                    return
        return await self.app(scope, receive, send)


def create_asgi_app():
    flask_app = create_app()
    asgi_app = WsgiToAsgi(flask_app)
    return LifespanMiddleware(asgi_app)


if __name__ == "__main__":
    asgi_app = create_asgi_app()
    import uvicorn

    port = int(os.getenv("PORT", 3000))
    logger.info(f"Starting Uvicorn server on port {port}...")
    uvicorn.run(asgi_app, host="0.0.0.0", port=port)
