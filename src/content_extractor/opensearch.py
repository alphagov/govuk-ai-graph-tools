import asyncio
import hashlib
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Set

from opensearchpy import OpenSearch, RequestsHttpConnection, helpers
from requests_aws4auth import AWS4Auth

from src.url.generator import generate_url_fragement, s3_to_govuk_url

from .base import (
    BaseExtractorConfig,
    BaseQuoteExtractor,
    FinalQuoteExtraction,
    Finding,
)


logger = logging.getLogger(__name__)


# --- Configuration ---


@dataclass
class OpenSearchConfig(BaseExtractorConfig):
    """Configuration for OpenSearch specialized extraction."""

    endpoint: str = ""
    port: int = 443
    index_name: str = "document_chunks"
    text_field: str = "text"
    metadata_field: str = "metadata"
    s3_uri_field: str = "s3_uri"


class OpenSearchQuoteExtractor(BaseQuoteExtractor):
    """
    Processes documents by querying OpenSearch for relevant chunks
    and then extracting quotes using the Bedrock agent.
    """

    def __init__(self, config: OpenSearchConfig):
        super().__init__(config)
        self.config: OpenSearchConfig = config  # Explicitly type for mypy

        # Initialize OpenSearch client
        region = self.config.region

        auth = None
        if self.config.secret_id:
            logger.info(
                f"Fetching OpenSearch credentials from Secrets Manager: {self.config.secret_id}"
            )
            secret = self.get_aws_secret(self.config.secret_id)
            user = secret.get("username") or secret.get("OPENSEARCH_USER")
            pwd = secret.get("password") or secret.get("OPENSEARCH_PASSWORD")

            if user and pwd:
                auth = (user, pwd)
            else:
                logger.warning("Basic auth credentials (username/password) not found in Secret: ")

        if not auth:
            logger.info("Using IAM authentication for OpenSearch.")
            credentials = self.session.get_credentials()
            auth = AWS4Auth(
                credentials.access_key,
                credentials.secret_key,
                region,
                "es",
                session_token=credentials.token,
            )

        self.os_client = OpenSearch(
            hosts=[{"host": self.config.endpoint, "port": self.config.port}],
            http_auth=auth,
            use_ssl=True,
            verify_certs=False,
            connection_class=RequestsHttpConnection,
            timeout=30,
            retry_on_timeout=True,
            max_retries=3,
        )

    async def _search_chunks(self, keywords: List[str]) -> List[Dict[str, Any]]:
        """Queries OpenSearch for chunks matching any of the keywords."""
        if not keywords:
            return []

        # Construct a boolean query to find any of the keywords
        query = {
            "size": 100,  # Adjustable
            "query": {
                "bool": {
                    "should": [{"match_phrase": {self.config.text_field: kw}} for kw in keywords],
                    "minimum_should_match": 1,
                }
            },
        }

        try:
            logger.info(f"Searching OpenSearch index '{self.config.index_name}' for keywords...")
            response = self.os_client.search(index=self.config.index_name, body=query)
            hits = response["hits"]["hits"]
            logger.info(f"Found {len(hits)} matching chunks in OpenSearch.")
            return hits
        except Exception as e:
            logger.error(f"OpenSearch query failed: {e}")
            return []

    async def process_chunk(
        self, chunk_text: str, s3_uri: str, keywords: List[str], results_list: list
    ):
        """Processes a single retrieved chunk with the agent."""
        prompt = f"Keywords: {', '.join(keywords)}\n\nContent:\n{chunk_text}"

        base_govuk_url = s3_to_govuk_url(s3_uri, self.url_map)

        try:
            result = await self.agent.run(prompt)
            for q in result.output.quotes:
                results_list.append(
                    {
                        "content": q.content,
                        "keyword_matched": q.keyword_matched,
                        "source": s3_uri,
                        "link": generate_url_fragement(base_govuk_url, q.content),
                    }
                )
        except Exception as e:
            logger.error(f"Error processing chunk from {s3_uri}: {e}")

    async def index_documents(self):
        """
        Fetches documents from S3, chunks them, and uploads to OpenSearch.
        Uses deterministic IDs based on content hash to avoid duplicates.
        """

        if not self.config.s3_documents:
            logger.warning("No S3 documents specified for indexing.")
            return

        actions = []
        for s3_uri in self.config.s3_documents:
            logger.info(f"Indexing {s3_uri}...")
            content = self.fetch_s3_content(s3_uri)
            if not content:
                continue

            chunks = self.chunk_content(content)
            for chunk in chunks:
                id_string = f"{s3_uri}:{chunk}"
                chunk_id = hashlib.sha256(id_string.encode("utf-8")).hexdigest()

                action = {
                    "_index": self.config.index_name,
                    "_id": chunk_id,  # Use the hash as the document ID
                    "_source": {
                        self.config.text_field: chunk,
                        self.config.metadata_field: {
                            self.config.s3_uri_field: s3_uri,
                        },
                    },
                }
                actions.append(action)

        if actions:
            try:
                success, failed = helpers.bulk(self.os_client, actions)
                logger.info(f"Successfully indexed {success} chunks. Failed: {failed}")
                # Refresh the index to make docs searchable immediately
                self.os_client.indices.refresh(index=self.config.index_name)
            except Exception as e:
                logger.error(f"Bulk indexing failed: {e}")

    async def run(
        self, perform_indexing: bool = False, output_file: str = "outputs/extracted_quotes_os.json"
    ):
        """
        Main entry point. Optionally indexes documents, then queries OpenSearch
        and uses the agent to refine findings.
        """
        # 1. Optionally index documents from S3
        if perform_indexing:
            await self.index_documents()

        # 2. Search for relevant chunks
        hits = await self._search_chunks(self.config.keywords)
        if not hits:
            return FinalQuoteExtraction(root={})

        # 3. Extract S3 URIs to fetch URL map
        s3_uris = []
        for hit in hits:
            metadata = hit["_source"].get(self.config.metadata_field, {})
            s3_uri = metadata.get(self.config.s3_uri_field)
            if s3_uri:
                s3_uris.append(s3_uri)

        self._fetch_url_map(s3_uris)

        # 4. Process each hit with the agent
        raw_findings: List[Dict[str, Any]] = []
        tasks = []
        for hit in hits:
            source = hit["_source"]
            chunk_text = source.get(self.config.text_field, "")
            metadata = source.get(self.config.metadata_field, {})
            s3_uri = metadata.get(self.config.s3_uri_field, "unknown")

            if chunk_text:
                tasks.append(
                    self.process_chunk(chunk_text, s3_uri, self.config.keywords, raw_findings)
                )

        if tasks:
            await asyncio.gather(*tasks)

        # 5. Consolidate results
        keyword_map: Dict[str, Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))
        for f in raw_findings:
            keyword_map[f["keyword_matched"]][f["content"]].add(f["source"])

        final_data = {
            kw: [
                Finding(content=txt, source_documents=sorted(list(srcs)))
                for txt, srcs in content_map.items()
            ]
            for kw, content_map in keyword_map.items()
        }

        extraction = FinalQuoteExtraction(root=final_data)
        return extraction
