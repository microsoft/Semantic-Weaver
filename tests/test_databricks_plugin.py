"""
Tests for Databricks plugin.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from semanticweaver.plugins.databricks.model import (
    DatabricksConfig,
    DatabricksSourceMap,
    DatabricksMeasure,
    DatabricksDimension,
    DatabricksMetricView,
    CatalogConfig,
)
from semanticweaver.plugins.databricks.plugin import DatabricksPlugin, AuthenticationError
from semanticweaver.models.base import FabricConfig, ServicePrincipalConfig


class TestDatabricksConfig:
    """Tests for Databricks configuration models."""
    
    def test_databricks_config_creation(self):
        """Test creating a DatabricksConfig instance."""
        config = DatabricksConfig(
            workspace_url="https://adb-123.azuredatabricks.net/",
            account_id="test-account-id",
            account_api_token="test-token",
            catalogs=[CatalogConfig(name="test-catalog")]
        )
        assert config.default_catalog == "test-catalog"
        assert config.workspace_url == "https://adb-123.azuredatabricks.net/"
        assert config.account_id == "test-account-id"
    
    def test_databricks_source_map_creation(self):
        """Test creating a DatabricksSourceMap instance."""
        config = DatabricksSourceMap(
            fabric=FabricConfig(
                workspace_id="fabric-ws-id",
                tenant_id="tenant-id"
            ),
            service_principal=ServicePrincipalConfig(
                client_id="client-id",
                client_secret="client-secret",
                tenant_id="tenant-id"
            ),
            databricks=DatabricksConfig(
                workspace_url="https://adb-123.azuredatabricks.net/",
                account_id="test-account-id",
                account_api_token="test-token",
                catalogs=[CatalogConfig(name="test-catalog")]
            )
        )
        assert config.databricks.default_catalog == "test-catalog"
        assert config.databricks.workspace_url == "https://adb-123.azuredatabricks.net/"
    
    def test_semantic_model_name_prefix(self):
        """Test setting semantic_model_name_prefix in FabricConfig."""
        config = DatabricksSourceMap(
            fabric=FabricConfig(
                workspace_id="fabric-ws-id",
                tenant_id="tenant-id",
                semantic_model_name_prefix="prod_"
            ),
            service_principal=ServicePrincipalConfig(
                client_id="client-id",
                client_secret="client-secret",
                tenant_id="tenant-id"
            ),
            databricks=DatabricksConfig(
                workspace_url="https://adb-123.azuredatabricks.net/",
                account_id="test-account-id",
                account_api_token="test-token",
                catalogs=[CatalogConfig(name="test-catalog")]
            )
        )
        assert config.fabric.semantic_model_name_prefix == "prod_"


class TestDatabricksMetricModels:
    """Tests for Databricks metric definition models."""
    
    def test_metric_definition_creation(self):
        """Test creating a DatabricksMeasure (measure definition)."""
        measure = DatabricksMeasure(
            name="total_revenue",
            expr="SUM(amount)",
            comment="Total revenue from all sales",
            display_name="Total Revenue",
            synonyms=["revenue", "total sales"]
        )
        assert measure.name == "total_revenue"
        assert measure.expr == "SUM(amount)"
        assert measure.display_name == "Total Revenue"
        assert len(measure.synonyms) == 2
    
    def test_dimension_creation(self):
        """Test creating a DatabricksDimension."""
        dimension = DatabricksDimension(
            name="product_category",
            expr="category",
            comment="Product category for grouping",
            display_name="Product Category",
            synonyms=["category", "product type"]
        )
        assert dimension.name == "product_category"
        assert dimension.expr == "category"
        assert dimension.display_name == "Product Category"
    
    def test_metric_view_creation(self):
        """Test creating a DatabricksMetricView with YAML v1.1 structure."""
        metric_view = DatabricksMetricView(
            version="1.1",
            source="main.analytics.sales_facts",
            comment="Sales metrics view",
            name="SalesMetrics",
            catalog_name="main",
            schema_name="analytics",
            measures=[
                DatabricksMeasure(
                    name="total_sales",
                    expr="SUM(amount)",
                    display_name="Total Sales"
                )
            ],
            dimensions=[
                DatabricksDimension(
                    name="region",
                    expr="region_name",
                    display_name="Region"
                )
            ],
            filter="amount > 0"
        )
        assert metric_view.name == "SalesMetrics"
        assert metric_view.catalog_name == "main"
        assert metric_view.source == "main.analytics.sales_facts"
        assert metric_view.version == "1.1"
        assert len(metric_view.measures) == 1
        assert len(metric_view.dimensions) == 1
        assert metric_view.filter == "amount > 0"


class TestDatabricksPlugin:
    """Tests for DatabricksPlugin class."""
    
    @pytest.fixture
    def sample_config(self):
        """Create a sample configuration for testing."""
        return DatabricksSourceMap(
            fabric=FabricConfig(
                workspace_id="fabric-ws-id",
                tenant_id="tenant-id"
            ),
            service_principal=ServicePrincipalConfig(
                client_id="client-id",
                client_secret="client-secret",
                tenant_id="tenant-id"
            ),
            databricks=DatabricksConfig(
                workspace_url="https://adb-123.azuredatabricks.net/",
                account_id="test-account-id",
                account_api_token="test-token",
                catalogs=[CatalogConfig(name="test-catalog")]
            )
        )
    
    @pytest.fixture
    def config_with_prefix(self):
        """Create a configuration with semantic model name prefix."""
        return DatabricksSourceMap(
            fabric=FabricConfig(
                workspace_id="fabric-ws-id",
                tenant_id="tenant-id",
                semantic_model_name_prefix="prod_"
            ),
            service_principal=ServicePrincipalConfig(
                client_id="client-id",
                client_secret="client-secret",
                tenant_id="tenant-id"
            ),
            databricks=DatabricksConfig(
                workspace_url="https://adb-123.azuredatabricks.net/",
                account_id="test-account-id",
                account_api_token="test-token",
                catalogs=[CatalogConfig(name="test-catalog")]
            )
        )
    
    def test_plugin_initialization(self, sample_config):
        """Test initializing the DatabricksPlugin."""
        plugin = DatabricksPlugin(sample_config)
        assert plugin.config == sample_config
        assert not plugin.is_authenticated
    
    def test_get_plugin_from_config(self, sample_config):
        """Test getting plugin instance from configuration."""
        plugin = sample_config.get_plugin()
        assert isinstance(plugin, DatabricksPlugin)
    
    def test_convert_metric_view_to_model_with_prefix(self, config_with_prefix):
        """Test that metric view conversion applies the prefix."""
        plugin = DatabricksPlugin(config_with_prefix)
        
        metric_view = DatabricksMetricView(
            source="main.analytics.sales_facts",
            name="SalesMetrics",
            catalog_name="main",
            schema_name="analytics"
        )
        
        model = plugin._convert_metric_view_to_model(metric_view, "prod_")
        
        assert model.name == "prod_SalesMetrics"
        assert model.source_system == "DATABRICKS"
        assert "SalesMetrics" in model.source_name
    
    def test_convert_metric_view_to_model_without_prefix(self, sample_config):
        """Test that metric view conversion works without prefix."""
        plugin = DatabricksPlugin(sample_config)
        
        metric_view = DatabricksMetricView(
            source="main.analytics.sales_facts",
            name="SalesMetrics",
            catalog_name="main",
            schema_name="analytics"
        )
        
        model = plugin._convert_metric_view_to_model(metric_view, "")
        
        assert model.name == "SalesMetrics"


class TestDatabricksConnection:
    """Tests for Databricks connection functionality."""
    
    @pytest.fixture
    def sample_config(self):
        """Create a sample configuration for testing."""
        return DatabricksSourceMap(
            fabric=FabricConfig(
                workspace_id="fabric-ws-id",
                tenant_id="tenant-id"
            ),
            service_principal=ServicePrincipalConfig(
                client_id="client-id",
                client_secret="client-secret",
                tenant_id="tenant-id"
            ),
            databricks=DatabricksConfig(
                workspace_url="https://adb-123.azuredatabricks.net/",
                account_id="test-account-id",
                account_api_token="test-token",
                catalogs=[CatalogConfig(name="main")]
            )
        )
    
    def test_plugin_not_authenticated_initially(self, sample_config):
        """Test that plugin is not authenticated on initialization."""
        plugin = DatabricksPlugin(sample_config)
        assert not plugin.is_authenticated
        assert plugin._client is None
    
    def test_client_property_raises_when_not_authenticated(self, sample_config):
        """Test that accessing client raises error when not authenticated."""
        plugin = DatabricksPlugin(sample_config)
        with pytest.raises(AuthenticationError, match="Not authenticated"):
            _ = plugin.client
    
    @pytest.mark.asyncio
    async def test_authenticate_success(self, sample_config):
        """Test successful authentication to Databricks."""
        plugin = DatabricksPlugin(sample_config)
        
        # Mock the WorkspaceClient
        mock_user = Mock()
        mock_user.user_name = "test@example.com"
        
        mock_client = Mock()
        mock_client.current_user.me.return_value = mock_user
        
        with patch("semanticweaver.plugins.databricks.plugin.WorkspaceClient", return_value=mock_client):
            await plugin.authenticate()
        
        assert plugin.is_authenticated
        assert plugin._client is not None
    
    @pytest.mark.asyncio
    async def test_authenticate_failure(self, sample_config):
        """Test authentication failure raises AuthenticationError."""
        plugin = DatabricksPlugin(sample_config)
        
        with patch("semanticweaver.plugins.databricks.plugin.WorkspaceClient") as mock_ws:
            mock_ws.side_effect = Exception("Invalid token")
            
            with pytest.raises(AuthenticationError, match="Failed to authenticate"):
                await plugin.authenticate()
        
        assert not plugin.is_authenticated
    
    @pytest.mark.asyncio
    async def test_authenticate_strips_trailing_slash(self, sample_config):
        """Test that workspace URL trailing slash is stripped."""
        sample_config.databricks.workspace_url = "https://adb-123.azuredatabricks.net/"
        plugin = DatabricksPlugin(sample_config)
        
        mock_user = Mock()
        mock_client = Mock()
        mock_client.current_user.me.return_value = mock_user
        
        with patch("semanticweaver.plugins.databricks.plugin.WorkspaceClient", return_value=mock_client) as mock_ws:
            await plugin.authenticate()
            
            # Verify the URL passed to WorkspaceClient has no trailing slash
            mock_ws.assert_called_once_with(
                host="https://adb-123.azuredatabricks.net",
                token="test-token"
            )
    
    @pytest.mark.asyncio
    async def test_get_available_catalogs(self, sample_config):
        """Test listing available catalogs filtered by configuration."""
        # Add analytics catalog to config
        sample_config.databricks.catalogs.append(CatalogConfig(name="analytics"))
        plugin = DatabricksPlugin(sample_config)
        
        # Create mock catalogs (simulating what's available in Databricks)
        mock_catalog1 = Mock()
        mock_catalog1.name = "main"
        mock_catalog2 = Mock()
        mock_catalog2.name = "analytics"
        mock_catalog3 = Mock()
        mock_catalog3.name = "other"  # Not in config, should be filtered out
        
        mock_client = Mock()
        mock_client.current_user.me.return_value = Mock()
        mock_client.catalogs.list.return_value = [mock_catalog1, mock_catalog2, mock_catalog3]
        
        with patch("semanticweaver.plugins.databricks.plugin.WorkspaceClient", return_value=mock_client):
            await plugin.authenticate()
            catalogs = await plugin.get_available_catalogs()
        
        # Should only return configured catalogs in config order
        assert catalogs == ["main", "analytics"]
    
    @pytest.mark.asyncio
    async def test_list_schemas(self, sample_config):
        """Test listing schemas in a catalog."""
        plugin = DatabricksPlugin(sample_config)
        
        # Create mock schemas
        mock_schema1 = Mock()
        mock_schema1.name = "default"
        mock_schema2 = Mock()
        mock_schema2.name = "analytics"
        
        mock_client = Mock()
        mock_client.current_user.me.return_value = Mock()
        mock_client.schemas.list.return_value = [mock_schema1, mock_schema2]
        
        with patch("semanticweaver.plugins.databricks.plugin.WorkspaceClient", return_value=mock_client):
            await plugin.authenticate()
            schemas = await plugin.list_schemas()
        
        # No schemas configured means all schemas returned
        assert len(schemas) == 2
        mock_client.schemas.list.assert_called_once_with(catalog_name="main")

    @pytest.mark.asyncio
    async def test_list_schemas_with_filter(self, sample_config):
        """Test listing schemas filtered by configuration."""
        # Configure specific schemas for the catalog
        sample_config.databricks.catalogs[0].schemas = ["default"]
        plugin = DatabricksPlugin(sample_config)
        
        # Create mock schemas (simulating what's available in Databricks)
        mock_schema1 = Mock()
        mock_schema1.name = "default"
        mock_schema2 = Mock()
        mock_schema2.name = "analytics"  # Not in config, should be filtered out
        mock_schema3 = Mock()
        mock_schema3.name = "other"  # Not in config, should be filtered out
        
        mock_client = Mock()
        mock_client.current_user.me.return_value = Mock()
        mock_client.schemas.list.return_value = [mock_schema1, mock_schema2, mock_schema3]
        
        with patch("semanticweaver.plugins.databricks.plugin.WorkspaceClient", return_value=mock_client):
            await plugin.authenticate()
            schemas = await plugin.list_schemas()
        
        # Should only return configured schemas
        assert len(schemas) == 1
        assert schemas[0].name == "default"
        mock_client.schemas.list.assert_called_once_with(catalog_name="main")
    
    @pytest.mark.asyncio
    async def test_validate_connection_success(self, sample_config):
        """Test successful connection validation."""
        plugin = DatabricksPlugin(sample_config)
        
        mock_catalog = Mock()
        mock_catalog.name = "main"
        
        mock_client = Mock()
        mock_client.current_user.me.return_value = Mock()
        mock_client.catalogs.get.return_value = mock_catalog
        
        with patch("semanticweaver.plugins.databricks.plugin.WorkspaceClient", return_value=mock_client):
            is_valid = await plugin.validate_connection()
        
        assert is_valid
        mock_client.catalogs.get.assert_called_once_with("main")
    
    @pytest.mark.asyncio
    async def test_validate_connection_failure(self, sample_config):
        """Test connection validation failure."""
        plugin = DatabricksPlugin(sample_config)
        
        mock_client = Mock()
        mock_client.current_user.me.return_value = Mock()
        mock_client.catalogs.get.side_effect = Exception("Catalog not found")
        
        with patch("semanticweaver.plugins.databricks.plugin.WorkspaceClient", return_value=mock_client):
            is_valid = await plugin.validate_connection()
        
        assert not is_valid
    
    @pytest.mark.asyncio
    async def test_get_catalog_info(self, sample_config):
        """Test getting catalog information."""
        plugin = DatabricksPlugin(sample_config)
        
        mock_catalog = Mock()
        mock_catalog.name = "main"
        mock_catalog.comment = "Main catalog"
        
        mock_client = Mock()
        mock_client.current_user.me.return_value = Mock()
        mock_client.catalogs.get.return_value = mock_catalog
        
        with patch("semanticweaver.plugins.databricks.plugin.WorkspaceClient", return_value=mock_client):
            catalog_info = await plugin.get_catalog_info()
        
        assert catalog_info is not None
        assert catalog_info.name == "main"

    @pytest.mark.asyncio
    async def test_list_metric_views(self, sample_config):
        """Test listing metric views from a catalog and schema."""
        from databricks.sdk.service.catalog import TableType
        
        plugin = DatabricksPlugin(sample_config)
        
        # Create mock tables - some are METRIC_VIEW, some are not
        # METRIC_VIEW tables need view_definition for parsing
        mock_table1 = Mock()
        mock_table1.name = "sales_metrics"
        mock_table1.full_name = "main.default.sales_metrics"
        mock_table1.catalog_name = "main"
        mock_table1.schema_name = "default"
        mock_table1.comment = "Sales metrics"
        mock_table1.table_type = TableType.METRIC_VIEW
        mock_table1.view_definition = """version: 1
