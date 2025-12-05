"""
Base plugin interface for source systems.

All source plugins must inherit from BaseSourcePlugin and implement
the required methods for authentication and extraction.
"""

from abc import ABC, abstractmethod
from typing import Any

from semanticweaver.models.intermediate import IntermediateSemanticModel


class ExtractionError(Exception):
    """Raised when extraction from source system fails."""
    pass


class BaseSourcePlugin(ABC):
    """
    Abstract base class for source system plugins.
    
    All source plugins must implement:
    - authenticate(): Authenticate to the source system
    - extract_semantic_models(): Extract and return semantic models (one per metric view)
    
    Optional methods:
    - validate_connection(): Test the connection to source
    - get_available_catalogs(): List available catalogs/databases
    """
    
    def __init__(self, config: Any):
        """
        Initialize the plugin with configuration.
        
        Args:
            config: Source-specific configuration object.
        """
        self.config = config
        self._authenticated = False
    
    @abstractmethod
    async def authenticate(self) -> None:
        """
        Authenticate to the source system.
        
        Raises:
            AuthenticationError: If authentication fails.
        """
        pass
    
    @abstractmethod
    async def extract_semantic_models(self) -> list[IntermediateSemanticModel]:
        """
        Extract semantic models from the source system.
        
        Queries all Metric Views (or equivalent) from the source and creates
        one IntermediateSemanticModel for each. The model name is formed by
        combining the configured prefix with the metric view name.
        
        Returns:
            list[IntermediateSemanticModel]: List of extracted models, one per metric view.
        
        Raises:
            ExtractionError: If extraction fails.
        """
        pass
    
    async def extract_semantic_model(self) -> IntermediateSemanticModel:
        """
        Extract a single semantic model from the source system.
        
        DEPRECATED: Use extract_semantic_models() instead to get all metric views.
        This method returns only the first model for backwards compatibility.
        
        Returns:
            IntermediateSemanticModel: The first extracted model.
        
        Raises:
            ExtractionError: If extraction fails.
        """
        models = await self.extract_semantic_models()
        if not models:
            raise ExtractionError("No semantic models found in source system")
        return models[0]
    
    async def validate_connection(self) -> bool:
        """
        Validate the connection to the source system.
        
        Returns:
            True if connection is valid, False otherwise.
        """
        try:
            await self.authenticate()
            return True
        except Exception:
            return False
    
    async def get_available_catalogs(self) -> list[str]:
        """
        List available catalogs/databases in the source system.
        
        Returns:
            List of catalog/database names.
        
        Raises:
            ExtractionError: If listing fails.
        """
        # Default implementation - override in subclasses
        raise NotImplementedError("This plugin does not support listing catalogs")
    
    @property
    def is_authenticated(self) -> bool:
        """Check if the plugin is authenticated."""
        return self._authenticated
