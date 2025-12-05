"""
Unit tests for the SemanticModelTransformer class.
"""

import pytest

from semanticweaver.core.transformer import SemanticModelTransformer, TransformationError
from semanticweaver.models.intermediate import (
    AggregationType,
    DataType,
    IntermediateColumn,
    IntermediateMeasure,
    IntermediateRelationship,
    IntermediateSemanticModel,
    IntermediateTable,
    RelationshipCardinality,
)
from semanticweaver.plugins.databricks.model import (
    CurrencyFormat,
    DatabricksDimension,
    DatabricksMeasure,
    DatabricksMetricView,
    DateFormat,
    DecimalPlaces,
    NumberFormat,
    PercentageFormat,
    WindowSpecification,
)


class TestSemanticModelTransformer:
    """Tests for SemanticModelTransformer."""

    def test_transform_unsupported_model_type(self):
        """Test that unsupported model types raise TransformationError."""
        transformer = SemanticModelTransformer()

        with pytest.raises(TransformationError) as exc_info:
            transformer.transform({"unsupported": "model"})

        assert "Unsupported source model type" in str(exc_info.value)
        assert "dict" in str(exc_info.value)

    def test_transform_databricks_metric_view_basic(self):
        """Test basic transformation of a Databricks Metric View."""
        transformer = SemanticModelTransformer()

        metric_view = DatabricksMetricView(
            version="1.1",
            name="orders_metrics",
            source="catalog.schema.orders",
            comment="Order metrics analysis",
            dimensions=[
                DatabricksDimension(
                    name="order_date",
                    expr="o_orderdate",
                    comment="Order date",
                )
            ],
            measures=[
                DatabricksMeasure(
                    name="total_revenue",
                    expr="SUM(o_totalprice)",
                    comment="Total revenue",
                )
            ],
            catalog_name="catalog",
            schema_name="schema",
        )

        result = transformer.transform(metric_view)

        assert isinstance(result, IntermediateSemanticModel)
        assert result.name == "orders_metrics"
        assert result.description == "Order metrics analysis"
        assert result.source_system == "DATABRICKS"
        assert result.source_name == "catalog"
        assert len(result.tables) == 1

    def test_transform_creates_table_with_columns_and_measures(self):
        """Test that transformation creates proper table structure."""
        transformer = SemanticModelTransformer()

        metric_view = DatabricksMetricView(
            version="1.1",
            name="sales_metrics",
            source="catalog.schema.sales",
            dimensions=[
                DatabricksDimension(name="customer_id", expr="customer_id"),
                DatabricksDimension(name="product_id", expr="product_id"),
            ],
            measures=[
                DatabricksMeasure(name="revenue", expr="SUM(amount)"),
                DatabricksMeasure(name="order_count", expr="COUNT(1)"),
            ],
        )

        result = transformer.transform(metric_view)
        table = result.tables[0]

        assert table.name == "sales_metrics"
        assert len(table.columns) == 2
        assert len(table.measures) == 2
        assert table.columns[0].name == "customer_id"
        assert table.columns[1].name == "product_id"
        assert table.measures[0].name == "revenue"
        assert table.measures[1].name == "order_count"


