"""
API clients for Semantic Weaver.

This package contains REST API clients for interacting with
Microsoft Fabric and creating/deploying semantic models.
"""

from semanticweaver.core.api.fabric_client import (
    DeploymentError,
    FabricAuthenticationError,
    FabricClient,
)

__all__ = ["DeploymentError", "FabricAuthenticationError", "FabricClient"]
