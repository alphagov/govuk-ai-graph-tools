import os
import boto3
import json
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from pprint import pprint
from pydantic import BaseModel, Field, RootModel
from pydantic_ai import Agent
from pydantic_ai.models.bedrock import BedrockConverseModel
from pydantic_ai.providers.bedrock import BedrockProvider

# --- Shared Models ---

class AgentQuote(BaseModel):
    """Simple quote model for the agent to return."""
    content: str = Field(description="The exact sentence or phrase found in the document.")
    keyword_matched: str = Field(description="The keyword or phrase that triggered this match.")

class AgentQuoteExtraction(BaseModel):
    """Collection of quotes returned by the agent for a single document."""
    quotes: List[AgentQuote]

class Finding(BaseModel):
    """A single unique finding within a keyword group."""
    content: str
    source_documents: List[str]

class FinalQuoteExtraction(BaseModel): # Changed to BaseModel as RootModel is often unnecessary for simple dict roots
    """The final collection of quotes as a dictionary of keyword -> list of findings."""
    root: Dict[str, List[Finding]]

# --- Shared Configuration ---

@dataclass
class BaseExtractorConfig:
    keywords: List[str]
    s3_documents: List[str]
    model_id: str = "eu.anthropic.claude-sonnet-4-6"
    region: str = field(default_factory=lambda: os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "eu-west-2")))
    chunk_max_chars: int = 6000
    secret_id: Optional[str] = None

# --- Base Extractor Class ---

class BaseQuoteExtractor:
    def __init__(self, config: BaseExtractorConfig):
        self.config = config
        self.s3_client = boto3.client("s3", region_name=self.config.region)
        
        # Initialize Bedrock Agent
        model = BedrockConverseModel(
            self.config.model_id, 
            provider=BedrockProvider(region_name=self.config.region)
        )
        self.agent = Agent(
            model,
            output_type=AgentQuoteExtraction,
            system_prompt=(
                "You are an expert at extracting direct quotes from documents. "
                "Given a list of keywords and the content of a document segment, "
                "identify every sentence that contains at least one of the keywords. "
                "For each match, return:\n"
                "1. the EXACT sentence as 'content' (do not paraphrase)\n"
                "2. the keyword that was matched as 'keyword_matched'\n\n"
                "If a keyword appears multiple times in different sentences, extract each unique sentence. "
                "If no matches are found, return an empty list of quotes.\n"
                "Also note source document is a markdown file; consider this when pre-cleaning."
            )
        )

    def get_aws_secret(self, secret_id: str) -> dict:
        """Fetches and parses a JSON secret from AWS Secrets Manager."""
        client = boto3.client("secretsmanager", region_name=self.config.region)
        try:
            response = client.get_secret_value(SecretId=secret_id)
            if "SecretString" in response:
                return json.loads(response["SecretString"])
            else:
                return {}
        except Exception as e:
            pprint(f"Error fetching secret {secret_id}: {e}")
            return {}

    def fetch_s3_content(self, s3_uri: str) -> str:
        """Fetches the content of a markdown file from S3."""
        try:
            if not s3_uri.startswith("s3://"):
                raise ValueError(f"Invalid S3 URI: {s3_uri}")
            
            parts = s3_uri.replace("s3://", "").split("/", 1)
            bucket, key = parts
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            return response["Body"].read().decode("utf-8")
        except Exception as e:
            pprint(f"Error fetching {s3_uri}: {e}")
            return ""

    def chunk_content(self, text: str) -> List[str]:
        """Splits text into chunks respecting paragraph boundaries."""
        if not text:
            return []
        
        paragraphs = text.split("\n\n")
        chunks, current_chunk = [], []
        current_length = 0
        
        for para in paragraphs:
            para_len = len(para)
            if current_length + para_len > self.config.chunk_max_chars and current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk, current_length = [para], para_len
            else:
                current_chunk.append(para)
                current_length += para_len + 2 # +2 for \n\n separators
                
        if current_chunk:
            chunks.append("\n\n".join(current_chunk))
        return chunks