class TestDimensionToColumn:
    """Tests for dimension to column conversion."""

    def test_dimension_basic_conversion(self):
        """Test basic dimension conversion."""
        transformer = SemanticModelTransformer()

        dimension = DatabricksDimension(
            name="customer_name",
            expr="c_name",
            comment="Customer name",
        )

        column = transformer._dimension_to_column(dimension)

        assert column.name == "customer_name"
        assert column.source_column == "c_name"
        assert column.description == "Customer name"
        assert column.data_type == DataType.STRING

    def test_dimension_with_date_format(self):
        """Test dimension with date format infers DateTime type."""
        transformer = SemanticModelTransformer()

        dimension = DatabricksDimension(
            name="order_date",
            expr="o_orderdate",
            format=DateFormat(type="date", date_format="year_month_day"),
        )

        column = transformer._dimension_to_column(dimension)

        assert column.data_type == DataType.DATETIME
        assert column.format_string == "yyyy-MM-dd"

    def test_dimension_with_number_format(self):
        """Test dimension with number format."""
        transformer = SemanticModelTransformer()

        dimension = DatabricksDimension(
            name="quantity",
            expr="qty",
            format=NumberFormat(
                type="number",
                decimal_places=DecimalPlaces(type="exact", places=0),
            ),
        )

        column = transformer._dimension_to_column(dimension)

        assert column.data_type == DataType.DOUBLE
        assert column.format_string == "#,##0"

    def test_dimension_infers_date_from_expression(self):
        """Test that date-related expressions infer DateTime type."""
        transformer = SemanticModelTransformer()

        dimension = DatabricksDimension(
            name="month",
            expr="DATE_TRUNC('MONTH', order_date)",
        )

        column = transformer._dimension_to_column(dimension)

        assert column.data_type == DataType.DATETIME


class TestMeasureToIntermediate:
    """Tests for measure to intermediate measure conversion."""

    def test_measure_basic_conversion(self):
        """Test basic measure conversion."""
        transformer = SemanticModelTransformer()

        measure = DatabricksMeasure(
            name="total_sales",
            expr="SUM(amount)",
            comment="Total sales amount",
        )

        result = transformer._measure_to_intermediate(measure)

        assert result.name == "total_sales"
        assert result.description == "Total sales amount"
        assert result.source_definition == "SUM(amount)"
        assert result.aggregation_type == AggregationType.SUM

    def test_measure_with_currency_format(self):
        """Test measure with currency format."""
        transformer = SemanticModelTransformer()

        measure = DatabricksMeasure(
            name="revenue",
            expr="SUM(price)",
            format=CurrencyFormat(
                type="currency",
                currency_code="USD",
                decimal_places=DecimalPlaces(type="exact", places=2),
            ),
        )

        result = transformer._measure_to_intermediate(measure)

        assert result.format_string == "$#,##0.00"

    def test_measure_with_percentage_format(self):
        """Test measure with percentage format."""
        transformer = SemanticModelTransformer()

        measure = DatabricksMeasure(
            name="margin_rate",
            expr="SUM(margin) / SUM(revenue)",
            format=PercentageFormat(
                type="percentage",
                decimal_places=DecimalPlaces(type="exact", places=1),
            ),
        )

        result = transformer._measure_to_intermediate(measure)

        assert result.format_string == "0.0%"


class TestSqlToDaxConversion:
    """Tests for SQL to DAX expression conversion."""

    def test_sum_expression(self):
        """Test SUM conversion."""
        transformer = SemanticModelTransformer()

        result = transformer._sql_to_dax_expression("SUM(amount)", "test")

        assert result == "SUM([amount])"

    def test_count_expression(self):
        """Test COUNT conversion."""
        transformer = SemanticModelTransformer()

        result = transformer._sql_to_dax_expression("COUNT(order_id)", "test")

        assert result == "COUNT([order_id])"

    def test_count_star_expression(self):
        """Test COUNT(*) conversion to COUNTROWS."""
        transformer = SemanticModelTransformer()

        result = transformer._sql_to_dax_expression("COUNT(*)", "test")

        assert result == "COUNTROWS()"

    def test_count_one_expression(self):
        """Test COUNT(1) conversion to COUNTROWS."""
        transformer = SemanticModelTransformer()

        result = transformer._sql_to_dax_expression("COUNT(1)", "test")

        assert result == "COUNTROWS()"

    def test_count_distinct_expression(self):
        """Test COUNT(DISTINCT x) conversion to DISTINCTCOUNT."""
        transformer = SemanticModelTransformer()

        result = transformer._sql_to_dax_expression("COUNT(DISTINCT customer_id)", "test")

        assert result == "DISTINCTCOUNT([customer_id])"

    def test_avg_expression(self):
        """Test AVG conversion to AVERAGE."""
        transformer = SemanticModelTransformer()

        result = transformer._sql_to_dax_expression("AVG(price)", "test")

        assert result == "AVERAGE([price])"

    def test_min_max_expressions(self):
        """Test MIN and MAX conversions."""
        transformer = SemanticModelTransformer()

        assert transformer._sql_to_dax_expression("MIN(date)", "test") == "MIN([date])"
        assert transformer._sql_to_dax_expression("MAX(date)", "test") == "MAX([date])"

    def test_complex_expression_with_division(self):
        """Test complex expression with division."""
        transformer = SemanticModelTransformer()

        result = transformer._sql_to_dax_expression(
            "SUM(revenue) / COUNT(DISTINCT customer_id)", "test"
        )

        assert "SUM([revenue])" in result
        assert "DISTINCTCOUNT([customer_id])" in result


