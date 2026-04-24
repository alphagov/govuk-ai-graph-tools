from dataclasses import dataclass

from .base import BaseExtractorConfig, BaseQuoteExtractor


# --- Configuration ---


@dataclass
class OpenSearchConfig(BaseExtractorConfig):
    """Placeholder for OpenSearch specialized configuration."""

    index_name: str = "document_chunks"


class OpenSearchQuoteExtractor(BaseQuoteExtractor):
    # TODO: Implement OpenSearch-based retrieval and extraction flow once access has been sorted
    def __init__(self, config: OpenSearchConfig):
        super().__init__(config)
        self.config = config

    async def run(
        self, perform_indexing: bool = False, output_file: str = "outputs/extracted_quotes_os.json"
    ):
        return None
