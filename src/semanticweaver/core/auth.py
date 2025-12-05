"""
Authentication management for Semantic Weaver.

This module handles authentication to both source systems and Microsoft Fabric.
"""


from semanticweaver.models.base import BaseSourceMap


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


class AuthenticationManager:
    """
    Manages authentication for source and target systems.
    
    Supports:
    - Azure Service Principal authentication for Fabric
    - Source system specific authentication (delegated to plugins)
    """
    
    def __init__(self, config: BaseSourceMap):
        """
        Initialize the authentication manager.
        
        Args:
            config: The source configuration containing credentials.
        """
        self.config = config
        self._fabric_token: str | None = None
        self._source_token: str | None = None
    
    async def authenticate(self) -> None:
        """
        Authenticate to all required systems.
        
        Raises:
            AuthenticationError: If authentication fails.
        """
        await self._authenticate_fabric()
        await self._authenticate_source()
    
    async def _authenticate_fabric(self) -> None:
        """
        Authenticate to Microsoft Fabric using Service Principal.
        
        Uses the client_id and client_secret from the configuration
        to obtain an access token for Fabric APIs.
        """
        # TODO: Implement Azure AD authentication
        # Use MSAL or azure-identity library to get token
        # Scopes: https://api.fabric.microsoft.com/.default
        pass
    
    async def _authenticate_source(self) -> None:
        """
        Authenticate to the source system.
        
        Delegates to the source plugin for system-specific authentication.
        """
        # TODO: Delegate to source plugin for authentication
        pass
    
    @property
    def fabric_token(self) -> str:
        """Get the Fabric access token."""
        if not self._fabric_token:
            raise AuthenticationError("Not authenticated to Fabric. Call authenticate() first.")
        return self._fabric_token
    
    @property
    def source_token(self) -> str:
        """Get the source system access token."""
        if not self._source_token:
            raise AuthenticationError("Not authenticated to source. Call authenticate() first.")
        return self._source_token
