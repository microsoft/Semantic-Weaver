"""
Source system plugins for Semantic Weaver.

This package contains plugins for various source systems:
- Databricks (Metric Views)
- Looker (planned)
- Additional sources can be added by creating new plugin folders
"""

from semanticweaver.plugins.base import BaseSourcePlugin

__all__ = ["BaseSourcePlugin"]
