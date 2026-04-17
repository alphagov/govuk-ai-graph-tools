import os
import logging
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from src.generate_graph import generate_graph

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
