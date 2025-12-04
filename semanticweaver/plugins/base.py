"""
Base plugin interface for source systems.

All source plugins must inherit from BaseSourcePlugin and implement
the required methods for authentication and extraction.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional
from semanticweaver.models.intermediate import IntermediateSemanticModel


class ExtractionError(Exception):
    """Raised when extraction from source system fails."""
    pass


class BaseSourcePlugin(ABC):
    """
    Abstract base class for source system plugins.
    
    All source plugins must implement:
    - authenticate(): Authenticate to the source system
    - extract_semantic_model(): Extract and return the semantic model
    
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
    async def extract_semantic_model(self) -> IntermediateSemanticModel:
        """
        Extract the semantic model from the source system.
        
        Returns:
            IntermediateSemanticModel: The extracted model in intermediate format.
        
        Raises:
            ExtractionError: If extraction fails.
        """
        pass
    
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
