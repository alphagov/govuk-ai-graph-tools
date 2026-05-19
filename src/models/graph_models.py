from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


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


class Relationship(BaseModel):
    type: str
    from_: str
    to: str

    model_config = ConfigDict(extra="allow")


class GraphInput(BaseModel):
    entities: List[Entity]
    relationships: List[Relationship] = Field(default_factory=list)

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
    edge_type: Optional[Literal["alias", "relationship"]] = None


class Edge(BaseModel):
    data: EdgeData


class SimilarAlias(BaseModel):
    id: str
    label: str
    similarity: int


class OutlierAlias(BaseModel):
    id: str
    label: str
    occurrence_count: int = 0
    similar_aliases: List[SimilarAlias] = Field(default_factory=list)


class AliasImbalanceStats(BaseModel):
    alias_id: str
    alias_label: str
    occurrence_count: int = 0
    z_score: Optional[float] = None


class EntityOutlier(BaseModel):
    entity_id: str
    entity_label: str
    occurrence_std_dev: float = 0.0
    aliases: List[OutlierAlias] = Field(default_factory=list)
    alias_imbalance: List[AliasImbalanceStats] = Field(default_factory=list)

    def model_post_init(self, __context: Any) -> None:
        """Compute z-score of alias_imbalance for each alias
        and add it to the alias_imbalance in an entity
        """
        import statistics

        counts = [stat.occurrence_count for stat in self.alias_imbalance]
        if len(counts) > 1:
            mean = statistics.mean(counts)
            std_dev = statistics.pstdev(counts)
            self.occurrence_std_dev = round(std_dev, 2)
            for stat in self.alias_imbalance:
                if std_dev > 0:
                    stat.z_score = round((stat.occurrence_count - mean) / std_dev, 2)
                else:
                    stat.z_score = 0.0
        elif len(counts) == 1:
            self.occurrence_std_dev = 0.0
            self.alias_imbalance[0].z_score = 0.0


class GraphOutput(BaseModel):
    nodes: List[Node]
    edges: List[Edge]
    relationships: List[Relationship] = Field(default_factory=list)
    outliers: List[EntityOutlier] = Field(default_factory=list)
