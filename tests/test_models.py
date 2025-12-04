"""
Tests for Semantic Weaver models.
"""

import pytest
from semanticweaver.models.base import (
    FabricConfig,
    ServicePrincipalConfig,
    SourceConfig,
    SourceType
)
from semanticweaver.models.intermediate import (
    IntermediateSemanticModel,
    IntermediateTable,
    IntermediateColumn,
    IntermediateMeasure,
    DataType,
    AggregationType
)


class TestFabricConfig:
    """Tests for FabricConfig model."""
    
    def test_fabric_config_creation(self):
        """Test creating a FabricConfig instance."""
        config = FabricConfig(
            workspace_id="test-workspace-id",
            tenant_id="test-tenant-id"
        )
        assert config.workspace_id == "test-workspace-id"
        assert config.tenant_id == "test-tenant-id"


class TestIntermediateModels:
    """Tests for intermediate representation models."""
    
    def test_intermediate_column_creation(self):
        """Test creating an IntermediateColumn."""
        column = IntermediateColumn(
            name="test_column",
            data_type=DataType.STRING,
            description="A test column"
        )
        assert column.name == "test_column"
        assert column.data_type == DataType.STRING
    
    def test_intermediate_measure_creation(self):
        """Test creating an IntermediateMeasure."""
        measure = IntermediateMeasure(
            name="Total Sales",
            expression="SUM(Sales[Amount])",
            description="Sum of all sales"
        )
        assert measure.name == "Total Sales"
        assert "SUM" in measure.expression
    
    def test_intermediate_table_creation(self):
        """Test creating an IntermediateTable with columns and measures."""
        column = IntermediateColumn(name="id", data_type=DataType.INTEGER)
        measure = IntermediateMeasure(name="Count", expression="COUNT(*)")
        
        table = IntermediateTable(
            name="Sales",
            columns=[column],
            measures=[measure]
        )
        
        assert table.name == "Sales"
        assert len(table.columns) == 1
        assert len(table.measures) == 1
    
    def test_intermediate_semantic_model_creation(self):
        """Test creating a complete IntermediateSemanticModel."""
        table = IntermediateTable(
            name="Sales",
            columns=[IntermediateColumn(name="id", data_type=DataType.INTEGER)],
            measures=[]
        )
        
        model = IntermediateSemanticModel(
            name="Test Model",
            tables=[table],
            source_system="DATABRICKS"
        )
        
        assert model.name == "Test Model"
        assert len(model.tables) == 1
        assert model.source_system == "DATABRICKS"
    
    def test_get_all_measures(self):
        """Test getting all measures from a model."""
        measure1 = IntermediateMeasure(name="M1", expression="SUM(A)")
        measure2 = IntermediateMeasure(name="M2", expression="SUM(B)")
        
        table1 = IntermediateTable(name="T1", columns=[], measures=[measure1])
        table2 = IntermediateTable(name="T2", columns=[], measures=[measure2])
        
        model = IntermediateSemanticModel(
            name="Test",
            tables=[table1, table2],
            source_system="TEST"
        )
        
        all_measures = model.get_all_measures()
        assert len(all_measures) == 2
