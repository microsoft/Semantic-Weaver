"""
Microsoft Fabric semantic model definitions.

This module defines Pydantic models that represent Power BI semantic models
in the format required by Microsoft Fabric APIs.
"""

from typing import Optional, Any
from pydantic import BaseModel, Field


class FabricColumn(BaseModel):
    """A column in a Fabric semantic model table."""
    
    name: str
    dataType: str
    sourceColumn: Optional[str] = None
    isHidden: bool = False
    description: Optional[str] = None
    formatString: Optional[str] = None
    displayFolder: Optional[str] = None
    summarizeBy: str = "none"


class FabricMeasure(BaseModel):
    """A measure in a Fabric semantic model."""
    
    name: str
    expression: str  # DAX expression
    description: Optional[str] = None
    formatString: Optional[str] = None
    displayFolder: Optional[str] = None
    isHidden: bool = False


class FabricPartition(BaseModel):
    """A partition (data source) for a table."""
    
    name: str
    mode: str = "import"  # import, directQuery, dual
    source: dict[str, Any] = Field(default_factory=dict)


class FabricTable(BaseModel):
    """A table in a Fabric semantic model."""
    
    name: str
    columns: list[FabricColumn] = Field(default_factory=list)
    measures: list[FabricMeasure] = Field(default_factory=list)
    partitions: list[FabricPartition] = Field(default_factory=list)
    isHidden: bool = False
    description: Optional[str] = None


class FabricRelationship(BaseModel):
    """A relationship between tables in the semantic model."""
    
    name: str
    fromTable: str
    fromColumn: str
    toTable: str
    toColumn: str
    fromCardinality: str = "many"  # one, many
    toCardinality: str = "one"  # one, many
    isActive: bool = True
    crossFilteringBehavior: str = "singleDirection"  # singleDirection, bothDirections


class FabricSemanticModel(BaseModel):
    """
    A complete Fabric semantic model definition.
    
    This model can be serialized to JSON/TMSL format for deployment
    to Microsoft Fabric via REST APIs.
    """
    
    name: str
    description: Optional[str] = None
    tables: list[FabricTable] = Field(default_factory=list)
    relationships: list[FabricRelationship] = Field(default_factory=list)
    
    # Model configuration
    defaultMode: str = "import"  # import, directQuery
    culture: str = "en-US"
    
    def to_tmsl(self) -> dict[str, Any]:
        """
        Convert to TMSL (Tabular Model Scripting Language) format.
        
        Returns:
            Dictionary representation in TMSL format for Fabric API.
        """
        # TODO: Implement TMSL conversion
        # This should create the proper structure for Fabric createOrUpdate API
        return {
            "createOrReplace": {
                "object": {
                    "database": self.name
                },
                "database": {
                    "name": self.name,
                    "model": {
                        "tables": [table.model_dump() for table in self.tables],
                        "relationships": [rel.model_dump() for rel in self.relationships]
                    }
                }
            }
        }
    
    def to_tmdl(self) -> str:
        """
        Convert to TMDL (Tabular Model Definition Language) format.
        
        Returns:
            String representation in TMDL format.
        """
        # TODO: Implement TMDL conversion
        # TMDL is a human-readable YAML-like format for semantic models
        pass
    
    @classmethod
    def from_intermediate(cls, intermediate: "IntermediateSemanticModel") -> "FabricSemanticModel":
        """
        Create a Fabric semantic model from intermediate representation.
        
        Args:
            intermediate: The intermediate semantic model.
        
        Returns:
            FabricSemanticModel ready for deployment.
        """
        # TODO: Implement conversion from intermediate model
        # Map IntermediateTable -> FabricTable, etc.
        pass


# Import for type hints
from semanticweaver.models.intermediate import IntermediateSemanticModel
