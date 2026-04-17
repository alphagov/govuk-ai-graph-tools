# FROM --platform=linux/arm64/v8 python:3.13-slim-bookworm AS base
FROM python:3.13-slim-bookworm AS base

ENV GOVUK_APP_NAME=GOVUK-AI-GRAPH-TOOLS
ENV UV_CACHE_DIR=/tmp/.uv_cache
# ARG GITHUB_TOKEN

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    libcurl4 \
    curl \
    pandoc \
    git \
    && apt-get -y clean && \
    rm -rf /var/lib/apt/lists/* /tmp/*

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY requirements.txt .

COPY requirements.txt .
RUN uv pip install --system -r requirements.txt

RUN rm -rf /root/.cache/uv

COPY . .

EXPOSE 8080

CMD ["waitress-serve", "--host=0.0.0.0", "--port=3000", "--call", "govuk_ai_graph_tools_app:create_app"]