class TestQualifyColumn:
    """Tests for column qualification."""

    def test_simple_column(self):
        """Test simple column qualification."""
        transformer = SemanticModelTransformer()

        result = transformer._qualify_column("amount")

        assert result == "[amount]"

    def test_already_qualified_column(self):
        """Test already qualified column."""
        transformer = SemanticModelTransformer()

        result = transformer._qualify_column("[amount]")

        assert result == "[amount]"

    def test_table_qualified_column(self):
        """Test table.column notation."""
        transformer = SemanticModelTransformer()

        result = transformer._qualify_column("Sales.amount")

        assert result == "'Sales'[amount]"


class TestFormatConversions:
    """Tests for format specification conversions."""

    def test_number_format_to_dax(self):
        """Test number format to DAX format string."""
        transformer = SemanticModelTransformer()

        format_spec = NumberFormat(
            type="number",
            decimal_places=DecimalPlaces(type="exact", places=2),
            hide_group_separator=False,
        )

        result = transformer._number_to_dax_format(format_spec)

        assert result == "#,##0.00"

    def test_number_format_no_decimals(self):
        """Test number format without decimals."""
        transformer = SemanticModelTransformer()

        format_spec = NumberFormat(
            type="number",
            decimal_places=DecimalPlaces(type="exact", places=0),
        )

        result = transformer._number_to_dax_format(format_spec)

        assert result == "#,##0"

    def test_number_format_no_group_separator(self):
        """Test number format without group separator."""
        transformer = SemanticModelTransformer()

        format_spec = NumberFormat(
            type="number",
            decimal_places=DecimalPlaces(type="exact", places=2),
            hide_group_separator=True,
        )

        result = transformer._number_to_dax_format(format_spec)

        assert result == "#0.00"

    def test_currency_format_usd(self):
        """Test USD currency format."""
        transformer = SemanticModelTransformer()

        format_spec = CurrencyFormat(
            type="currency",
            currency_code="USD",
            decimal_places=DecimalPlaces(type="exact", places=2),
        )

        result = transformer._currency_to_dax_format(format_spec)

        assert result == "$#,##0.00"

    def test_currency_format_eur(self):
        """Test EUR currency format."""
        transformer = SemanticModelTransformer()

        format_spec = CurrencyFormat(
            type="currency",
            currency_code="EUR",
            decimal_places=DecimalPlaces(type="exact", places=2),
        )

        result = transformer._currency_to_dax_format(format_spec)

        assert result == "€#,##0.00"

    def test_percentage_format(self):
        """Test percentage format."""
        transformer = SemanticModelTransformer()

        format_spec = PercentageFormat(
            type="percentage",
            decimal_places=DecimalPlaces(type="exact", places=1),
        )

        result = transformer._percentage_to_dax_format(format_spec)

        assert result == "0.0%"

    def test_date_format_year_month_day(self):
        """Test year_month_day date format."""
        transformer = SemanticModelTransformer()

        format_spec = DateFormat(type="date", date_format="year_month_day")

        result = transformer._date_to_dax_format(format_spec)

        assert result == "yyyy-MM-dd"

    def test_date_format_locale_short_month(self):
        """Test locale_short_month date format."""
        transformer = SemanticModelTransformer()

        format_spec = DateFormat(type="date", date_format="locale_short_month")

        result = transformer._date_to_dax_format(format_spec)

        assert result == "MMM d, yyyy"


