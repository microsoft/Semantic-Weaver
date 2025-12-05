"""
Main entry point for Semantic Weaver.

This module contains the WeaverAgent class that orchestrates the entire
semantic model migration process.
"""

from semanticweaver.core.api.fabric_client import FabricClient
from semanticweaver.core.auth import AuthenticationManager
from semanticweaver.core.transformer import SemanticModelTransformer
from semanticweaver.models.base import BaseSourceMap


class WeaverAgent:
    """
    The main orchestrator for semantic model migration.

    This class coordinates the entire process of:
    1. Reading semantic model definitions from source systems
    2. Transforming them into a Fabric semantic model representation
    3. Deploying to Microsoft Fabric as Power BI Semantic Models
    """

    @classmethod
    async def run(cls, config: BaseSourceMap) -> list[str]:
        """
        Execute the semantic model migration process.

        Extracts all semantic models from the source system (one per Metric View),
        transforms them to Fabric format, and deploys them all to the target workspace.

        Args:
            config: The source configuration loaded from a YAML file.
                   This should be a subclass of BaseSourceMap specific to the
                   source system (e.g., DatabricksSourceMap).

        Returns:
            list[str]: List of deployed semantic model IDs in Fabric.

        Raises:
            AuthenticationError: If authentication to source or target fails.
            ExtractionError: If reading from source system fails.
            DeploymentError: If deployment to Fabric fails.
        """
        # Step 1: Authenticate to source and target systems
        auth_manager = AuthenticationManager(config)
        await auth_manager.authenticate()

        # Step 2: Extract all semantic models from source system
        # Each Metric View in the source becomes a separate semantic model
        source_plugin = config.get_plugin()
        await source_plugin.authenticate()
        intermediate_models = await source_plugin.extract_semantic_models()

        print(f"Extracted {len(intermediate_models)} semantic model(s) from source")

        # Step 3: Transform all models to Fabric format
        transformer = SemanticModelTransformer()
        fabric_models = transformer.transform_all(intermediate_models)

        print(f"Transformed {len(fabric_models)} model(s) to Fabric format")

        # Step 4: Deploy all semantic models to Microsoft Fabric
        fabric_client = FabricClient(
            workspace_id=config.fabric.workspace_id,
            auth_manager=auth_manager
        )
        deployed_model_ids = await fabric_client.deploy_semantic_models(fabric_models)

        print(f"Successfully deployed {len(deployed_model_ids)} semantic model(s) to Fabric workspace: "
              f"{config.fabric.workspace_id}")

        return deployed_model_ids
