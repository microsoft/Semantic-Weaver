"""
Semantic Weaver - Run Script

This script demonstrates how to use Semantic Weaver to connect to
Databricks Unity Catalog and extract semantic model definitions,
then transform them to Power BI Semantic Models.
"""

import asyncio

import yaml

from semanticweaver.core.transformer import SemanticModelTransformer
from semanticweaver.plugins.databricks import DatabricksSourceMap


async def main():
    """Main entry point for Semantic Weaver."""
    print("Semantic Weaver - Databricks to Fabric Migration")
    print("=" * 50)

    # Load config from YAML
    print("\n1. Loading configuration from config.yml...")
    config = DatabricksSourceMap.from_yaml("config.yml")
    print(f"   Catalogs: {', '.join(config.databricks.get_catalog_names())}")
    print(f"   Workspace: {config.databricks.workspace_url}")
    print(f"   Prefix: {config.fabric.semantic_model_name_prefix or '(none)'}")

    # Get the plugin
    print("\n2. Initializing Databricks plugin...")
    plugin = config.get_plugin()

    # Authenticate to Databricks
    print("\n3. Authenticating to Databricks...")
    try:
        await plugin.authenticate()
        print("   ✓ Authentication successful")
    except Exception as e:
        print(f"   ✗ Authentication failed: {e}")
        return

    # List available catalogs
    print("\n4. Listing available catalogs...")
    catalogs = await plugin.get_available_catalogs()
    for catalog in catalogs:
        print(f"   - {catalog}")

    # List schemas in the first configured catalog
    print(f"\n5. Listing schemas in '{config.databricks.default_catalog}' catalog...")
    schemas = await plugin.list_schemas()
    for schema in schemas:
        print(f"   - {schema.name}")

    # Collect all Metric Views for transformation
    all_metric_views = []

    # List Metric Views for each catalog.schema
    print("\n6. Listing Metric Views for each catalog.schema...")
    for catalog in catalogs:
        catalog_schemas = await plugin.list_schemas(catalog)
        for schema in catalog_schemas:
            full_name = f"{catalog}.{schema.name}"
            print(f"\n   [{full_name}]")
            metric_views = await plugin.list_metric_views(catalog, schema.name)
            if not metric_views:
                print("      (no metric views found)")
            else:
                for mv in metric_views:
                    all_metric_views.append(mv)
                    print(f"\n      Metric View: {mv.name or '(unnamed)'}")
                    print("      " + "-" * 40)
                    # Use Pydantic's model_dump with PyYAML for clean YAML output
                    mv_dict = mv.model_dump(exclude_none=True, exclude_unset=True)
                    mv_yaml = yaml.dump(mv_dict, default_flow_style=False, sort_keys=False, allow_unicode=True)
                    # Indent the YAML output for readability
                    for line in mv_yaml.strip().split('\n'):
                        print(f"      {line}")

    # Transform Metric Views to Power BI Semantic Models
    print("\n" + "=" * 50)
    print("\n7. Transforming Metric Views to Power BI Semantic Models...")

    if not all_metric_views:
        print("   (no metric views to transform)")
    else:
        transformer = SemanticModelTransformer(
            name_prefix=config.fabric.semantic_model_name_prefix
        )

        fabric_models = []
        for mv in all_metric_views:
            try:
                # Transform to intermediate model first
                intermediate = transformer.transform(mv)
                # Then convert to Fabric model
                fabric_model = transformer.to_fabric_model(intermediate)
                fabric_models.append(fabric_model)
                print(f"   ✓ Transformed: {mv.name} → {fabric_model.name}")
            except Exception as e:
                print(f"   ✗ Failed to transform {mv.name}: {e}")

        # List the Power BI Semantic Models
        print("\n8. Power BI Semantic Models created:")
        for model in fabric_models:
            print(f"\n   Semantic Model: {model.name}")
            print("   " + "-" * 40)
            # Use Pydantic's model_dump with PyYAML for clean YAML output
            model_dict = model.model_dump(exclude_none=True, exclude_unset=True)
            model_yaml = yaml.dump(model_dict, default_flow_style=False, sort_keys=False, allow_unicode=True)
            # Indent the YAML output for readability
            for line in model_yaml.strip().split('\n'):
                print(f"   {line}")

    print("\n" + "=" * 50)
    print("Semantic Weaver completed.")


if __name__ == "__main__":
    asyncio.run(main())
