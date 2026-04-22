import json
import asyncio
import os
import re
import logging
from typing import List, Dict, Any, Set, Tuple, Optional, Union
from collections import defaultdict
from src.content_extractor.s3_sequential import S3QuoteExtractor
from src.content_extractor.base import BaseExtractorConfig
from src.content_extractor.highlighter import highlight_occurrence
import fsspec
from src.models.graph_models import (
    GraphInput, GraphOutput, Node, NodeData, Edge, EdgeData, Occurrence, Entity
)


logger = logging.getLogger(__name__)

def slugify(text: str) -> str:
    """Simple slugify for node IDs."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '_', text)
    return text.strip('_')

def build_registries(entities: List[Entity]) -> Dict[str, Any]:
    """Parses entities to map s3_uris to keywords and metadata based on structured aliases."""
    registry = defaultdict(lambda: {"keywords": set(), "entities": []})
    
    for ent in entities:
        for alias in ent.aliases:
            for uri in alias.source_files:
                if not uri or not uri.startswith("s3://"):
                    continue
                registry[uri]["keywords"].add(alias.name)
                # Ensure each entity is only added once per unique URI
                if ent not in registry[uri]["entities"]:
                    registry[uri]["entities"].append(ent)
            
    return registry

async def fetch_extraction_findings(registry: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Runs the extractor over unique S3 documents."""
    config = BaseExtractorConfig(keywords=[], s3_documents=[])
    extractor = S3QuoteExtractor(config)

    doc_to_keywords = {
        uri: list(data["keywords"]) 
        for uri, data in registry.items() 
        if data["keywords"]
    }
    
    if not doc_to_keywords:
        logger.warning("No documents or aliases found to extract.")
        return []

    logger.info(f"Starting extraction for {len(doc_to_keywords)} documents...")
    return await extractor.run_mapping(doc_to_keywords)

def map_findings_to_entities(raw_findings: List[Dict[str, Any]], registry: Dict[str, Any]) -> Dict[str, Any]:
    """Groups findings by entity and alias with highlighting and links."""
    results = defaultdict(lambda: defaultdict(list))
    
    for finding in raw_findings:
        uri = finding["source"]
        keyword = finding["keyword_matched"]
        content = finding["content"]
        link = finding["link"] 
        
        for ent in registry[uri]["entities"]:
            if any(a.name == keyword for a in ent.aliases):
                occurrence = Occurrence(
                    link=link,
                    context=highlight_occurrence(content, keyword)
                )
                results[ent.canonical_key][keyword].append(occurrence)
                
    return results

def build_node_structure(entities: List[Entity], entity_results: Dict[str, Any]) -> GraphOutput:
    """Constructs the final list of nodes and edges."""
    nodes, edges = [], []

    for ent in entities:
        ent_id = ent.canonical_key
        human_label = ent.label or ent_id.replace("_", " ").title()
        nodes.append(Node(data=NodeData(id=ent_id, label=human_label, type="entity")))
        
        # Use a dict to accumulate alias nodes by their slugified ID to avoid duplicates
        alias_map = {}
        
        for alias_obj in ent.aliases:
            alias = alias_obj.name
            occurrences = entity_results[ent_id].get(alias, [])
            alias_id = f"{ent_id}__{slugify(alias)}"
            
            if alias_id not in alias_map:
                alias_map[alias_id] = NodeData(
                    id=alias_id,
                    label=alias,
                    type="alias",
                    occurrences=[]
                )
            
            if occurrences:
                alias_map[alias_id].occurrences.extend(occurrences)
        
        # Add the deduplicated alias nodes and their edges
        for alias_id, node_data in alias_map.items():
            # If no occurrences, clear the list (Pydantic will handle Optional)
            if not node_data.occurrences:
                node_data.occurrences = None
            
            nodes.append(Node(data=node_data))
            
            count = len(node_data.occurrences) if node_data.occurrences else 0
            edges.append(Edge(
                data=EdgeData(
                    source=ent_id,
                    target=alias_id,
                    label=f"Alias ({count})" if count > 0 else "Alias"
                )
            ))

    return GraphOutput(nodes=nodes, edges=edges)

async def generate_graph(input_data: Union[str, Dict[str, Any]], output_path: Optional[str] = None):
    """Main orchestration function. Can take a file path (str) or a dictionary."""
    if isinstance(input_data, str):
        of = fsspec.open(input_data, "r")
        if not of.fs.exists(of.path):
            logger.error(f"Input file {input_data} not found.")
            return
        with of as f:
            graph_data = json.load(f)
    else:
        graph_data = input_data
    
    # Validate input
    try:
        validated_input = GraphInput.model_validate(graph_data)
        entities = validated_input.entities
    except Exception as e:
        logger.error(f"Input validation failed: {e}")
        raise

    registry = build_registries(entities)
    
    raw_findings = await fetch_extraction_findings(registry)
    entity_results = map_findings_to_entities(raw_findings, registry)
    
    cy_graph = build_node_structure(entities, entity_results)
    cy_json = cy_graph.model_dump(exclude_none=True)
    
    if output_path:
        with fsspec.open(output_path, "w", auto_mkdir=True) as f:
            json.dump(cy_json, f, indent=4)
        logger.info(f"Graph saved to {summarize_path(output_path)}")
    
    return cy_json

def load_json_file(file_path: str) -> Dict[str, Any]:
    """Utility function to load JSON data from a file."""
    of = fsspec.open(file_path, "r")
    if not of.fs.exists(of.path):
        logger.error(f"File {file_path} not found.")
        return {}
    with of as f:
        return json.load(f)

def load_graph_viewmodel(file_path: str) -> Dict[str, Any]:
    """Loads the graph viewmodel JSON for the frontend."""
    return load_json_file(file_path)


def summarize_path(path: str) -> str:
    """Extracts a concise representation (project/run) of a path for logging."""
    match = re.search(r'([^/]+)/(run-\d+-\d+)', path)
    if match:
        return f"{match.group(1)}/{match.group(2)}"
    return path.split('/')[-1]

def generate_output_path(input_path: str) -> str:
    """Generates the output path for the graph JSON file."""
    

    match = re.search(r'(?P<base>s3://govuk-ai-accelerator-data-integration/)?(?P<domain_name>[^/]+)/(?P<run>run-\d+-\d+)', input_path)
    
    if match:
        base = match.group('base')
        domain_name = match.group('domain_name')
        run_id = match.group('run')
        
        if base:
            # Dynamically use the same S3 bucket but route to graph_tools prefix
            return f"{base}graph_tools/{domain_name}/output/graphNode.json"
            
        else:
            raise ValueError(f"Input path '{input_path}' does not contain a recognizable S3 path structure.")
    
    summary = summarize_path(input_path)
    raise ValueError(f"Input path '{summary}' does not contain a recognizable project/run structure.")

if __name__ == "__main__":
    asyncio.run(generate_graph("graph.json", "outputs/graphNode.json"))
