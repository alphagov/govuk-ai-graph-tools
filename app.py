import os
import logging
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from src.generate_graph import generate_graph, load_graph_viewmodel

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
            graph_data = load_graph_viewmodel("graph-viewmodel.json")
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
            logger.info('Starting graph generation process...')
            graph_data = await generate_graph("graph.json")
            logger.info('Graph generation completed successfully.')
            
            return jsonify(graph_data), 200

        except Exception as e:
            app.logger.error(f"Error generating graph: {str(e)}")
            return jsonify({"error": str(e)}), 500
            
    return app

if __name__ == "__main__":
    app = create_app()
    # Using Waitress as the production-ready WSGI server
    try:
        from waitress import serve
        port = int(os.getenv("PORT", 3000))
        logger.info(f"Starting Waitress server on port {port}...")
        serve(app, host='0.0.0.0', port=port)
    except ImportError:
        # Fallback to Flask dev server if waitress is not installed (e.g. local dev without it)
        port = int(os.getenv("PORT", 3000))
        logger.warning("Waitress not found, falling back to Flask development server.")
        app.run(host='0.0.0.0', port=port)