class TestAggregationTypeDetection:
    """Tests for aggregation type detection."""

    def test_detect_sum(self):
        """Test SUM detection."""
        transformer = SemanticModelTransformer()

        result = transformer._detect_aggregation_type("SUM(amount)")

        assert result == AggregationType.SUM

    def test_detect_count(self):
        """Test COUNT detection."""
        transformer = SemanticModelTransformer()

        result = transformer._detect_aggregation_type("COUNT(id)")

        assert result == AggregationType.COUNT

    def test_detect_distinctcount(self):
        """Test DISTINCTCOUNT detection."""
        transformer = SemanticModelTransformer()

        result = transformer._detect_aggregation_type("COUNT(DISTINCT customer_id)")

        assert result == AggregationType.DISTINCTCOUNT

    def test_detect_average(self):
        """Test AVERAGE detection."""
        transformer = SemanticModelTransformer()

        result = transformer._detect_aggregation_type("AVG(price)")

        assert result == AggregationType.AVERAGE

    def test_detect_min_max(self):
        """Test MIN and MAX detection."""
        transformer = SemanticModelTransformer()

        assert transformer._detect_aggregation_type("MIN(date)") == AggregationType.MIN
        assert transformer._detect_aggregation_type("MAX(date)") == AggregationType.MAX


class TestParseSource:
    """Tests for source string parsing."""

    def test_parse_three_level_name(self):
        """Test parsing catalog.schema.table format."""
        transformer = SemanticModelTransformer()

        schema, table = transformer._parse_source("catalog.schema.orders")

        assert schema == "schema"
        assert table == "orders"

    def test_parse_two_level_name(self):
        """Test parsing schema.table format."""
        transformer = SemanticModelTransformer()

        schema, table = transformer._parse_source("schema.orders")

        assert schema == "schema"
        assert table == "orders"

    def test_parse_single_name(self):
        """Test parsing table-only format."""
        transformer = SemanticModelTransformer()

        schema, table = transformer._parse_source("orders")

        assert schema is None
        assert table == "orders"

    def test_parse_sql_query(self):
        """Test that SQL queries return None."""
        transformer = SemanticModelTransformer()

        schema, table = transformer._parse_source("SELECT * FROM orders WHERE active = true")

        assert schema is None
        assert table is None


class TestToFabricModel:
    """Tests for intermediate to Fabric model conversion."""

    def test_basic_conversion(self):
        """Test basic conversion to Fabric model."""
        transformer = SemanticModelTransformer()

        intermediate = IntermediateSemanticModel(
            name="test_model",
            description="Test model",
            tables=[
                IntermediateTable(
                    name="Sales",
                    columns=[
                        IntermediateColumn(
                            name="amount",
                            data_type=DataType.DECIMAL,
                            source_column="amount",
                        )
                    ],
                    measures=[
                        IntermediateMeasure(
                            name="Total Sales",
                            expression="SUM([amount])",
                        )
                    ],
                )
            ],
            relationships=[],
            source_system="DATABRICKS",
        )

        result = transformer.to_fabric_model(intermediate)

        assert result.name == "test_model"
        assert result.description == "Test model"
        assert len(result.tables) == 1
        assert result.tables[0].name == "Sales"
        assert len(result.tables[0].columns) == 1
        assert len(result.tables[0].measures) == 1

    def test_relationship_conversion(self):
        """Test relationship conversion to Fabric model."""
        transformer = SemanticModelTransformer()

        intermediate = IntermediateSemanticModel(
            name="test_model",
            tables=[
                IntermediateTable(name="Sales", columns=[], measures=[]),
                IntermediateTable(name="Products", columns=[], measures=[]),
            ],
            relationships=[
                IntermediateRelationship(
                    name="Sales_Products",
                    from_table="Sales",
                    from_column="product_id",
                    to_table="Products",
                    to_column="id",
                    cardinality=RelationshipCardinality.MANY_TO_ONE,
                )
            ],
            source_system="DATABRICKS",
        )

        result = transformer.to_fabric_model(intermediate)

        assert len(result.relationships) == 1
        rel = result.relationships[0]
        assert rel.fromTable == "Sales"
        assert rel.toTable == "Products"
        assert rel.fromCardinality == "many"
        assert rel.toCardinality == "one"