source: main.default.sales_facts
filter: is_active = true
dimensions:
  - name: region
    expr: region_code
measures:
  - name: total_sales
    agg: sum
    expr: amount
"""
        
        mock_table2 = Mock()
        mock_table2.name = "raw_sales"
        mock_table2.full_name = "main.default.raw_sales"
        mock_table2.table_type = TableType.MANAGED
        
        mock_table3 = Mock()
        mock_table3.name = "customer_metrics"
        mock_table3.full_name = "main.default.customer_metrics"
        mock_table3.catalog_name = "main"
        mock_table3.schema_name = "default"
        mock_table3.comment = "Customer metrics"
        mock_table3.table_type = TableType.METRIC_VIEW
        mock_table3.view_definition = """version: 1
source: main.default.customers
dimensions:
  - name: segment
    expr: customer_segment
measures:
  - name: customer_count
    agg: count
    expr: customer_id
"""
        
        mock_client = Mock()
        mock_client.current_user.me.return_value = Mock()
        mock_client.tables.list.return_value = [mock_table1, mock_table2, mock_table3]
        
        with patch("semanticweaver.plugins.databricks.plugin.WorkspaceClient", return_value=mock_client):
            await plugin.authenticate()
            metric_views = await plugin.list_metric_views("main", "default")
        
        # Should only return METRIC_VIEW tables
        assert len(metric_views) == 2
        
        # Check first metric view
        assert metric_views[0].name == "sales_metrics"
        assert metric_views[0].source == "main.default.sales_facts"
        assert metric_views[0].filter == "is_active = true"
        assert len(metric_views[0].dimensions) == 1
        assert metric_views[0].dimensions[0].name == "region"
        assert len(metric_views[0].measures) == 1
        assert metric_views[0].measures[0].name == "total_sales"
        
        # Check second metric view
        assert metric_views[1].name == "customer_metrics"
        assert metric_views[1].source == "main.default.customers"
        
        # Verify tables.list was called with correct params
        mock_client.tables.list.assert_called_once_with(
            catalog_name="main",
            schema_name="default",
            omit_columns=False,
            omit_properties=False
        )

    @pytest.mark.asyncio
    async def test_list_metric_views_empty(self, sample_config):
        """Test listing metric views when none exist."""
        from databricks.sdk.service.catalog import TableType
        
        plugin = DatabricksPlugin(sample_config)
        
        # Only non-metric-view tables
        mock_table = Mock()
        mock_table.name = "raw_data"
        mock_table.full_name = "main.default.raw_data"
        mock_table.table_type = TableType.MANAGED
        
        mock_client = Mock()
        mock_client.current_user.me.return_value = Mock()
        mock_client.tables.list.return_value = [mock_table]
        
        with patch("semanticweaver.plugins.databricks.plugin.WorkspaceClient", return_value=mock_client):
            await plugin.authenticate()
            metric_views = await plugin.list_metric_views("main", "default")
        
        assert len(metric_views) == 0


class TestLoadConfigFromYaml:
    """Tests for loading configuration from YAML files."""
    
    def test_load_databricks_source_map_from_yaml(self, tmp_path):
        """Test loading DatabricksSourceMap from a YAML file."""
        config_content = """
