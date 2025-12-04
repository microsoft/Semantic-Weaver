"""
Core functionality for Semantic Weaver.

This package contains:
- Authentication management
- Semantic model transformation logic
- API clients for Fabric deployment
"""

from semanticweaver.core.auth import AuthenticationManager
from semanticweaver.core.transformer import SemanticModelTransformer

__all__ = ["AuthenticationManager", "SemanticModelTransformer"]
