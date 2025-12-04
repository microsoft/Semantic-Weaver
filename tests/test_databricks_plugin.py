"""
Tests for Databricks plugin.
"""

import pytest
from semanticweaver.plugins.databricks.model import (
    DatabricksConfig,
    DatabricksSourceMap,
    DatabricksMetricDefinition,
    DatabricksDimension
)
from semanticweaver.plugins.databricks.plugin import DatabricksPlugin
from semanticweaver.models.base import FabricConfig, ServicePrincipalConfig, SourceConfig, SourceType


class TestDatabricksConfig:
    """Tests for Databricks configuration models."""
    
    def test_databricks_config_creation(self):
        """Test creating a DatabricksConfig instance."""
        config = DatabricksConfig(
            workspace_url="https://adb-123.azuredatabricks.net/",
            account_id="test-account-id",
            account_api_token="test-token"
        )
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
            source=SourceConfig(
                name="test-catalog",
                type=SourceType.DATABRICKS
            ),
            databricks=DatabricksConfig(
                workspace_url="https://adb-123.azuredatabricks.net/",
                account_id="test-account-id",
                account_api_token="test-token"
            )
        )
        assert config.source.name == "test-catalog"
        assert config.databricks.workspace_url == "https://adb-123.azuredatabricks.net/"


class TestDatabricksMetricModels:
    """Tests for Databricks metric definition models."""
    
    def test_metric_definition_creation(self):
        """Test creating a DatabricksMetricDefinition."""
        metric = DatabricksMetricDefinition(
            name="total_revenue",
            expression="SUM(amount)",
            table_name="sales",
            aggregation="SUM"
        )
        assert metric.name == "total_revenue"
        assert metric.aggregation == "SUM"
    
    def test_dimension_creation(self):
        """Test creating a DatabricksDimension."""
        dimension = DatabricksDimension(
            name="product_category",
            column_name="category",
            data_type="STRING"
        )
        assert dimension.name == "product_category"
        assert dimension.data_type == "STRING"


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
            source=SourceConfig(
                name="test-catalog",
                type=SourceType.DATABRICKS
            ),
            databricks=DatabricksConfig(
                workspace_url="https://adb-123.azuredatabricks.net/",
                account_id="test-account-id",
                account_api_token="test-token"
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
