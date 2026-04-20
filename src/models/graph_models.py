from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Union, Any, Literal

class Alias(BaseModel):
    name: str
    source_files: List[str] = Field(default_factory=list)

class Entity(BaseModel):
    id: str
    canonical_key: str
    label: Optional[str] = None
    aliases: List[Alias] = Field(default_factory=list)
    properties: Dict[str, Any] = Field(default_factory=dict)
    type: Optional[str] = None
    description: Optional[str] = None

    model_config = ConfigDict(extra="allow")

class GraphInput(BaseModel):
    entities: List[Entity]
    
    model_config = ConfigDict(extra="allow")

class Occurrence(BaseModel):
    link: str
    context: str

class NodeData(BaseModel):
    id: str
    label: str
    type: Literal["entity", "alias"]
    occurrences: Optional[List[Occurrence]] = None

class Node(BaseModel):
    data: NodeData

class EdgeData(BaseModel):
    source: str
    target: str
    label: str

class Edge(BaseModel):
    data: EdgeData

class GraphOutput(BaseModel):
    nodes: List[Node]
    edges: List[Edge]
