"""
Databricks-specific configuration models.

This module defines Pydantic models for Databricks configuration
and Unity Catalog semantic model definitions.
"""

from typing import Optional
from pydantic import BaseModel, Field
from semanticweaver.models.base import BaseSourceMap, SourceType
from semanticweaver.plugins.base import BaseSourcePlugin


class DatabricksConfig(BaseModel):
    """Databricks-specific configuration."""
    
    workspace_url: str = Field(
        ..., 
        description="Databricks workspace URL (e.g., https://adb-xxx.azuredatabricks.net/)"
    )
    account_id: str = Field(..., description="Databricks account ID")
    account_api_token: str = Field(..., description="Databricks API token or OAuth secret")
    
    # Optional settings
    http_timeout: int = Field(30, description="HTTP request timeout in seconds")


class DatabricksSourceMap(BaseSourceMap):
    """
    Configuration model for Databricks source.
    
    Extends BaseSourceMap with Databricks-specific settings.
    """
    
    databricks: DatabricksConfig = Field(..., description="Databricks configuration")
    
    def get_plugin(self) -> "BaseSourcePlugin":
        """
        Get the Databricks source plugin.
        
        Returns:
            DatabricksPlugin instance configured for extraction.
        """
        from semanticweaver.plugins.databricks.plugin import DatabricksPlugin
        return DatabricksPlugin(self)


# ============================================================================
# Databricks Unity Catalog Models
# These represent the structure of semantic definitions in Databricks
# ============================================================================

class DatabricksMetricDefinition(BaseModel):
    """Represents a metric definition from Databricks Metric Views."""
    
    name: str = Field(..., description="Metric name")
    expression: str = Field(..., description="SQL/metric expression")
    description: Optional[str] = Field(None, description="Metric description")
    table_name: str = Field(..., description="Associated table name")
    
    # Metric properties
    aggregation: Optional[str] = Field(None, description="Aggregation function")
    filters: list[str] = Field(default_factory=list, description="Default filters")
    dimensions: list[str] = Field(default_factory=list, description="Valid dimensions")


class DatabricksDimension(BaseModel):
    """Represents a dimension from Databricks Metric Views."""
    
    name: str = Field(..., description="Dimension name")
    column_name: str = Field(..., description="Source column name")
    description: Optional[str] = Field(None, description="Dimension description")
    data_type: str = Field(..., description="Data type")


class DatabricksEntity(BaseModel):
    """Represents an entity (fact table) from Databricks Metric Views."""
    
    name: str = Field(..., description="Entity name")
    table_name: str = Field(..., description="Source table name")
    schema_name: str = Field(..., description="Schema name")
    catalog_name: str = Field(..., description="Catalog name")
    
    dimensions: list[DatabricksDimension] = Field(default_factory=list)
    metrics: list[DatabricksMetricDefinition] = Field(default_factory=list)


class DatabricksSemanticModel(BaseModel):
    """
    Represents the full semantic model definition from Databricks.
    
    This captures Metric Views, entities, dimensions, and metrics
    as defined in Unity Catalog.
    """
    
    name: str = Field(..., description="Model name")
    catalog_name: str = Field(..., description="Unity Catalog name")
    description: Optional[str] = Field(None, description="Model description")
    
    entities: list[DatabricksEntity] = Field(default_factory=list)
