"""
Intermediate semantic model representation.

This module defines the generic intermediate format that serves as the
bridge between source-specific models and the Fabric semantic model format.
"""

from enum import Enum

from pydantic import BaseModel, Field


class DataType(str, Enum):
    """Supported data types for columns."""
    STRING = "String"
    INTEGER = "Int64"
    DECIMAL = "Decimal"
    DOUBLE = "Double"
    BOOLEAN = "Boolean"
    DATETIME = "DateTime"
    DATE = "Date"
    TIME = "Time"
    BINARY = "Binary"


class AggregationType(str, Enum):
    """Supported aggregation types for measures."""
    SUM = "Sum"
    COUNT = "Count"
    DISTINCTCOUNT = "DistinctCount"
    AVERAGE = "Average"
    MIN = "Min"
    MAX = "Max"
    NONE = "None"


class RelationshipCardinality(str, Enum):
    """Cardinality types for relationships."""
    ONE_TO_ONE = "OneToOne"
    ONE_TO_MANY = "OneToMany"
    MANY_TO_ONE = "ManyToOne"
    MANY_TO_MANY = "ManyToMany"


class IntermediateColumn(BaseModel):
    """Represents a column in the intermediate model."""
    
    name: str = Field(..., description="Column name")
    data_type: DataType = Field(..., description="Data type of the column")
    description: str | None = Field(None, description="Column description")
    is_hidden: bool = Field(False, description="Whether the column is hidden")
    display_folder: str | None = Field(None, description="Display folder for organization")
    format_string: str | None = Field(None, description="Format string for display")
    source_column: str | None = Field(None, description="Source column name if different")


class IntermediateMeasure(BaseModel):
    """Represents a measure/metric in the intermediate model."""
    
    name: str = Field(..., description="Measure name")
    expression: str = Field(..., description="DAX expression for the measure")
    description: str | None = Field(None, description="Measure description")
    display_folder: str | None = Field(None, description="Display folder for organization")
    format_string: str | None = Field(None, description="Format string for display")
    is_hidden: bool = Field(False, description="Whether the measure is hidden")
    
    # Original metric definition from source (for reference)
    source_definition: str | None = Field(None, description="Original source definition")
    aggregation_type: AggregationType | None = Field(None, description="Aggregation type")


class IntermediateTable(BaseModel):
    """Represents a table in the intermediate model."""
    
    name: str = Field(..., description="Table name")
    description: str | None = Field(None, description="Table description")
    columns: list[IntermediateColumn] = Field(default_factory=list, description="Table columns")
    measures: list[IntermediateMeasure] = Field(default_factory=list, description="Table measures")
    is_hidden: bool = Field(False, description="Whether the table is hidden")
    
    # Source information
    source_schema: str | None = Field(None, description="Source schema name")
    source_table: str | None = Field(None, description="Source table name")
    source_query: str | None = Field(None, description="Source SQL query if not direct table")


class IntermediateRelationship(BaseModel):
    """Represents a relationship between tables."""
    
    name: str = Field(..., description="Relationship name")
    from_table: str = Field(..., description="Source table name")
    from_column: str = Field(..., description="Source column name")
    to_table: str = Field(..., description="Target table name")
    to_column: str = Field(..., description="Target column name")
    cardinality: RelationshipCardinality = Field(
        RelationshipCardinality.MANY_TO_ONE,
        description="Relationship cardinality"
    )
    is_active: bool = Field(True, description="Whether the relationship is active")
    cross_filter_direction: str = Field("Single", description="Cross filter direction")


class IntermediateSemanticModel(BaseModel):
    """
    The intermediate representation of a semantic model.
    
    This is the common format used between source extraction and Fabric deployment.
    It captures tables, columns, measures, and relationships in a generic way.
    """
    
    name: str = Field(..., description="Model name")
    description: str | None = Field(None, description="Model description")
    tables: list[IntermediateTable] = Field(default_factory=list, description="Model tables")
    relationships: list[IntermediateRelationship] = Field(
        default_factory=list, 
        description="Model relationships"
    )
    
    # Metadata
    source_system: str = Field(..., description="Source system type (e.g., DATABRICKS)")
    source_name: str | None = Field(None, description="Original source name/catalog")
    
    def add_table(self, table: IntermediateTable) -> None:
        """Add a table to the model."""
        self.tables.append(table)
    
    def add_relationship(self, relationship: IntermediateRelationship) -> None:
        """Add a relationship to the model."""
        self.relationships.append(relationship)
    
    def get_table(self, name: str) -> IntermediateTable | None:
        """Get a table by name."""
        for table in self.tables:
            if table.name == name:
                return table
        return None
    
    def get_all_measures(self) -> list[IntermediateMeasure]:
        """Get all measures from all tables."""
        measures = []
        for table in self.tables:
            measures.extend(table.measures)
        return measures
