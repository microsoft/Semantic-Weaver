"""
Main entry point for Semantic Weaver.

This module contains the WeaverAgent class that orchestrates the entire
semantic model migration process.
"""

from typing import Any
from semanticweaver.models.base import BaseSourceMap
from semanticweaver.core.auth import AuthenticationManager
from semanticweaver.core.transformer import SemanticModelTransformer
from semanticweaver.core.api.fabric_client import FabricClient


class WeaverAgent:
    """
    The main orchestrator for semantic model migration.
    
    This class coordinates the entire process of:
    1. Reading semantic model definitions from source systems
    2. Transforming them into an intermediate representation
    3. Deploying to Microsoft Fabric as Power BI Semantic Models
    """
    
    @classmethod
    async def run(cls, config: BaseSourceMap) -> None:
        """
        Execute the semantic model migration process.
        
        Args:
            config: The source configuration loaded from a YAML file.
                   This should be a subclass of BaseSourceMap specific to the
                   source system (e.g., DatabricksSourceMap).
        
        Raises:
            AuthenticationError: If authentication to source or target fails.
            ExtractionError: If reading from source system fails.
            DeploymentError: If deployment to Fabric fails.
        """
        # Step 1: Authenticate to source and target systems
        auth_manager = AuthenticationManager(config)
        await auth_manager.authenticate()
        
        # Step 2: Extract semantic model from source system
        source_plugin = config.get_plugin()
        source_model = await source_plugin.extract_semantic_model()
        
        # Step 3: Transform to intermediate representation
        transformer = SemanticModelTransformer()
        intermediate_model = transformer.transform(source_model)
        
        # Step 4: Deploy to Microsoft Fabric
        fabric_client = FabricClient(
            workspace_id=config.fabric.workspace_id,
            auth_manager=auth_manager
        )
        await fabric_client.deploy_semantic_model(intermediate_model)
        
        print(f"Successfully deployed semantic model to Fabric workspace: {config.fabric.workspace_id}")
