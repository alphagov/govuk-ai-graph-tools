# GOV.UK AI Graph Tools

A proof-of-concept tool for identifying duplicate and outlier content across GOV.UK at scale. The tool uses semantic similarity and vector search (Amazon OpenSearch) to surface content relationships and anomalies that would be impractical to detect through manual review.

Content is ingested from a knowledge graph built by the ontology generator, enabling content teams to prioritise quality improvements across large content estates. Outputs are surfaced through a graph visualiser with canonical node edges and alias search, designed for use by non-technical content professionals.

The tool also includes outlier detection, which filters entities or aliases that look unusual compared to the rest, helping content teams identify errors, inconsistencies, or gaps. For now, outlier types include imbalanced terms (where some aliases for an entity are used significantly less often than others) and near-identical terms (aliases with very similar wording that may indicate a misspelling or inconsistent usage).


![Example 01](images/example-01.png)


## Architecture

![Architecture diagram](images/architecture.png)

The tool is a Flask/Uvicorn web application deployed as a Docker container on AWS, built around four main layers.

**Ingestion and extraction**
A knowledge graph (JSON) maps entities to aliases and their source documents on S3. Two extraction strategies are available: an S3 sequential extractor (fetches and chunks documents directly) and an OpenSearch extractor (uses a pre-indexed vector search to retrieve targeted chunks). The OpenSearch extractor is used by default. Extracted chunks are sent to Anthropic Claude (via AWS Bedrock), which pulls relevant quotes directly from the source markdown files.

**Processing and storage**
Extraction runs as an async background job. Job status and output are persisted to S3. Once complete, the system generates a graph model — nodes, edges, and outlier metadata — saved as `graphNode.json`.

**Outlier detection**
Imbalanced aliases are surfaced using z-score analysis of alias occurrence counts. Near-identical aliases are detected by edit distance (Levenshtein distance) scoring.

**Visualisation**
Results are served through a set of HTML/JS views: an interactive Cytoscape graph, a React-based metrics dashboard, and dedicated outlier views for similar and imbalanced aliases. The UI uses GOV.UK Design System CSS classes wherever possible.

**Key technologies:** Python 3.12, Flask, Uvicorn, AWS Bedrock (Claude Sonnet), Amazon OpenSearch, AWS S3, Cytoscape.js, Pydantic, uv.


## Available API endpoints

All endpoints use `GET`.

| Endpoint | Parameters | Description |
|---|---|---|
| `GET /extract` | `source_path` | Start an extraction job using the S3 extractor. |
| `GET /extract-os` | `source_path`, `index` | Start an extraction job using the OpenSearch extractor. Set `index=true` to re-index before extracting. |
| `GET /status/<job_id>` | — | Get the status of a background job. |
| `GET /visualisations` | — | Browse all available visualisation outputs. |
| `GET /graph` | `run_path` | Interactive Cytoscape graph for a given run. |
| `GET /graph-viewmodel` | `run_path` | Raw graph data as JSON. |
| `GET /metrics` | `run_path` | Metrics dashboard for a given run. |
| `GET /outliers` | `run_path` | Select an outlier type to explore. |
| `GET /outliers/similar-aliases` | `run_path` | Aliases syntactically similar to others for the same entity. |
| `GET /outliers/imbalanced-aliases` | `run_path` | Aliases that occur significantly less often than others for the same entity. |
| `GET /` | — | Redirects to `/visualisations`. |
| `GET /healthcheck/ready` | — | Returns `200 Application OK`. |


## Use Cases

### Current

### Future


