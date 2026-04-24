import asyncio
import fsspec
import json
import logging
import os
import re
import time
import uuid
from asgiref.wsgi import WsgiToAsgi
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template
from src.visualiser_graph_generator import generate_graph, generate_output_path
from src.visualiser_graph_loader import load_json_file, extract_path_parts, visualiser_graph_file_path
from src.utils import (
    update_job_status, 
    read_job_status, 
    get_job_id_for_path,
    get_active_job_status,
    background_run_extraction,
    resume_interrupted_jobs
)
from werkzeug.exceptions import BadRequest


load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)

    @app.route('/graph', methods=['GET'])
    def graph_page():
        """Serve the Cytoscape graph viewer page."""
        source_path_param = request.args.get('source_path')

        # Validate the source_path format
        if source_path_param:
            extract_path_parts(source_path_param)

        return render_template('graph.html', source_path=source_path_param or '')

    @app.route('/visualisations', methods=['GET'])
    def visualisations_page():
        """Serve a page listing all available visualisations."""
        visualisations = [
            {"source_path": "test-visa-5/run-20260420-2"},
            {"source_path": "fake-domain/run-7891-2"}
        ]
        return render_template('visualisations.html', visualisations=visualisations)

    @app.route('/graph-viewmodel', methods=['GET'])
    async def graph_viewmodel():
        """Serve the graph data as JSON for the frontend."""
        try:
            source_path_param = request.args.get('source_path')
            
            graph_filepath = visualiser_graph_file_path(source_path_param)

            graph_data = load_json_file(graph_filepath)

            logger.info('Graph data loaded successfully.')
            return jsonify(graph_data), 200
        except Exception as e:
            app.logger.error(f"Error loading graph data: {str(e)}")
            return jsonify({"error": "Error loading graph data."}), 500

    @app.route('/healthcheck/ready', methods=['GET'])
    def health_check():
        """Simple health check endpoint."""
        return "Application OK", 200

    @app.route('/extract', methods=['GET'])
    async def extract_quotes():
        """
        Endpoint that runs the Cytoscape graph generation logic based on graph.json.
        """
        try:
            source_path = request.args.get('source_path')
            if not source_path:
                return jsonify({"error": "Missing 'source_path' query parameter"}), 400

            input_path, output_path = generate_output_path(source_path)
            job_id = get_job_id_for_path(source_path)
            
            active_status = get_active_job_status(job_id)
            if active_status:
                logger.info(f"Duplicate request for {source_path}. Job {job_id} is already in progress.")
                return jsonify({
                    'job_id': job_id,
                    'status': 'already_running',
                    'message': f'A graph generation job is already in progress for {source_path}',
                    'output_path': output_path
                }), 202

            initial_status = {
                "job_id": job_id,
                "status": "pending",
                "source_path": source_path,
                "created_at": time.time()
            }
            update_job_status(job_id, initial_status)

            asyncio.create_task(background_run_extraction(job_id, input_path, output_path, initial_status))

            return jsonify({
                'job_id': job_id,
                'status': 'accepted',
                'message': f'Graph generation started in background for {source_path}',
                'output_path': output_path
            }), 202

        except Exception as e:
            app.logger.error(f"Error starting background task: {str(e)}")
            return jsonify({"error": str(e)}), 500

    @app.route('/status/<job_id>', methods=['GET'])
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
    uvicorn.run(asgi_app, host='0.0.0.0', port=port)
