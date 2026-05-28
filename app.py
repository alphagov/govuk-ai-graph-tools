import asyncio
import logging
import os

from asgiref.wsgi import WsgiToAsgi
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, url_for
from werkzeug.exceptions import BadRequest

from src.utils import (
    read_job_status_metadata,
    resume_interrupted_jobs,
    start_extraction_job,
)
from src.utils.job_tracker import JobStatus, get_job_id_for_path
from src.visualiser_graph_loader import (
    available_visualisations,
    visualisation_graph_data,
)


load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)

    @app.route("/", methods=["GET"])
    def index():
        return redirect(url_for("visualisations_page"))

    @app.route("/graph", methods=["GET"])
    def graph_page():
        """Serve the Cytoscape graph viewer page."""
        run_path_param = request.args.get("run_path")
        if not run_path_param:
            return redirect(url_for("visualisations_page"))

        try:
            # Attempt to load the graph data to determine if it's available
            visualisation_graph_data(run_path_param)

            return render_template("graph.html", run_path=run_path_param)
        except Exception:
            logger.exception(f"Error loading graph data for '{run_path_param}'")

        job_id = get_job_id_for_path(run_path_param)
        logger.info(f"Checking job status for '{run_path_param}' with job ID '{job_id}'")

        job_status_metadata = read_job_status_metadata(job_id)

        if not job_status_metadata:
            error = f"No extraction job found for '{run_path_param}'."
        else:
            match job_status_metadata.get("status"):
                case JobStatus.PENDING | JobStatus.RUNNING:
                    error = f"Graph for '{run_path_param}' is not available yet."
                case _:
                    error = f"Graph for '{run_path_param}' failed to generate."

        return render_template("graph-unavailable.html", message=error, run_path=run_path_param)

    @app.route("/visualisations", methods=["GET"])
    def visualisations_page():
        """Serve a page listing all available visualisations."""
        return render_template("visualisations.html", visualisations=available_visualisations())

    @app.route("/metrics", methods=["GET"])
    def metrics_page():
        """Serve the React CDN sample metrics dashboard."""
        run_path_param = request.args.get("run_path")
        if not run_path_param:
            return redirect(url_for("visualisations_page"))
        return render_template("metrics.html", run_path=run_path_param)

    @app.route("/graph-viewmodel", methods=["GET"])
    async def graph_viewmodel():
        """Serve the graph data as JSON for the frontend."""
        try:
            run_path_param = request.args.get("run_path")
            if not run_path_param:
                return jsonify({"error": "Missing required parameter: run_path"}), 400

            graph_data = visualisation_graph_data(run_path_param)

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
        status_info = read_job_status_metadata(job_id)
        if not status_info:
            return jsonify({"error": "Job ID not found"}), 404
        return jsonify(status_info), 200

    @app.route("/outliers", methods=["GET"])
    def outliers_page():
        """View a page to select the type of outlier to display."""
        run_path_param = request.args.get("run_path")
        if not run_path_param:
            return redirect(url_for("visualisations_page"))

        return render_template("outliers.html", run_path=run_path_param)

    @app.route("/outliers/similar-aliases", methods=["GET"])
    def see_similar_aliases():
        """View aliases that are (syntactically) similar to other aliases of the same entity."""
        run_path_param = request.args.get("run_path")
        if not run_path_param:
            return redirect(url_for("visualisations_page"))

        return render_template("similar-aliases.html", run_path=run_path_param)

    @app.route("/outliers/imbalanced-aliases", methods=["GET"])
    def see_imbalanced_aliases():
        """View aliases with fewer occurrences relative to the total number of alias occurrences."""
        run_path_param = request.args.get("run_path")
        if not run_path_param:
            return redirect(url_for("visualisations_page"))

        return render_template("imbalanced-aliases.html", run_path=run_path_param)

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
