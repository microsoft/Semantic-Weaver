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


class TestMultiTableTransformation:
    """Tests for multi-table transformation with joins."""

    def test_transform_with_single_join(self):
        """Test transformation with one join creates two tables and one relationship."""
        transformer = SemanticModelTransformer()

        metric_view = DatabricksMetricView(
            version="1.1",
            name="orders_with_customers",
            source="catalog.schema.orders",
            dimensions=[
                # Dimensions on the source table (orders)
                DatabricksDimension(name="order_date", expr="o_orderdate"),
                DatabricksDimension(name="order_status", expr="o_orderstatus"),
                # Dimensions from joined table (customer)
                DatabricksDimension(name="customer_name", expr="customer.c_name"),
                DatabricksDimension(name="customer_segment", expr="customer.c_mktsegment"),
            ],
            measures=[
                DatabricksMeasure(name="total_revenue", expr="SUM(o_totalprice)"),
            ],
            joins=[
                {
                    "type": "left",
                    "table": "catalog.schema.customer",
                    "on": "orders.o_custkey = customer.c_custkey",
                }
            ],
        )

        result = transformer.transform(metric_view)

        # Should have 2 tables: orders_with_customers (source) and customer
        assert len(result.tables) == 2

        # Find tables by name
        source_table = next((t for t in result.tables if t.name == "orders_with_customers"), None)
        customer_table = next((t for t in result.tables if t.name == "customer"), None)

        assert source_table is not None, "Source table should exist"
        assert customer_table is not None, "Customer table should exist"

        # Source table should have 2 columns (order_date, order_status)
        assert len(source_table.columns) == 2
        source_col_names = {c.name for c in source_table.columns}
        assert "order_date" in source_col_names
        assert "order_status" in source_col_names

        # Measures should be on source table
        assert len(source_table.measures) == 1
        assert source_table.measures[0].name == "total_revenue"

        # Customer table should have 2 columns (customer_name, customer_segment)
        assert len(customer_table.columns) == 2
        customer_col_names = {c.name for c in customer_table.columns}
        assert "customer_name" in customer_col_names
        assert "customer_segment" in customer_col_names

        # Customer table should have no measures
        assert len(customer_table.measures) == 0

        # Should have 1 relationship
        assert len(result.relationships) == 1
        rel = result.relationships[0]
        assert rel.from_table == "orders_with_customers"
        assert rel.to_table == "customer"
        assert rel.cardinality == RelationshipCardinality.MANY_TO_ONE

    def test_transform_with_nested_joins(self):
        """Test transformation with nested joins creates all tables and relationships."""
        transformer = SemanticModelTransformer()

        metric_view = DatabricksMetricView(
            version="1.1",
            name="lineitem_metrics",
            source="catalog.schema.lineitem",
            dimensions=[
                # Source table columns
                DatabricksDimension(name="shipdate", expr="l_shipdate"),
                # First level join (orders)
                DatabricksDimension(name="order_status", expr="orders.o_orderstatus"),
                DatabricksDimension(name="order_date", expr="orders.o_orderdate"),
                # Nested join (customer, joined through orders)
                DatabricksDimension(name="customer_name", expr="orders.customer.c_name"),
            ],
            measures=[
                DatabricksMeasure(name="total_extended_price", expr="SUM(l_extendedprice)"),
            ],
            joins=[
                {
                    "type": "left",
                    "table": "catalog.schema.orders",
                    "on": "lineitem.l_orderkey = orders.o_orderkey",
                    "joins": [
                        {
                            "type": "left",
                            "table": "catalog.schema.customer",
                            "on": "orders.o_custkey = customer.c_custkey",
                        }
                    ],
                }
            ],
        )

        result = transformer.transform(metric_view)

        # Should have 3 tables: lineitem_metrics (source), orders, customer
        assert len(result.tables) == 3

        table_names = {t.name for t in result.tables}
        assert "lineitem_metrics" in table_names
        assert "orders" in table_names
        assert "customer" in table_names

        # Verify column distribution
        source_table = next(t for t in result.tables if t.name == "lineitem_metrics")
        orders_table = next(t for t in result.tables if t.name == "orders")
        customer_table = next(t for t in result.tables if t.name == "customer")

        # Source should have shipdate column and measures
        assert len(source_table.columns) == 1
        assert source_table.columns[0].name == "shipdate"
        assert len(source_table.measures) == 1

        # Orders should have order_status and order_date
        assert len(orders_table.columns) == 2
        orders_col_names = {c.name for c in orders_table.columns}
        assert "order_status" in orders_col_names
        assert "order_date" in orders_col_names
        assert len(orders_table.measures) == 0

        # Customer should have customer_name
        assert len(customer_table.columns) == 1
        assert customer_table.columns[0].name == "customer_name"
        assert len(customer_table.measures) == 0

        # Should have 2 relationships
        assert len(result.relationships) == 2

    def test_dimension_source_column_strips_table_prefix(self):
        """Test that source_column strips table prefixes from expr."""
        transformer = SemanticModelTransformer()

        metric_view = DatabricksMetricView(
            version="1.1",
            name="test_model",
            source="catalog.schema.fact_table",
            dimensions=[
                DatabricksDimension(name="dim_col", expr="dim_table.column_name"),
            ],
            measures=[],
            joins=[
                {
                    "type": "left",
                    "table": "catalog.schema.dim_table",
                    "on": "fact_table.key = dim_table.key",
                }
            ],
        )

        result = transformer.transform(metric_view)

        # Find the dim_table
        dim_table = next(t for t in result.tables if t.name == "dim_table")
        assert len(dim_table.columns) == 1

        # source_column should be just "column_name", not "dim_table.column_name"
        assert dim_table.columns[0].source_column == "column_name"

    def test_relationship_uses_model_name_for_source_table(self):
        """Test that relationships use the model name for the source table."""
        transformer = SemanticModelTransformer()

        metric_view = DatabricksMetricView(
            version="1.1",
            name="my_custom_model",
            source="catalog.schema.base_table",
            dimensions=[
                DatabricksDimension(name="col1", expr="col1"),
                DatabricksDimension(name="dim_col", expr="dim.dim_column"),
            ],
            measures=[],
            joins=[
                {
                    "type": "left",
                    "table": "catalog.schema.dim",
                    "on": "base_table.key = dim.key",
                }
            ],
        )

        result = transformer.transform(metric_view)

        # The relationship should reference the model name, not "base_table"
        assert len(result.relationships) == 1
        rel = result.relationships[0]
        assert rel.from_table == "my_custom_model"  # Model name
        assert rel.to_table == "dim"  # Joined table alias

    def test_transform_without_joins_single_table(self):
        """Test that transformation without joins creates a single table."""
        transformer = SemanticModelTransformer()

        metric_view = DatabricksMetricView(
            version="1.1",
            name="simple_model",
            source="catalog.schema.fact_table",
            dimensions=[
                DatabricksDimension(name="col1", expr="column1"),
                DatabricksDimension(name="col2", expr="column2"),
            ],
            measures=[
                DatabricksMeasure(name="measure1", expr="SUM(value)"),
            ],
        )

        result = transformer.transform(metric_view)

        # Should have exactly 1 table
        assert len(result.tables) == 1
        assert result.tables[0].name == "simple_model"

        # All dimensions should be in the table
        assert len(result.tables[0].columns) == 2

        # Measure should be in the table
        assert len(result.tables[0].measures) == 1

        # No relationships
        assert len(result.relationships) == 0

    def test_extract_tables_from_metric_view(self):
        """Test the helper method that extracts table info."""
        transformer = SemanticModelTransformer()

        metric_view = DatabricksMetricView(
            version="1.1",
            name="test",
            source="catalog.schema.fact",
            dimensions=[],
            measures=[],
            joins=[
                {
                    "table": "catalog.schema.dim1",
                    "on": "fact.k = dim1.k",
                    "joins": [
                        {
                            "table": "catalog.schema.dim2",
                            "alias": "d2",
                            "on": "dim1.k = d2.k",
                        }
                    ],
                }
            ],
        )

        table_info = transformer._extract_tables_from_metric_view(metric_view)

        # Should have 3 tables: fact (source), dim1, d2 (aliased)
        assert len(table_info) == 3
        assert "fact" in table_info
        assert "dim1" in table_info
        assert "d2" in table_info

        # Verify source flag
        assert table_info["fact"]["is_source"] is True
        assert table_info["dim1"]["is_source"] is False
        assert table_info["d2"]["is_source"] is False

    def test_get_table_from_expr(self):
        """Test the helper that determines table from expression."""
        transformer = SemanticModelTransformer()

        table_info = {
            "fact": {"is_source": True},
            "orders": {"is_source": False},
            "customer": {"is_source": False},
        }

        # No prefix -> source table
        assert transformer._get_table_from_expr("column1", table_info, "fact") == "fact"

        # Single prefix -> that table
        assert transformer._get_table_from_expr("orders.o_status", table_info, "fact") == "orders"

        # Nested prefix -> innermost valid table
        assert transformer._get_table_from_expr(
            "orders.customer.c_name", table_info, "fact"
        ) == "customer"

        # Unknown prefix -> source table
        assert transformer._get_table_from_expr(
            "unknown.column", table_info, "fact"
        ) == "fact"
