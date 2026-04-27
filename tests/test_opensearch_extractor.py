from unittest.mock import MagicMock, patch

import pytest

from src.content_extractor.base import AgentQuote, AgentQuoteExtraction
from src.content_extractor.opensearch import OpenSearchConfig, OpenSearchQuoteExtractor


@pytest.fixture
def mock_config():
    return OpenSearchConfig(
        keywords=["test keyword"],
        s3_documents=[],
        endpoint="search-test-domain.eu-west-2.es.amazonaws.com",
        index_name="test_index",
    )


@pytest.mark.asyncio
async def test_opensearch_extractor_full_flow(mock_config):
    # Mock OpenSearch client, Bedrock Agent, and boto3 Session
    with (
        patch("src.content_extractor.opensearch.OpenSearch") as mock_os_class,
        patch("src.content_extractor.opensearch.boto3.Session") as mock_session_class,
        patch("src.content_extractor.opensearch.helpers.bulk") as mock_bulk,
        patch("src.content_extractor.base.BedrockConverseModel"),
        patch("src.content_extractor.base.Agent") as mock_agent_class,
    ):
        mock_session = mock_session_class.return_value
        mock_credentials = MagicMock()
        mock_credentials.access_key = "access"
        mock_credentials.secret_key = "secret"
        mock_credentials.token = "token"
        mock_session.get_credentials.return_value = mock_credentials

        mock_os_client = mock_os_class.return_value
        mock_agent = mock_agent_class.return_value

        # Mock Bulk indexing
        mock_bulk.return_value = (1, [])

        # Mock OpenSearch response
        mock_os_client.search.return_value = {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "text": "This is a test sentence with test keyword.",
                            "metadata": {"s3_uri": "s3://bucket/doc1.md"},
                        }
                    }
                ]
            }
        }

        # Mock Agent response
        from unittest.mock import AsyncMock

        mock_agent.run = AsyncMock(
            return_value=MagicMock(
                output=AgentQuoteExtraction(
                    quotes=[
                        AgentQuote(
                            content="This is a test sentence with test keyword.",
                            keyword_matched="test keyword",
                        )
                    ]
                )
            )
        )

        extractor = OpenSearchQuoteExtractor(mock_config)
        extractor.config.s3_documents = ["s3://bucket/doc1.md"]

        # Mock fetch_s3_content and chunk_content using patch.object to satisfy mypy
        with (
            patch.object(extractor, "fetch_s3_content", return_value="Some content."),
            patch.object(extractor, "chunk_content", return_value=["Some content."]),
        ):
            results = await extractor.run(perform_indexing=True)

        # Verify indexing was called
        mock_bulk.assert_called_once()

        assert "test keyword" in results.root
        assert len(results.root["test keyword"]) == 1
        assert (
            results.root["test keyword"][0].content == "This is a test sentence with test keyword."
        )
        assert results.root["test keyword"][0].source_documents == ["s3://bucket/doc1.md"]