class TestTransformAll:
    """Tests for transform_all method."""

    def test_transform_all_multiple_models(self):
        """Test transforming multiple intermediate models."""
        transformer = SemanticModelTransformer()

        intermediates = [
            IntermediateSemanticModel(
                name="model1",
                tables=[IntermediateTable(name="Table1", columns=[], measures=[])],
                relationships=[],
                source_system="DATABRICKS",
            ),
            IntermediateSemanticModel(
                name="model2",
                tables=[IntermediateTable(name="Table2", columns=[], measures=[])],
                relationships=[],
                source_system="DATABRICKS",
            ),
        ]

        results = transformer.transform_all(intermediates)

        assert len(results) == 2
        assert results[0].name == "model1"
        assert results[1].name == "model2"

    def test_transform_all_empty_list(self):
        """Test transforming empty list."""
        transformer = SemanticModelTransformer()

        results = transformer.transform_all([])

        assert results == []


class TestEndToEndTransformation:
    """End-to-end transformation tests."""

    def test_full_metric_view_transformation(self):
        """Test complete transformation from Metric View to Fabric model."""
        transformer = SemanticModelTransformer()

        # Create a realistic Metric View
        metric_view = DatabricksMetricView(
            version="1.1",
            name="ecommerce_metrics",
            source="ecommerce.sales.orders",
            comment="E-commerce order metrics",
            dimensions=[
                DatabricksDimension(
                    name="order_date",
                    expr="order_date",
                    comment="Order date",
                    format=DateFormat(type="date", date_format="year_month_day"),
                ),
                DatabricksDimension(
                    name="customer_segment",
                    expr="segment",
                    comment="Customer segment",
                ),
            ],
            measures=[
                DatabricksMeasure(
                    name="total_revenue",
                    expr="SUM(order_total)",
                    comment="Total order revenue",
                    format=CurrencyFormat(
                        type="currency",
                        currency_code="USD",
                        decimal_places=DecimalPlaces(type="exact", places=2),
                    ),
                ),
                DatabricksMeasure(
                    name="order_count",
                    expr="COUNT(1)",
                    comment="Number of orders",
                ),
                DatabricksMeasure(
                    name="unique_customers",
                    expr="COUNT(DISTINCT customer_id)",
                    comment="Unique customer count",
                ),
            ],
            filter="status = 'completed'",
            catalog_name="ecommerce",
            schema_name="sales",
        )

        # Transform to intermediate
        intermediate = transformer.transform(metric_view)

        # Verify intermediate model
        assert intermediate.name == "ecommerce_metrics"
        assert intermediate.description == "E-commerce order metrics"
        assert len(intermediate.tables) == 1

        table = intermediate.tables[0]
        assert len(table.columns) == 2
        assert len(table.measures) == 3

        # Verify columns
        date_col = next(c for c in table.columns if c.name == "order_date")
        assert date_col.data_type == DataType.DATETIME
        assert date_col.format_string == "yyyy-MM-dd"

        # Verify measures
        revenue_measure = next(m for m in table.measures if m.name == "total_revenue")
        assert revenue_measure.format_string == "$#,##0.00"
        assert "SUM(" in revenue_measure.expression

        count_measure = next(m for m in table.measures if m.name == "order_count")
        assert count_measure.expression == "COUNTROWS()"

        distinct_measure = next(m for m in table.measures if m.name == "unique_customers")
        assert "DISTINCTCOUNT(" in distinct_measure.expression

        # Transform to Fabric model
        fabric_model = transformer.to_fabric_model(intermediate)

        # Verify Fabric model
        assert fabric_model.name == "ecommerce_metrics"
        assert len(fabric_model.tables) == 1
        assert len(fabric_model.tables[0].columns) == 2
        assert len(fabric_model.tables[0].measures) == 3
