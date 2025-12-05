"""
Databricks source plugin implementation.

This plugin connects to Databricks Unity Catalog, extracts Metric Views
and other semantic definitions, and converts them to the intermediate format.
"""

import yaml

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.catalog import CatalogInfo, SchemaInfo, TableType

from semanticweaver.models.intermediate import (
    AggregationType,
    DataType,
    IntermediateColumn,
    IntermediateMeasure,
    IntermediateSemanticModel,
    IntermediateTable,
)
from semanticweaver.plugins.base import BaseSourcePlugin
from semanticweaver.plugins.databricks.model import DatabricksMetricView, DatabricksSourceMap


class AuthenticationError(Exception):
    """Raised when authentication to Databricks fails."""
    pass


class DatabricksPlugin(BaseSourcePlugin):
    """
    Plugin for extracting semantic models from Databricks Unity Catalog.
    
    Uses the Databricks SDK to connect to Unity Catalog and extract
    Metric Views, tables, and semantic definitions. Creates one Fabric
    semantic model for each Metric View found in the catalog.
    """
    
    def __init__(self, config: DatabricksSourceMap):
        """
        Initialize the Databricks plugin.
        
        Args:
            config: Databricks source configuration.
        """
        super().__init__(config)
        self.config: DatabricksSourceMap = config
        self._client: WorkspaceClient | None = None
    
    @property
    def client(self) -> WorkspaceClient:
        """
        Get the Databricks WorkspaceClient.
        
        Returns:
            WorkspaceClient: The authenticated Databricks client.
        
        Raises:
            AuthenticationError: If not authenticated.
        """
        if self._client is None:
            raise AuthenticationError("Not authenticated. Call authenticate() first.")
        return self._client
    
    async def authenticate(self) -> None:
        """
        Authenticate to Databricks using the configured credentials.
        
        Uses Personal Access Token (PAT) authentication with the workspace URL
        and API token from the configuration.
        
        Raises:
            AuthenticationError: If authentication fails.
        """
        try:
            # Remove trailing slash from workspace URL if present
            workspace_url = self.config.databricks.workspace_url.rstrip("/")
            
            # Initialize the Databricks client with PAT authentication
            self._client = WorkspaceClient(
                host=workspace_url,
                token=self.config.databricks.account_api_token
            )

            # Verify connection by getting current user
            # This validates that the token is valid
            self._client.current_user.me()

            self._authenticated = True
            
        except Exception as e:
            self._authenticated = False
            self._client = None
            raise AuthenticationError(f"Failed to authenticate to Databricks: {e}") from e
    
    async def validate_connection(self) -> bool:
        """
        Validate the connection to Databricks Unity Catalog.
        
        Attempts to authenticate and verify access to the configured catalog.
        
        Returns:
            bool: True if connection is valid, False otherwise.
        """
        try:
            if not self._authenticated:
                await self.authenticate()
            
            # Verify we can access the first configured catalog
            catalog_name = self.config.databricks.default_catalog
            catalog = self._client.catalogs.get(catalog_name)
            
            return catalog is not None
            
        except Exception:
            return False
    
    async def get_catalog_info(self) -> CatalogInfo | None:
        """
        Get information about the configured Unity Catalog.
        
        Returns:
            CatalogInfo: The catalog information, or None if not found.
        """
        if not self._authenticated:
            await self.authenticate()
        
        try:
            catalog_name = self.config.databricks.default_catalog
            return self._client.catalogs.get(catalog_name)
        except Exception:
            return None
    
    async def list_schemas(self, catalog_name: str | None = None) -> list[SchemaInfo]:
        """
        List schemas in a catalog, filtered by configuration.

        Only returns schemas that are configured in config.yml for the catalog.
        If no schemas are specified in config, returns all schemas.

        Args:
            catalog_name: Catalog to list schemas for. Defaults to first configured catalog.

        Returns:
            list[SchemaInfo]: List of schemas matching the configuration filter.
        """
        if not self._authenticated:
            await self.authenticate()

        catalog = catalog_name or self.config.databricks.default_catalog
        all_schemas = list(self._client.schemas.list(catalog_name=catalog))

        # Get configured schema filter for this catalog
        configured_schemas = self.config.databricks.get_schemas_for_catalog(catalog)

        # If no schemas configured (None), return all schemas
        if configured_schemas is None:
            return all_schemas

        # Filter to only configured schemas
        return [s for s in all_schemas if s.name in configured_schemas]

    async def get_available_catalogs(self) -> list[str]:
        """
        List Unity Catalogs that are configured in config.yml.

        Only returns catalogs that are both accessible to the authenticated user
        AND specified in the configuration file.

        Returns:
            list[str]: List of configured catalog names that are accessible.
        """
        if not self._authenticated:
            await self.authenticate()

        # Get all accessible catalogs from Databricks
        all_catalogs = list(self._client.catalogs.list())
        accessible_catalog_names = {c.name for c in all_catalogs if c.name}

        # Get configured catalog names
        configured_catalog_names = self.config.databricks.get_catalog_names()

        # Return only catalogs that are both configured AND accessible
        return [name for name in configured_catalog_names if name in accessible_catalog_names]

    async def list_metric_views(
        self, catalog_name: str | None = None, schema_name: str | None = None
    ) -> list[DatabricksMetricView]:
        """
        List all Metric Views in a catalog/schema.

        Queries the Databricks Unity Catalog to discover all Metric View objects
        in the specified (or configured) catalog and schema.

        Args:
            catalog_name: Catalog to query. Defaults to first configured catalog.
            schema_name: Schema to query. If None, queries all configured schemas.

        Returns:
            list[DatabricksMetricView]: List of Metric View definitions.
        """
        if not self._authenticated:
            await self.authenticate()

        catalog = catalog_name or self.config.databricks.default_catalog

        # Get schemas to query
        if schema_name:
            schemas_to_query = [schema_name]
        else:
            # Get all schemas for this catalog (filtered by config)
            schema_infos = await self.list_schemas(catalog)
            schemas_to_query = [s.name for s in schema_infos if s.name]

        metric_views: list[DatabricksMetricView] = []

        for schema in schemas_to_query:
            # Query metric views in this schema
            schema_metric_views = await self._get_metric_views_in_schema(
                catalog, schema
            )
            metric_views.extend(schema_metric_views)

        return metric_views

    def _parse_format(self, format_def: dict | None):
        """
        Parse a format specification from YAML into the appropriate model.

        Args:
            format_def: Format dictionary from YAML, or None.

        Returns:
            FormatSpecification model or None.
        """
        if not format_def:
            return None

        from semanticweaver.plugins.databricks.model import (
            CurrencyFormat,
            DateFormat,
            DateTimeFormat,
            DecimalPlaces,
            NumberFormat,
            PercentageFormat,
        )

        format_type = format_def.get("type")

        # Parse decimal_places if present
        decimal_places = None
        if "decimal_places" in format_def:
            dp = format_def["decimal_places"]
            decimal_places = DecimalPlaces(
                type=dp.get("type", "exact"),
                places=dp.get("places"),
            )

        if format_type == "number":
            return NumberFormat(
                type="number",
                decimal_places=decimal_places,
                hide_group_separator=format_def.get("hide_group_separator"),
                abbreviation=format_def.get("abbreviation"),
            )
        elif format_type == "currency":
            return CurrencyFormat(
                type="currency",
                currency_code=format_def.get("currency_code", "USD"),
                decimal_places=decimal_places,
                hide_group_separator=format_def.get("hide_group_separator"),
                abbreviation=format_def.get("abbreviation"),
            )
        elif format_type == "percentage":
            return PercentageFormat(
                type="percentage",
                decimal_places=decimal_places,
                hide_group_separator=format_def.get("hide_group_separator"),
            )
        elif format_type == "date":
            return DateFormat(
                type="date",
                date_format=format_def.get("date_format", "year_month_day"),
                leading_zeros=format_def.get("leading_zeros"),
            )
        elif format_type == "date_time":
            return DateTimeFormat(
                type="date_time",
                date_format=format_def.get("date_format"),
                time_format=format_def.get("time_format"),
                leading_zeros=format_def.get("leading_zeros"),
            )

        return None

    async def _get_metric_views_in_schema(
        self, catalog_name: str, schema_name: str
    ) -> list[DatabricksMetricView]:
        """
        Query Metric Views from a specific schema using the Tables API.

        Uses the databricks-sdk tables.list() method to find all tables
        with table_type=METRIC_VIEW, then parses their YAML definitions
        from the view_definition field.

        Args:
            catalog_name: Unity Catalog name.
            schema_name: Schema name.

        Returns:
            list[DatabricksMetricView]: Metric Views in the schema.
        """
        metric_views: list[DatabricksMetricView] = []

        try:
            # List all tables in the schema
            tables = list(
                self._client.tables.list(
                    catalog_name=catalog_name,
                    schema_name=schema_name,
                    omit_columns=False,  # We need column info
                    omit_properties=False,  # We need properties
                )
            )

            # Filter for METRIC_VIEW table type
            for table in tables:
                if table.table_type == TableType.METRIC_VIEW:
                    metric_view = self._parse_metric_view_from_table(table)
                    if metric_view:
                        metric_views.append(metric_view)

        except Exception as e:
            # Log warning but don't fail - schema might not be accessible
            print(f"Warning: Could not list tables in {catalog_name}.{schema_name}: {e}")

        return metric_views

    def _parse_metric_view_from_table(self, table) -> DatabricksMetricView | None:
        """
        Parse a TableInfo object into a DatabricksMetricView.

        The view_definition field contains the YAML specification of the
        Metric View, which we parse to extract dimensions and measures.

        Args:
            table: TableInfo object from the Databricks SDK.

        Returns:
            DatabricksMetricView if parsing succeeds, None otherwise.
        """
        from semanticweaver.plugins.databricks.model import (
            DatabricksDimension,
            DatabricksMeasure,
            WindowSpecification,
        )

        try:
            # Parse the YAML definition from view_definition
            if table.view_definition:
                yaml_def = yaml.safe_load(table.view_definition)
            else:
                yaml_def = {}

            # Extract dimensions from YAML with all fields
            dimensions = []
            for dim_def in yaml_def.get("dimensions", []):
                dim = DatabricksDimension(
                    name=dim_def.get("name", ""),
                    expr=dim_def.get("expr", dim_def.get("name", "")),
                    comment=dim_def.get("comment"),
                    display_name=dim_def.get("display_name"),
                    format=self._parse_format(dim_def.get("format")),
                    synonyms=dim_def.get("synonyms", []),
                )
                dimensions.append(dim)

            # Extract measures from YAML with all fields
            measures = []
            for measure_def in yaml_def.get("measures", []):
                # Parse window specifications if present
                window_specs = []
                for win_def in measure_def.get("window", []):
                    window_spec = WindowSpecification(
                        order=win_def.get("order", ""),
                        semiadditive=win_def.get("semiadditive"),
                        range=win_def.get("range"),
                    )
                    window_specs.append(window_spec)

                measure = DatabricksMeasure(
                    name=measure_def.get("name", ""),
                    expr=measure_def.get("expr", ""),
                    comment=measure_def.get("comment"),
                    display_name=measure_def.get("display_name"),
                    format=self._parse_format(measure_def.get("format")),
                    window=window_specs,
                    synonyms=measure_def.get("synonyms", []),
                )
                measures.append(measure)

            # Create the metric view object
            # Note: version may be parsed as int from YAML, so convert to string
            version_value = yaml_def.get("version", "1.1")
            metric_view = DatabricksMetricView(
                name=table.name,
                catalog_name=table.catalog_name,
                schema_name=table.schema_name,
                version=str(version_value),
                source=yaml_def.get("source", f"{table.catalog_name}.{table.schema_name}.{table.name}"),
                dimensions=dimensions,
                measures=measures,
                comment=table.comment or yaml_def.get("comment"),
                filter=yaml_def.get("filter"),
                joins=yaml_def.get("joins"),
            )

            return metric_view

        except Exception as e:
            print(f"Warning: Could not parse metric view {table.full_name}: {e}")
            return None

    async def extract_semantic_models(self) -> list[IntermediateSemanticModel]:
        """
        Extract semantic models from Databricks Unity Catalog.
        
        Queries all Metric Views in the configured catalog and creates
        one IntermediateSemanticModel for each. The model name is formed
        by combining the configured prefix with the metric view name.
        
        Returns:
            list[IntermediateSemanticModel]: List of extracted models.
        
        Raises:
            ExtractionError: If extraction fails.
        """
        if not self._authenticated:
            await self.authenticate()
        
        # Step 1: Get all metric views from the catalog
        metric_views = await self._get_all_metric_views()
        
        # Step 2: Convert each metric view to an intermediate semantic model
        models = []
        prefix = self.config.fabric.semantic_model_name_prefix or ""
        
        for metric_view in metric_views:
            model = self._convert_metric_view_to_model(metric_view, prefix)
            models.append(model)
        
        return models
    
    async def _get_all_metric_views(self) -> list[DatabricksMetricView]:
        """
        Query all Metric Views from the Databricks Unity Catalog.
        
        Uses the system.information_schema tables to discover all
        Metric View objects in the configured catalog.
        
        Returns:
            list[DatabricksMetricView]: All metric views in the catalog.
        """
        _catalog_name = self.config.databricks.default_catalog  # noqa: F841

        # TODO: Implement actual Databricks query using SDK
        # 
        # The query would look something like:
        # SELECT 
        #     metric_view_name,
        #     schema_name,
        #     comment,
        #     created,
        #     last_altered
        # FROM system.information_schema.metric_views
        # WHERE catalog_name = '{catalog_name}'
        #
        # Then for each metric view, query:
        # SELECT * FROM system.information_schema.metric_view_columns
        # SELECT * FROM system.information_schema.metric_view_measures
        
        # Placeholder implementation - returns empty list
        # Real implementation would query Databricks using:
        # self._client.statement.execute(sql=query, warehouse_id=...).result.as_dict()
        
        return []
    
    async def _get_metric_view_details(
        self, 
        catalog_name: str,
        schema_name: str,
        metric_view_name: str
    ) -> DatabricksMetricView:
        """
        Get detailed information about a specific Metric View.
        
        Args:
            catalog_name: The Unity Catalog name.
            schema_name: The schema containing the metric view.
            metric_view_name: The metric view name.
        
        Returns:
            DatabricksMetricView: Detailed metric view information.
        """
        # TODO: Query metric view metadata
        # Query dimensions:
        # SELECT column_name, data_type, comment
        # FROM system.information_schema.metric_view_columns  
        # WHERE catalog_name = ? AND schema_name = ? AND metric_view_name = ?
        #
        # Query metrics:
        # SELECT metric_name, expression, aggregation, comment
        # FROM system.information_schema.metric_view_measures
        # WHERE catalog_name = ? AND schema_name = ? AND metric_view_name = ?
        
        return DatabricksMetricView(
            name=metric_view_name,
            catalog_name=catalog_name,
            schema_name=schema_name,
            description=None,
            source_table="",
            source_schema=schema_name,
            metrics=[],
            dimensions=[]
        )
    
    def _convert_metric_view_to_model(
        self, 
        metric_view: DatabricksMetricView,
        prefix: str
    ) -> IntermediateSemanticModel:
        """
        Convert a Databricks Metric View to an intermediate semantic model.
        
        The model name is formed by combining the prefix with the metric view name.
        For example, with prefix "prod_" and metric view "SalesMetrics",
        the resulting model name would be "prod_SalesMetrics".
        
        Args:
            metric_view: The Databricks Metric View to convert.
            prefix: The prefix to add to the model name.
        
        Returns:
            IntermediateSemanticModel: The Fabric semantic model representation.
        """
        # Create model name with prefix
        model_name = f"{prefix}{metric_view.name}"

        # Convert dimensions to columns
        columns = [
            IntermediateColumn(
                name=dim.name,
                data_type=self._infer_data_type_from_expr(dim.expr),
                description=dim.comment,
                source_column=dim.expr,
            )
            for dim in metric_view.dimensions
        ]

        # Convert measures to intermediate measures
        measures = [
            IntermediateMeasure(
                name=measure.name,
                expression=self._convert_to_dax(measure.expr),
                description=measure.comment,
                source_definition=measure.expr,
                aggregation_type=self._infer_aggregation(measure.expr),
            )
            for measure in metric_view.measures
        ]

        # Extract source table from the source field (catalog.schema.table format)
        source_parts = metric_view.source.split(".")
        source_schema = source_parts[1] if len(source_parts) > 1 else ""
        source_table = source_parts[2] if len(source_parts) > 2 else metric_view.source

        # Create the main table from the metric view
        table = IntermediateTable(
            name=metric_view.name or "metrics",
            description=metric_view.comment,
            columns=columns,
            measures=measures,
            source_schema=source_schema,
            source_table=source_table,
        )

        return IntermediateSemanticModel(
            name=model_name,
            description=f"Semantic model from Databricks Metric View: {metric_view.name}",
            tables=[table],
            relationships=[],
            source_system="DATABRICKS",
            source_name=f"{metric_view.catalog_name}.{metric_view.schema_name}.{metric_view.name}",
        )

    def _infer_data_type_from_expr(self, expr: str) -> DataType:
        """Infer data type from expression (best effort)."""
        expr_lower = expr.lower()
        if any(kw in expr_lower for kw in ["date", "time", "timestamp"]):
            return DataType.DATETIME
        if any(kw in expr_lower for kw in ["int", "count", "number"]):
            return DataType.INTEGER
        if any(kw in expr_lower for kw in ["decimal", "float", "double", "sum", "avg"]):
            return DataType.DECIMAL
        if any(kw in expr_lower for kw in ["bool"]):
            return DataType.BOOLEAN
        return DataType.STRING

    def _infer_aggregation(self, expr: str) -> str | None:
        """Infer aggregation type from expression."""
        expr_upper = expr.upper()
        if expr_upper.startswith("SUM("):
            return "SUM"
        if expr_upper.startswith("COUNT("):
            return "COUNT"
        if expr_upper.startswith("AVG("):
            return "AVERAGE"
        if expr_upper.startswith("MIN("):
            return "MIN"
        if expr_upper.startswith("MAX("):
            return "MAX"
        return None

    def _convert_to_dax(self, expr: str) -> str:
        """Convert SQL expression to DAX (basic conversion)."""
        # For now, return the expression as-is
        # TODO: Implement proper SQL to DAX conversion
        return expr

    def _map_data_type(self, databricks_type: str) -> DataType:
        """Map Databricks data type to intermediate data type."""
        type_mapping = {
            "STRING": DataType.STRING,
            "INT": DataType.INTEGER,
            "BIGINT": DataType.INTEGER,
            "DOUBLE": DataType.DOUBLE,
            "FLOAT": DataType.DOUBLE,
            "DECIMAL": DataType.DECIMAL,
            "BOOLEAN": DataType.BOOLEAN,
            "DATE": DataType.DATE,
            "TIMESTAMP": DataType.DATETIME,
        }
        return type_mapping.get(databricks_type.upper(), DataType.STRING)

    def _map_aggregation(self, aggregation: str | None) -> AggregationType | None:
        """Map Databricks aggregation to intermediate aggregation type."""
        if not aggregation:
            return None

        agg_mapping = {
            "SUM": AggregationType.SUM,
            "COUNT": AggregationType.COUNT,
            "COUNT_DISTINCT": AggregationType.DISTINCTCOUNT,
            "AVG": AggregationType.AVERAGE,
            "MIN": AggregationType.MIN,
            "MAX": AggregationType.MAX,
        }
        return agg_mapping.get(aggregation.upper(), AggregationType.NONE)
