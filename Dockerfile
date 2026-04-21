# Use a slim Python image
FROM python:3.13-slim


RUN pip install uv

ENV UV_CACHE_DIR=/tmp/.uv_cache



WORKDIR /app
COPY pyproject.toml uv.lock ./


RUN uv sync --no-dev --no-install-project

COPY src/ ./src/
COPY static/ ./static/
COPY templates/ ./templates/
COPY graph-viewmodel.json ./graph-viewmodel.json
COPY app.py ./app.py
# COPY graph.json ./

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PORT=3000

# Expose the port
EXPOSE 3000

# Use waitress-serve to serve the Flask app
CMD ["waitress-serve", "--host=0.0.0.0", "--port=3000", "--call", "app:create_app"]
