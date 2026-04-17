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

logger = logging.getLogger(__name__)

def slugify(text: str) -> str:
    """Simple slugify for node IDs."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '_', text)
    return text.strip('_')

def build_registries(entities: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Parses entities to map s3_uris to keywords and metadata."""
    registry = defaultdict(lambda: {"keywords": set(), "entities": []})
    
    for ent in entities:
        props = ent.get("properties", {})
        source_urls_raw = props.get("sourceUrls", [])
        
        if isinstance(source_urls_raw, str):
            s3_uris = [u.strip() for u in source_urls_raw.split(',')]
        else:
            s3_uris = source_urls_raw
            
        aliases = ent.get("aliases", [])
        
        for uri in s3_uris:
            if not uri: continue
            registry[uri]["keywords"].update(aliases)
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
        link = finding["link"] # Use the pre-calculated link from extractor
        
        for ent in registry[uri]["entities"]:
            if keyword in ent.get("aliases", []):
                occurrence = {
                    "link": link,
                    "context": highlight_occurrence(content, keyword)
                }
                results[ent["canonical_key"]][keyword].append(occurrence)
                
    return results

def build_node_structure(entities: List[Dict[str, Any]], entity_results: Dict[str, Any]) -> Dict[str, Any]:
    """Constructs the final list of nodes and edges."""
    nodes, edges = [], []

    for ent in entities:
        ent_id = ent["canonical_key"]
        human_label = ent.get("label") or ent_id.replace("_", " ").title()
        nodes.append({"data": {"id": ent_id, "label": human_label, "type": "entity"}})
        
        # Use a dict to accumulate alias nodes by their slugified ID to avoid duplicates
        alias_map = {}
        
        for alias in ent.get("aliases", []):
            occurrences = entity_results[ent_id].get(alias, [])
            alias_id = f"{ent_id}__{slugify(alias)}"
            
            if alias_id not in alias_map:
                alias_map[alias_id] = {
                    "id": alias_id,
                    "label": alias,
                    "type": "alias",
                    "occurrences": []
                }
            
            if occurrences:
                alias_map[alias_id]["occurrences"].extend(occurrences)
        
        # Add the deduplicated alias nodes and their edges
        for alias_id, alias_data in alias_map.items():
            # If no occurrences, remove the empty list from the data
            if not alias_data["occurrences"]:
                del alias_data["occurrences"]
            
            nodes.append({"data": alias_data})
            
            count = len(alias_data.get("occurrences", []))
            edges.append({
                "data": {
                    "source": ent_id,
                    "target": alias_id,
                    "label": f"Alias ({count})" if count > 0 else "Alias"
                }
            })

    return {"nodes": nodes, "edges": edges}

async def generate_graph(input_data: Union[str, Dict[str, Any]], output_path: Optional[str] = None):
    """Main orchestration function. Can take a file path (str) or a dictionary."""
    if isinstance(input_data, str):
        if not os.path.exists(input_data):
            logger.error(f"Input file {input_data} not found.")
            return
        with open(input_data, "r") as f:
            graph_data = json.load(f)
    else:
        graph_data = input_data
    
    entities = graph_data.get("entities", [])
    registry = build_registries(entities)
    
    raw_findings = await fetch_extraction_findings(registry)
    entity_results = map_findings_to_entities(raw_findings, registry)
    
    cy_json = build_node_structure(entities, entity_results)
    
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(cy_json, f, indent=4)
        logger.info(f"Graph saved to {output_path}")
    
    return cy_json

def load_json_file(file_path: str) -> Dict[str, Any]:
    """Utility function to load JSON data from a file."""
    if not os.path.exists(file_path):
        logger.error(f"File {file_path} not found.")
        return {}
    with open(file_path, "r") as f:
        return json.load(f)

def load_graph_viewmodel(file_path: str) -> Dict[str, Any]:
    """Loads the graph viewmodel JSON for the frontend."""
    return load_json_file(file_path)

if __name__ == "__main__":
    asyncio.run(generate_graph("graph.json", "outputs/graphNode.json"))
