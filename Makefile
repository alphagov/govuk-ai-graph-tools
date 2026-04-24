# Variables
IMAGE_NAME = extractor-agent
PORT = 3000

.PHONY: build run stop clean test start shell logs lint format lint-fix typecheck install-hooks

# Pre-commit hooks
install-hooks:
	uv run pre-commit install

# Linting and Formatting
lint:
	uv run ruff check .

format:
	uv run ruff format .

lint-fix:
	uv run ruff check --fix .
	uv run ruff format .

typecheck:
	uv run mypy .

# Build and run the container
start: build run

# View container logs
logs:
	@docker logs $$(docker ps -q --filter ancestor=$(IMAGE_NAME)) 2>/dev/null || echo "No running containers found"

# Enter the container shell
shell: build
	docker run -it \
	  -e AWS_REGION \
	  -e AWS_DEFAULT_REGION \
	  -e AWS_ACCESS_KEY_ID \
	  -e AWS_SECRET_ACCESS_KEY \
	  -e AWS_SESSION_TOKEN \
	  $(IMAGE_NAME) /bin/sh

# Build the Docker image
build:
	docker build -t $(IMAGE_NAME) .

run:
	@if [ -f .env ]; then \
		docker run -p $(PORT):$(PORT) \
		  -e AWS_REGION \
		  -e AWS_DEFAULT_REGION \
		  -e AWS_ACCESS_KEY_ID \
		  -e AWS_SECRET_ACCESS_KEY \
		  -e AWS_SESSION_TOKEN \
		  --env-file .env $(IMAGE_NAME); \
	else \
		docker run -p $(PORT):$(PORT) \
		  -e AWS_REGION \
		  -e AWS_DEFAULT_REGION \
		  -e AWS_ACCESS_KEY_ID \
		  -e AWS_SECRET_ACCESS_KEY \
		  -e AWS_SESSION_TOKEN \
		  $(IMAGE_NAME); \
	fi

# Stop the running container≈
stop:
	@docker stop $$(docker ps -q --filter ancestor=$(IMAGE_NAME)) 2>/dev/null || echo "No containers found to stop"

# Clean up Docker images and containers
clean:
	@docker rm -f $$(docker ps -aq --filter ancestor=$(IMAGE_NAME)) 2>/dev/null || true
	@docker rmi $(IMAGE_NAME) 2>/dev/null || true