fabric:
  workspace_id: "test-workspace-id"
  tenant_id: "test-tenant-id"
  semantic_model_name_prefix: "sw_"

service_principal:
  client_id: "test-client-id"
  client_secret: "test-client-secret"
  tenant_id: "test-tenant-id"

databricks:
  workspace_url: "https://adb-123.azuredatabricks.net/"
  account_id: "test-account-id"
  account_api_token: "test-token"
  catalogs:
    - name: "main"
"""
        config_file = tmp_path / "config.yml"
        config_file.write_text(config_content)
        
        config = DatabricksSourceMap.from_yaml(str(config_file))
        
        assert config.fabric.workspace_id == "test-workspace-id"
        assert config.fabric.semantic_model_name_prefix == "sw_"
        assert config.databricks.default_catalog == "main"
        assert config.databricks.workspace_url == "https://adb-123.azuredatabricks.net/"
    
    def test_load_config_file_not_found(self):
        """Test that FileNotFoundError is raised for missing config file."""
        with pytest.raises(FileNotFoundError):
            DatabricksSourceMap.from_yaml("/nonexistent/path/config.yml")
    
    def test_get_plugin_from_loaded_config(self, tmp_path):
        """Test getting plugin from YAML-loaded configuration."""
        config_content = """
fabric:
  workspace_id: "test-workspace-id"
  tenant_id: "test-tenant-id"

service_principal:
  client_id: "test-client-id"
  client_secret: "test-client-secret"
  tenant_id: "test-tenant-id"

databricks:
  workspace_url: "https://adb-123.azuredatabricks.net/"
  account_id: "test-account-id"
  account_api_token: "test-token"
  catalogs:
    - name: "main"
"""
        config_file = tmp_path / "config.yml"
        config_file.write_text(config_content)
        
        config = DatabricksSourceMap.from_yaml(str(config_file))
        plugin = config.get_plugin()
        
        assert isinstance(plugin, DatabricksPlugin)
        assert plugin.config.databricks.default_catalog == "main"
