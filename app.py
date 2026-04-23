import os
import logging
import asyncio
import uuid
import json
import time
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from src.visualiser_graph_generator import generate_graph, generate_output_path
from src.visualiser_graph_loader import load_graph
import fsspec
from asgiref.wsgi import WsgiToAsgi
from src.utils import update_job_status, read_job_status


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
        return render_template('graph.html')

    @app.route('/graph-viewmodel', methods=['GET'])
    async def graph_viewmodel():
        """Serve the graph data as JSON for the frontend."""
        try:
            logger.info('Loading graph data for viewmodel endpoint...')
            graph_data = load_graph("graph-viewmodel.json")
            logger.info('Graph data loaded successfully.')
            return jsonify(graph_data), 200
        except Exception as e:
            app.logger.error(f"Error loading graph data: {str(e)}")
            return jsonify({"error": str(e)}), 500

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
            job_id = str(uuid.uuid4())
            
            initial_status = {
                "job_id": job_id,
                "status": "pending",
                "source_path": source_path,
                "created_at": time.time()
            }
            update_job_status(job_id, initial_status)

            async def run_extraction():
                try:
                    logger.info(f'Starting background graph generation for {input_path} (Job: {job_id})...')
                    initial_status["status"] = "running"
                    update_job_status(job_id, initial_status)
                    
                    await generate_graph(input_path, output_path)
                    
                    initial_status["status"] = "completed"
                    initial_status["output_path"] = output_path
                    initial_status["completed_at"] = time.time()
                    update_job_status(job_id, initial_status)
                    logger.info(f'Graph generation completed successfully for {output_path}')
                except Exception as e:
                    logger.error(f"Background graph generation failed for job {job_id}: {str(e)}")
                    initial_status["status"] = "failed"
                    initial_status["error"] = str(e)
                    update_job_status(job_id, initial_status)

            asyncio.create_task(run_extraction())

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

    return app

def create_asgi_app():
    return WsgiToAsgi(create_app())

if __name__ == "__main__":
    asgi_app = create_asgi_app()
    import uvicorn
    port = int(os.getenv("PORT", 3000))
    logger.info(f"Starting Uvicorn server on port {port}...")
    uvicorn.run(asgi_app, host='0.0.0.0', port=port)
