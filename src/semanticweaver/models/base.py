"""
Base configuration models for Semantic Weaver.

This module defines the base Pydantic models for configuration
that are shared across all source systems.
"""

from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from semanticweaver.plugins.base import BaseSourcePlugin


class FabricConfig(BaseModel):
    """Configuration for the target Microsoft Fabric workspace."""

    workspace_id: str = Field(..., description="The Fabric workspace ID")
    tenant_id: str = Field(..., description="The Azure tenant ID")
    semantic_model_name_prefix: str | None = Field(
        None,
        description="Prefix for semantic model names. Models are named '<prefix><metric_view_name>'."
    )


class ServicePrincipalConfig(BaseModel):
    """Azure Service Principal credentials."""
    
    client_id: str = Field(..., description="The Service Principal client ID")
    client_secret: str = Field(..., description="The Service Principal client secret")
    tenant_id: str = Field(..., description="The Service Principal tenant ID")


class BaseSourceMap(BaseModel):
    """
    Base configuration model for all source systems.
    
    Subclasses should add source-specific configuration fields.
    """
    
    fabric: FabricConfig = Field(..., description="Target Fabric configuration")
    service_principal: ServicePrincipalConfig = Field(..., description="Service Principal credentials")
    
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
        
        with open(path) as f:
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
