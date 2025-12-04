"""
Base configuration models for Semantic Weaver.

This module defines the base Pydantic models for configuration
that are shared across all source systems.
"""

from typing import Optional, Any, TYPE_CHECKING
from enum import Enum
from pathlib import Path
import yaml
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from semanticweaver.plugins.base import BaseSourcePlugin


class SourceType(str, Enum):
    """Supported source system types."""
    DATABRICKS = "DATABRICKS"
    LOOKER = "LOOKER"
    # Add more source types as plugins are developed


class FabricConfig(BaseModel):
    """Configuration for the target Microsoft Fabric workspace."""
    
    workspace_id: str = Field(..., description="The Fabric workspace ID")
    tenant_id: str = Field(..., description="The Azure tenant ID")
    semantic_model_name: Optional[str] = Field(
        None, 
        description="Name for the created semantic model. If not provided, uses source name."
    )


class ServicePrincipalConfig(BaseModel):
    """Azure Service Principal credentials."""
    
    client_id: str = Field(..., description="The Service Principal client ID")
    client_secret: str = Field(..., description="The Service Principal client secret")
    tenant_id: str = Field(..., description="The Service Principal tenant ID")


class SourceConfig(BaseModel):
    """Base source system configuration."""
    
    name: str = Field(..., description="Name of the source catalog/database")
    type: SourceType = Field(..., description="Type of source system")


class BaseSourceMap(BaseModel):
    """
    Base configuration model for all source systems.
    
    Subclasses should add source-specific configuration fields.
    """
    
    fabric: FabricConfig = Field(..., description="Target Fabric configuration")
    service_principal: ServicePrincipalConfig = Field(..., description="Service Principal credentials")
    source: SourceConfig = Field(..., description="Source system configuration")
    
    @classmethod
    def from_yaml(cls, file_path: str) -> "BaseSourceMap":
        """
        Load configuration from a YAML file.
        
        Args:
            file_path: Path to the YAML configuration file.
        
        Returns:
            The configuration object.
        
        Raises:
            FileNotFoundError: If the config file doesn't exist.
            ValidationError: If the config is invalid.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")
        
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        
        return cls(**data)
    
    def get_plugin(self) -> "BaseSourcePlugin":
        """
        Get the appropriate source plugin based on configuration.
        
        Returns:
            The source plugin instance configured for extraction.
        
        Raises:
            ValueError: If the source type is not supported.
        """
        # This method should be overridden in subclasses
        raise NotImplementedError("Subclasses must implement get_plugin()")
