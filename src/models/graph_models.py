import re
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

    def model_post_init(self, __context: Any) -> None:
        if self.label and not self.aliases:
            new_alias_name = " ".join(
                word.lower() for word in re.split(r"(?=[A-Z])", self.label) if word
            )

            existing_alias = next((a for a in self.aliases if a.name == new_alias_name), None)

            if not existing_alias:
                source_urls_val = self.properties.get("sourceUrls", "")
                if isinstance(source_urls_val, list):
                    new_urls = [
                        url.strip()
                        for url in source_urls_val
                        if isinstance(url, str) and url.strip()
                    ]
                elif isinstance(source_urls_val, str):
                    new_urls = (
                        [url.strip() for url in source_urls_val.split(",") if url.strip()]
                        if source_urls_val
                        else []
                    )
                else:
                    new_urls = []

                new_alias = Alias(name=new_alias_name, source_files=new_urls)
                self.aliases.append(new_alias)


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

        self.alias_imbalance = [stat for stat in self.alias_imbalance if stat.occurrence_count > 0]
        self.aliases = [alias for alias in self.aliases if alias.occurrence_count > 0]

        valid_alias_ids = {alias.id for alias in self.aliases}
        for alias in self.aliases:
            alias.similar_aliases = [
                similar for similar in alias.similar_aliases if similar.id in valid_alias_ids
            ]

        if len(self.aliases) <= 1:
            for alias in self.aliases:
                alias.similar_aliases = []

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

    def model_post_init(self, __context: Any) -> None:
        if not self.outliers:
            return

        valid_entity_ids = set()
        valid_node_ids = set()

        for outlier in self.outliers:
            if len(outlier.alias_imbalance) > 0:
                valid_entity_ids.add(outlier.entity_id)
                valid_node_ids.add(outlier.entity_id)
                for alias in outlier.aliases:
                    valid_node_ids.add(alias.id)

        self.outliers = [
            outlier for outlier in self.outliers if outlier.entity_id in valid_entity_ids
        ]

        self.nodes = [node for node in self.nodes if node.data.id in valid_node_ids]

        self.edges = [
            edge
            for edge in self.edges
            if edge.data.source in valid_node_ids and edge.data.target in valid_node_ids
        ]
