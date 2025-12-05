"""
Databricks plugin for Semantic Weaver.

This plugin extracts semantic model definitions from Databricks Unity Catalog,
specifically from Metric Views, and converts them to the intermediate format.
"""

from semanticweaver.plugins.databricks.model import DatabricksConfig, DatabricksSourceMap
from semanticweaver.plugins.databricks.plugin import AuthenticationError, DatabricksPlugin

__all__ = ["DatabricksPlugin", "DatabricksSourceMap", "DatabricksConfig", "AuthenticationError"]
