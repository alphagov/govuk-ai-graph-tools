import asyncio
import logging
from typing import List
from collections import defaultdict
from .base import BaseQuoteExtractor, Finding, FinalQuoteExtraction, BaseExtractorConfig
from src.url.generator import generate_url_fragement, s3_to_govuk_url

logger = logging.getLogger(__name__)


class S3QuoteExtractor(BaseQuoteExtractor):
    """Processes documents sequentially by fetching from S3 and chunking."""
    
    async def process_document(self, s3_uri: str, keywords: List[str], results_list: list):
        """Processes a single document for a specific set of keywords."""
        content = self.fetch_s3_content(s3_uri)
        if not content: return

        chunks = self.chunk_content(content)
        if len(chunks) > 1:
            logger.info(f"  Split {s3_uri} into {len(chunks)} chunks.")

        for i, chunk in enumerate(chunks, 1):
            prompt = (
                f"Keywords: {', '.join(keywords)}\n\n"
                f"Content (Chunk {i}/{len(chunks)}):\n{chunk}"
            )
            try:
                result = await self.agent.run(prompt)
                for q in result.output.quotes:
                    results_list.append({
                        "content": q.content,
                        "keyword_matched": q.keyword_matched,
                        "source": s3_uri,
                        "link": generate_url_fragement(s3_to_govuk_url(s3_uri), q.content)
                    })
            except Exception as e:
                logger.error(f"  Error in {s3_uri} chunk {i}: {e}")

    async def run_mapping(self, doc_to_keywords: dict):
        """Processes documents based on a mapping of {s3_uri: [keywords]}."""
        raw_findings = []
        
        tasks = [
            self.process_document(uri, keywords, raw_findings) 
            for uri, keywords in doc_to_keywords.items()
        ]
        await asyncio.gather(*tasks)
        return raw_findings

    async def run(self, output_file: str = "outputs/extracted_quotes.json"):
        """Main entry point to run extraction and save results."""
        doc_to_keywords = {uri: self.config.keywords for uri in self.config.s3_documents}
        raw_findings = await self.run_mapping(doc_to_keywords)

        keyword_map = defaultdict(lambda: defaultdict(set))
        for f in raw_findings:
            keyword_map[f["keyword_matched"]][f["content"]].add(f["source"])

        final_data = {
            kw: [Finding(content=txt, source_documents=sorted(list(srcs))) 
                 for txt, srcs in content_map.items()]
            for kw, content_map in keyword_map.items()
        }

        extraction = FinalQuoteExtraction(root=final_data)
        return extraction