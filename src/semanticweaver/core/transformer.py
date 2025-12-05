"""
Semantic model transformation logic.

This module transforms source-specific semantic models into the
Fabric semantic model representation that can be deployed to a Fabric Workspace.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from semanticweaver.models.fabric import (
    FabricColumn,
    FabricMeasure,
    FabricPartition,
    FabricRelationship,
    FabricSemanticModel,
    FabricTable,
)
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

if TYPE_CHECKING:
    from semanticweaver.plugins.databricks.model import (
        CurrencyFormat,
        DatabricksDimension,
        DatabricksMeasure,
        DatabricksMetricView,
        DateFormat,
        DateTimeFormat,
        FormatSpecification,
        NumberFormat,
        PercentageFormat,
    )


class TransformationError(Exception):
    """Raised when transformation fails."""

    pass


class SemanticModelTransformer:
    """
    Transforms source semantic models into intermediate and Fabric representations.

    The transformation process:
    1. Source model -> Intermediate model (generic representation)
    2. Intermediate model -> Fabric model (Power BI Semantic Model format)
    """

    # SQL to DAX aggregation function mapping
    SQL_TO_DAX_AGGREGATIONS: dict[str, str] = {
        "SUM": "SUM",
        "COUNT": "COUNT",
        "AVG": "AVERAGE",
        "MIN": "MIN",
        "MAX": "MAX",
        "COUNT_DISTINCT": "DISTINCTCOUNT",
        "COUNTDISTINCT": "DISTINCTCOUNT",
    }

    # SQL data type to DAX data type mapping
    SQL_TO_DAX_DATATYPES: dict[str, str] = {
        "STRING": "String",
        "VARCHAR": "String",
        "CHAR": "String",
        "TEXT": "String",
        "INT": "Int64",
        "INTEGER": "Int64",
        "BIGINT": "Int64",
        "SMALLINT": "Int64",
        "TINYINT": "Int64",
        "LONG": "Int64",
        "DECIMAL": "Decimal",
        "NUMERIC": "Decimal",
        "FLOAT": "Double",
        "DOUBLE": "Double",
        "REAL": "Double",
        "BOOLEAN": "Boolean",
        "BOOL": "Boolean",
        "DATE": "DateTime",
        "DATETIME": "DateTime",
        "TIMESTAMP": "DateTime",
        "TIME": "DateTime",
        "BINARY": "Binary",
        "BYTES": "Binary",
    }

    def __init__(self, name_prefix: str | None = None):
        """
        Initialize the transformer.

        Args:
            name_prefix: Optional prefix to add to generated model names.
        """
        self.name_prefix = name_prefix

    def transform(self, source_model: Any) -> IntermediateSemanticModel:
        """
        Transform a source-specific model to Fabric semantic model representation.

        Args:
            source_model: The semantic model extracted from the source system.
                         Supports DatabricksMetricView.

        Returns:
            IntermediateSemanticModel: The Fabric semantic model representation.

        Raises:
            TransformationError: If transformation fails or unsupported model type.
        """
        # Import here to avoid circular imports
        from semanticweaver.plugins.databricks.model import DatabricksMetricView

        if isinstance(source_model, DatabricksMetricView):
            return self._transform_databricks_metric_view(source_model)
        else:
            raise TransformationError(
                f"Unsupported source model type: {type(source_model).__name__}. "
                "Currently supported: DatabricksMetricView"
            )

    def _transform_databricks_metric_view(
        self, metric_view: DatabricksMetricView
    ) -> IntermediateSemanticModel:
        """
        Transform a Databricks Metric View to Fabric semantic model representation.

        This method extracts all tables from the source and joins, places dimensions
        in their correct tables based on expr prefixes, and creates relationships.

        Args:
            metric_view: The Databricks Metric View to transform.

        Returns:
            IntermediateSemanticModel with tables, columns, and measures.

        Raises:
            TransformationError: If transformation fails.
        """
        try:
            # Determine model name from metric view
            model_name = self._get_model_name(metric_view)

            # Extract all tables from source and joins
            table_info = self._extract_tables_from_metric_view(metric_view)

            # Map dimensions to their respective tables based on expr prefixes
            table_dimensions = self._map_dimensions_to_tables(
                metric_view.dimensions, table_info
            )

            # Create tables with their respective columns
            tables = self._create_tables_from_map(
                table_info, table_dimensions, metric_view
            )

            # Create relationships from joins
            relationships = self._create_relationships_from_joins(metric_view)

            # Build the intermediate model
            return IntermediateSemanticModel(
                name=model_name,
                description=metric_view.comment,
                tables=tables,
                relationships=relationships,
                source_system="DATABRICKS",
                source_name=metric_view.catalog_name,
            )

        except Exception as e:
            raise TransformationError(
                f"Failed to transform Databricks Metric View '{metric_view.name}': {e}"
            ) from e

    def _extract_tables_from_metric_view(
        self, metric_view: DatabricksMetricView
    ) -> dict[str, dict]:
        """
        Extract all table information from the metric view source and joins.

        Returns a dict mapping table alias -> table info:
        {
            "alias": {
                "full_name": "catalog.schema.table",
                "table_name": "table",
                "alias": "alias",
                "is_source": True/False
            }
        }
        """
        tables = {}

        # Extract source table
        source_parts = metric_view.source.split(".")
        source_table_name = source_parts[-1] if source_parts else metric_view.source

        # The source table's alias is the table name itself
        tables[source_table_name] = {
            "full_name": metric_view.source,
            "table_name": source_table_name,
            "alias": source_table_name,
            "is_source": True,
        }

        # Extract tables from joins recursively
        if metric_view.joins:
            self._extract_tables_from_joins(metric_view.joins, tables)

        return tables

    def _extract_tables_from_joins(
        self, joins: list[dict], tables: dict[str, dict], parent_alias: str | None = None
    ) -> None:
        """
        Recursively extract table information from joins.

        Args:
            joins: List of join definitions
            tables: Dict to populate with table info
            parent_alias: Parent table alias for nested joins
        """
        for join in joins:
            table_ref = join.get("table", "")
            if not table_ref:
                continue

            # Parse the table reference (catalog.schema.table)
            parts = table_ref.split(".")
            table_name = parts[-1] if parts else table_ref

            # Use alias from join if provided, otherwise use table name
            alias = join.get("alias", table_name)

            tables[alias] = {
                "full_name": table_ref,
                "table_name": table_name,
                "alias": alias,
                "is_source": False,
            }

            # Process nested joins if present
            nested_joins = join.get("joins", [])
            if nested_joins:
                self._extract_tables_from_joins(nested_joins, tables, alias)

    def _map_dimensions_to_tables(
        self,
        dimensions: list["DatabricksDimension"],
        table_info: dict[str, dict],
    ) -> dict[str, list["DatabricksDimension"]]:
        """
        Map dimensions to their respective tables based on expr prefixes.

        Dimension expr can be:
        - "column_name" -> belongs to source table
        - "table_alias.column_name" -> belongs to specified table
        - "table1.table2.column_name" -> nested join table (use innermost path)

        Returns dict mapping table alias -> list of dimensions
        """
        table_dimensions: dict[str, list] = {alias: [] for alias in table_info}

        # Find the source table alias
        source_alias = None
        for alias, info in table_info.items():
            if info.get("is_source"):
                source_alias = alias
                break

        for dimension in dimensions:
            expr = dimension.expr
            target_table = self._get_table_from_expr(expr, table_info, source_alias)
            if target_table in table_dimensions:
                table_dimensions[target_table].append(dimension)
            elif source_alias:
                # Fallback to source table
                table_dimensions[source_alias].append(dimension)

        return table_dimensions

    def _get_table_from_expr(
        self, expr: str, table_info: dict[str, dict], source_alias: str | None
    ) -> str:
        """
        Determine which table a dimension expression belongs to.

        Examples:
        - "o_orderdate" -> source table (no prefix)
        - "orders.o_orderstatus" -> "orders"
        - "orders.customer.c_name" -> "customer"

        Args:
            expr: The dimension expression
            table_info: Dict of table aliases
            source_alias: The source table alias

        Returns:
            Table alias that owns this expression
        """
        # Split expression by dots to find table prefix
        parts = expr.split(".")

        if len(parts) == 1:
            # No table prefix, belongs to source table
            return source_alias or list(table_info.keys())[0]

        # Check for nested references (e.g., "orders.customer.c_name")
        # The table is determined by the path, last prefix before column
        # For "orders.customer.c_name", the table is "customer"
        for i in range(len(parts) - 1, 0, -1):
            # Check from innermost to outermost
            potential_alias = parts[i - 1]
            if potential_alias in table_info:
                return potential_alias

        # If we have "table.column" format
        if parts[0] in table_info:
            return parts[0]

        # Fallback to source table
        return source_alias or list(table_info.keys())[0]

    def _create_tables_from_map(
        self,
        table_info: dict[str, dict],
        table_dimensions: dict[str, list["DatabricksDimension"]],
        metric_view: DatabricksMetricView,
    ) -> list[IntermediateTable]:
        """
        Create IntermediateTable objects from the table map.

        Measures are placed on the source (fact) table.
        For single-table scenarios, the source table uses the model name.
        For multi-table scenarios, tables use their actual names.
        """
        tables = []
        model_name = self._get_model_name(metric_view)

        for alias, info in table_info.items():
            dims = table_dimensions.get(alias, [])

            # Convert dimensions to columns
            columns = [self._dimension_to_column(dim, alias) for dim in dims]

            # Measures go on the source (fact) table only
            measures = []
            is_source = info.get("is_source", False)
            if is_source:
                measures = [
                    self._measure_to_intermediate(measure)
                    for measure in metric_view.measures
                ]

            # Parse full table reference for source info
            full_name = info.get("full_name", "")
            parts = full_name.split(".")

            source_schema = None
            source_table = None
            if len(parts) >= 3:
                source_schema = parts[-2]
                source_table = parts[-1]
            elif len(parts) == 2:
                source_schema = parts[0]
                source_table = parts[1]
            elif len(parts) == 1:
                source_table = parts[0]

            # Determine table name:
            # - Source table uses model name for backward compatibility
            # - Joined tables use their actual alias
            table_name = model_name if is_source else alias

            table = IntermediateTable(
                name=table_name,
                description=metric_view.comment if is_source else None,
                columns=columns,
                measures=measures,
                is_hidden=False,
                source_schema=source_schema,
                source_table=source_table,
                source_query=metric_view.filter if is_source else None,
            )

            tables.append(table)

        return tables

    def _dimension_to_column(
        self, dimension: "DatabricksDimension", table_alias: str | None = None
    ) -> IntermediateColumn:
        """
        Convert a Databricks dimension to an intermediate column.

        Strips the table prefix from source_column if present.

        Args:
            dimension: The Databricks dimension to convert
            table_alias: Optional table alias (used for multi-table scenarios)

        Returns:
            IntermediateColumn with proper column mapping
        """
        # Infer data type from expression or format
        data_type = self._infer_data_type_from_dimension(dimension)

        # Generate format string
        format_string = self._format_to_string(dimension.format) if dimension.format else None

        # Clean up source column - remove table prefix for the column reference
        source_col = dimension.expr
        parts = source_col.split(".")
        if len(parts) > 1:
            # Use just the column name part (last part)
            source_col = parts[-1]

        return IntermediateColumn(
            name=dimension.name,
            data_type=data_type,
            description=dimension.comment,
            is_hidden=False,
            display_folder=None,
            format_string=format_string,
            source_column=source_col,
        )

    def _get_model_name(self, metric_view: DatabricksMetricView) -> str:
        """Get a suitable model name from the metric view."""
        if metric_view.name:
            return metric_view.name
        # Fallback: derive from source
        if metric_view.source:
            # Extract table name from source (e.g., "catalog.schema.table" -> "table")
            parts = metric_view.source.split(".")
            return parts[-1] if parts else "UnnamedModel"
        return "UnnamedModel"

    def _create_main_table(self, metric_view: DatabricksMetricView) -> IntermediateTable:
        """
        Create the main fact table from the metric view.

        DEPRECATED: Use _create_tables_from_map for multi-table support.
        Kept for backward compatibility with single-table scenarios.
        """
        # Convert dimensions to columns
        columns = [
            self._dimension_to_column(dim, "main") for dim in metric_view.dimensions
        ]

        # Convert measures
        measures = [
            self._measure_to_intermediate(measure) for measure in metric_view.measures
        ]

        # Parse source to get schema and table info
        source_schema, source_table = self._parse_source(metric_view.source)

        return IntermediateTable(
            name=self._get_model_name(metric_view),
            description=metric_view.comment,
            columns=columns,
            measures=measures,
            is_hidden=False,
            source_schema=source_schema,
            source_table=source_table,
            source_query=metric_view.filter,  # Store filter as query reference
        )

    def _measure_to_intermediate(self, measure: DatabricksMeasure) -> IntermediateMeasure:
        """Convert a Databricks measure to an intermediate measure."""
        # Convert SQL expression to DAX
        dax_expression = self._sql_to_dax_expression(measure.expr, measure.name)

        # Generate format string
        format_string = self._format_to_dax_format(measure.format) if measure.format else None

        # Detect aggregation type from expression
        agg_type = self._detect_aggregation_type(measure.expr)

        return IntermediateMeasure(
            name=measure.name,
            expression=dax_expression,
            description=measure.comment,
            display_folder=None,
            format_string=format_string,
            is_hidden=False,
            source_definition=measure.expr,
            aggregation_type=agg_type,
        )

    def _infer_data_type_from_dimension(self, dimension: DatabricksDimension) -> DataType:
        """Infer the data type from a dimension's format or expression."""
        # Check format type first
        if dimension.format:
            format_type = getattr(dimension.format, "type", None)
            if format_type in ("date", "date_time"):
                return DataType.DATETIME
            elif format_type == "number":
                return DataType.DOUBLE
            elif format_type == "currency":
                return DataType.DECIMAL
            elif format_type == "percentage":
                return DataType.DOUBLE

        # Infer from expression patterns
        expr_lower = dimension.expr.lower()
        if any(
            kw in expr_lower
            for kw in ["date", "timestamp", "datetime", "date_trunc", "year", "month", "day"]
        ):
            return DataType.DATETIME
        elif any(kw in expr_lower for kw in ["count", "sum", "avg", "decimal", "numeric"]):
            return DataType.DECIMAL
        elif any(kw in expr_lower for kw in ["int", "integer", "bigint"]):
            return DataType.INTEGER
        elif any(kw in expr_lower for kw in ["float", "double", "real"]):
            return DataType.DOUBLE
        elif any(kw in expr_lower for kw in ["bool", "boolean"]):
            return DataType.BOOLEAN

        # Default to string
        return DataType.STRING

    def _format_to_string(self, format_spec: FormatSpecification | None) -> str | None:
        """Convert a Databricks format specification to a display format string."""
        if format_spec is None:
            return None

        format_type = getattr(format_spec, "type", None)

        if format_type == "date":
            date_format = getattr(format_spec, "date_format", "locale_short_month")
            return self._date_format_to_string(date_format)
        elif format_type == "date_time":
            return self._datetime_format_to_string(format_spec)
        elif format_type == "number":
            return self._number_format_to_string(format_spec)
        elif format_type == "currency":
            return self._currency_format_to_string(format_spec)
        elif format_type == "percentage":
            return self._percentage_format_to_string(format_spec)

        return None

    def _format_to_dax_format(self, format_spec: FormatSpecification | None) -> str | None:
        """Convert a Databricks format specification to DAX format string."""
        if format_spec is None:
            return None

        format_type = getattr(format_spec, "type", None)

        if format_type == "number":
            return self._number_to_dax_format(format_spec)
        elif format_type == "currency":
            return self._currency_to_dax_format(format_spec)
        elif format_type == "percentage":
            return self._percentage_to_dax_format(format_spec)
        elif format_type == "date":
            return self._date_to_dax_format(format_spec)
        elif format_type == "date_time":
            return self._datetime_to_dax_format(format_spec)

        return None

    def _number_to_dax_format(self, format_spec: NumberFormat) -> str:
        """Convert NumberFormat to DAX format string."""
        decimal_places = self._get_decimal_places(format_spec.decimal_places)
        hide_group_sep = format_spec.hide_group_separator or False

        if hide_group_sep:
            # Without group separator: #0 or #0.00
            if decimal_places == 0:
                return "#0"
            else:
                decimal_part = "0" * decimal_places
                return f"#0.{decimal_part}"
        else:
            # With group separator: #,##0 or #,##0.00
            if decimal_places == 0:
                return "#,##0"
            else:
                decimal_part = "0" * decimal_places
                return f"#,##0.{decimal_part}"

    def _currency_to_dax_format(self, format_spec: CurrencyFormat) -> str:
        """Convert CurrencyFormat to DAX format string."""
        decimal_places = self._get_decimal_places(format_spec.decimal_places, default=2)
        group_sep = "" if format_spec.hide_group_separator else ","
        currency = format_spec.currency_code or "USD"

        # Map common currency codes to symbols
        currency_symbols = {
            "USD": "$",
            "EUR": "€",
            "GBP": "£",
            "JPY": "¥",
            "CNY": "¥",
            "INR": "₹",
            "CAD": "CA$",
            "AUD": "A$",
        }
        symbol = currency_symbols.get(currency.upper(), currency)

        if decimal_places == 0:
            return f"{symbol}#{group_sep}##0"
        else:
            decimal_part = "0" * decimal_places
            return f"{symbol}#{group_sep}##0.{decimal_part}"

    def _percentage_to_dax_format(self, format_spec: PercentageFormat) -> str:
        """Convert PercentageFormat to DAX format string."""
        decimal_places = self._get_decimal_places(format_spec.decimal_places, default=2)

        if decimal_places == 0:
            return "0%"
        else:
            decimal_part = "0" * decimal_places
            return f"0.{decimal_part}%"

    def _date_to_dax_format(self, format_spec: DateFormat) -> str:
        """Convert DateFormat to DAX format string."""
        date_format = format_spec.date_format

        format_map = {
            "locale_short_month": "MMM d, yyyy",
            "locale_long_month": "MMMM d, yyyy",
            "year_month_day": "yyyy-MM-dd",
            "locale_number_month": "M/d/yyyy",
            "year_week": "yyyy-'W'ww",
        }
        return format_map.get(date_format, "yyyy-MM-dd")

    def _datetime_to_dax_format(self, format_spec: DateTimeFormat) -> str:
        """Convert DateTimeFormat to DAX format string."""
        date_format = getattr(format_spec, "date_format", "year_month_day") or "year_month_day"
        time_format = getattr(format_spec, "time_format", "locale_hour_minute") or "locale_hour_minute"

        # Date part
        date_map = {
            "no_date": "",
            "locale_short_month": "MMM d, yyyy",
            "locale_long_month": "MMMM d, yyyy",
            "year_month_day": "yyyy-MM-dd",
            "locale_number_month": "M/d/yyyy",
            "year_week": "yyyy-'W'ww",
        }
        date_str = date_map.get(date_format, "yyyy-MM-dd")

        # Time part
        time_map = {
            "no_time": "",
            "locale_hour_minute": "HH:mm",
            "locale_hour_minute_second": "HH:mm:ss",
        }
        time_str = time_map.get(time_format, "HH:mm")

        if date_str and time_str:
            return f"{date_str} {time_str}"
        return date_str or time_str or "yyyy-MM-dd HH:mm"

    def _date_format_to_string(self, date_format: str) -> str:
        """Convert Databricks date format to display string."""
        format_map = {
            "locale_short_month": "MMM d, yyyy",
            "locale_long_month": "MMMM d, yyyy",
            "year_month_day": "yyyy-MM-dd",
            "locale_number_month": "M/d/yyyy",
            "year_week": "yyyy-Www",
        }
        return format_map.get(date_format, "yyyy-MM-dd")

    def _datetime_format_to_string(self, format_spec: DateTimeFormat) -> str:
        """Convert Databricks datetime format to display string."""
        return self._datetime_to_dax_format(format_spec)

    def _number_format_to_string(self, format_spec: NumberFormat) -> str:
        """Convert NumberFormat to display string."""
        return self._number_to_dax_format(format_spec)

    def _currency_format_to_string(self, format_spec: CurrencyFormat) -> str:
        """Convert CurrencyFormat to display string."""
        return self._currency_to_dax_format(format_spec)

    def _percentage_format_to_string(self, format_spec: PercentageFormat) -> str:
        """Convert PercentageFormat to display string."""
        return self._percentage_to_dax_format(format_spec)

    def _get_decimal_places(
        self, decimal_spec: Any | None, default: int = 2
    ) -> int:
        """Extract decimal places from a DecimalPlaces specification."""
        if decimal_spec is None:
            return default

        places = getattr(decimal_spec, "places", None)
        if places is not None:
            return places

        # For 'all' type, use max precision
        spec_type = getattr(decimal_spec, "type", None)
        if spec_type == "all":
            return 10  # Max precision

        return default

    def _sql_to_dax_expression(self, sql_expr: str, measure_name: str) -> str:
        """
        Convert a SQL aggregate expression to DAX.

        Args:
            sql_expr: SQL expression like "SUM(amount)" or "COUNT(DISTINCT customer_id)"
            measure_name: Name of the measure for context

        Returns:
            DAX expression string.
        """
        # Normalize the expression
        expr = sql_expr.strip()

        # Check for complex expressions with operators FIRST
        # These need special handling to convert all aggregations
        # Use pattern that requires operators to be outside of parentheses
        # to avoid matching COUNT(*) as complex
        if self._is_complex_expression(expr):
            return self._convert_complex_expression(expr)

        # Handle COUNT(DISTINCT x) -> DISTINCTCOUNT(x)
        count_distinct_match = re.match(
            r"COUNT\s*\(\s*DISTINCT\s+(.+?)\s*\)", expr, re.IGNORECASE
        )
        if count_distinct_match:
            column = count_distinct_match.group(1)
            return f"DISTINCTCOUNT({self._qualify_column(column)})"

        # Handle standard aggregations: SUM(x), COUNT(x), AVG(x), MIN(x), MAX(x)
        agg_match = re.match(
            r"(SUM|COUNT|AVG|AVERAGE|MIN|MAX)\s*\(\s*(.+?)\s*\)", expr, re.IGNORECASE
        )
        if agg_match:
            agg_func = agg_match.group(1).upper()
            inner_expr = agg_match.group(2)

            # Map SQL function to DAX
            dax_func = self.SQL_TO_DAX_AGGREGATIONS.get(agg_func, agg_func)

            # Handle COUNT(1) or COUNT(*) -> COUNTROWS
            if agg_func == "COUNT" and inner_expr.strip() in ("1", "*"):
                return "COUNTROWS()"

            # Qualify column references
            qualified_inner = self._qualify_column(inner_expr)
            return f"{dax_func}({qualified_inner})"

        # Fallback: wrap as-is with qualification
        return self._qualify_column(expr)

    def _is_complex_expression(self, expr: str) -> bool:
        """
        Check if expression contains operators outside of parentheses.
        
        This distinguishes "SUM(a) / SUM(b)" (complex) from "COUNT(*)" (simple).
        """
        # Remove content inside parentheses to check for operators at top level
        # Simple approach: check for operators with spaces around them (typical for formulas)
        # or closing paren followed by operator
        if re.search(r"\)\s*[/+\-*]\s*", expr):
            return True
        if re.search(r"\s+[/+\-*]\s+", expr):
            return True
        return False

    def _convert_complex_expression(self, expr: str) -> str:
        """Convert a complex SQL expression with operators to DAX."""
        result = expr

        # Replace COUNT(DISTINCT x) patterns first (before COUNT)
        result = re.sub(
            r"COUNT\s*\(\s*DISTINCT\s+(\w+)\s*\)",
            lambda m: f"DISTINCTCOUNT([{m.group(1)}])",
            result,
            flags=re.IGNORECASE,
        )

        # Replace standard aggregations (but not DISTINCTCOUNT which we just created)
        for sql_func in ["SUM", "AVG", "MIN", "MAX"]:
            dax_func = self.SQL_TO_DAX_AGGREGATIONS.get(sql_func, sql_func)
            pattern = rf"\b{sql_func}\s*\(\s*(\w+)\s*\)"
            result = re.sub(
                pattern,
                lambda m, d=dax_func: f"{d}([{m.group(1)}])",
                result,
                flags=re.IGNORECASE,
            )

        # Handle COUNT separately (but not if it's part of DISTINCTCOUNT)
        result = re.sub(
            r"\bCOUNT\s*\(\s*(\w+)\s*\)",
            lambda m: f"COUNT([{m.group(1)}])",
            result,
            flags=re.IGNORECASE,
        )

        return result

    def _qualify_column(self, column: str) -> str:
        """
        Qualify a column reference for DAX.

        In TMDL/DAX, columns should be referenced as [ColumnName] or 'Table'[ColumnName].
        """
        column = column.strip()

        # Already qualified
        if column.startswith("[") and column.endswith("]"):
            return column

        # Handle table.column notation
        if "." in column:
            parts = column.rsplit(".", 1)
            return f"'{parts[0]}'[{parts[1]}]"

        # Simple column - use brackets
        return f"[{column}]"

    def _detect_aggregation_type(self, expr: str) -> AggregationType | None:
        """Detect the aggregation type from a SQL expression."""
        expr_upper = expr.upper().strip()

        if "COUNT(DISTINCT" in expr_upper or "COUNTDISTINCT" in expr_upper:
            return AggregationType.DISTINCTCOUNT
        elif expr_upper.startswith("SUM("):
            return AggregationType.SUM
        elif expr_upper.startswith("COUNT("):
            return AggregationType.COUNT
        elif expr_upper.startswith("AVG(") or expr_upper.startswith("AVERAGE("):
            return AggregationType.AVERAGE
        elif expr_upper.startswith("MIN("):
            return AggregationType.MIN
        elif expr_upper.startswith("MAX("):
            return AggregationType.MAX

        return None

    def _parse_source(self, source: str) -> tuple[str | None, str | None]:
        """
        Parse a source string to extract schema and table names.

        Args:
            source: Source like "catalog.schema.table" or SQL query

        Returns:
            Tuple of (schema_name, table_name)
        """
        if not source:
            return None, None

        # Check if it's a SQL query (contains SELECT, FROM, etc.)
        if any(kw in source.upper() for kw in ["SELECT ", "FROM ", "WHERE ", "JOIN "]):
            return None, None

        # Parse three-level name: catalog.schema.table
        parts = source.split(".")
        if len(parts) >= 3:
            return parts[-2], parts[-1]  # schema, table
        elif len(parts) == 2:
            return parts[0], parts[1]  # schema, table
        elif len(parts) == 1:
            return None, parts[0]

        return None, None

    def _create_relationships_from_joins(
        self, metric_view: DatabricksMetricView
    ) -> list[IntermediateRelationship]:
        """
        Create relationships from Metric View joins.

        Recursively processes joins to create relationships for nested joins as well.

        Args:
            metric_view: The metric view with optional joins

        Returns:
            List of intermediate relationships
        """
        relationships: list[IntermediateRelationship] = []

        if not metric_view.joins:
            return relationships

        # Get model name (used for source table in relationships)
        model_name = self._get_model_name(metric_view)

        # Get source table alias for mapping
        source_parts = metric_view.source.split(".")
        source_alias = source_parts[-1] if source_parts else "source"

        # Create alias to table name mapping (source table uses model name)
        alias_to_name = {source_alias: model_name}

        # Build mapping for all joined tables
        self._build_alias_map(metric_view.joins, alias_to_name)

        self._process_joins_recursive(
            joins=metric_view.joins,
            parent_alias=source_alias,
            relationships=relationships,
            index_counter=[0],
            alias_to_name=alias_to_name,
        )

        return relationships

    def _build_alias_map(self, joins: list[dict], alias_to_name: dict[str, str]) -> None:
        """Build a mapping of table aliases to table names for relationships."""
        for join in joins:
            table_ref = join.get("table", "")
            if not table_ref:
                continue

            parts = table_ref.split(".")
            table_name = parts[-1] if parts else table_ref
            alias = join.get("alias", table_name)

            # Joined tables use their alias as the name
            alias_to_name[alias] = alias

            # Process nested joins
            nested_joins = join.get("joins", [])
            if nested_joins:
                self._build_alias_map(nested_joins, alias_to_name)

    def _process_joins_recursive(
        self,
        joins: list[dict],
        parent_alias: str,
        relationships: list[IntermediateRelationship],
        index_counter: list[int],
        alias_to_name: dict[str, str],
    ) -> None:
        """
        Recursively process joins and create relationships.

        Args:
            joins: List of join definitions
            parent_alias: The alias of the parent table (for nested joins)
            relationships: List to append relationships to
            index_counter: Counter for unique relationship naming
            alias_to_name: Mapping of aliases to actual table names
        """
        for join in joins:
            # Get table alias
            table_ref = join.get("table", "")
            parts = table_ref.split(".")
            table_name = parts[-1] if parts else table_ref
            alias = join.get("alias", table_name)

            # Parse the ON clause
            join_on = join.get("on", "")
            join_type = join.get("type", "left")

            if table_ref and join_on:
                rel = self._parse_join_on_clause(
                    on_clause=join_on,
                    parent_alias=parent_alias,
                    join_alias=alias,
                    join_type=join_type,
                    index=index_counter[0],
                    alias_to_name=alias_to_name,
                )
                if rel:
                    relationships.append(rel)
                    index_counter[0] += 1

            # Process nested joins
            nested_joins = join.get("joins", [])
            if nested_joins:
                self._process_joins_recursive(
                    joins=nested_joins,
                    parent_alias=alias,
                    relationships=relationships,
                    index_counter=index_counter,
                    alias_to_name=alias_to_name,
                )

    def _parse_join_on_clause(
        self,
        on_clause: str,
        parent_alias: str,
        join_alias: str,
        join_type: str,
        index: int,
        alias_to_name: dict[str, str] | None = None,
    ) -> IntermediateRelationship | None:
        """
        Parse a join ON clause to create a relationship.

        Args:
            on_clause: The ON clause (e.g., "orders.o_custkey = customer.c_custkey")
            parent_alias: The parent table alias
            join_alias: The joined table alias
            join_type: The join type (left, inner, etc.)
            index: Index for unique naming
            alias_to_name: Mapping of aliases to actual table names

        Returns:
            IntermediateRelationship or None if parsing fails
        """
        try:
            # Handle different ON clause formats:
            # "table1.col1 = table2.col2"
            # "col1 = col2" (implicit table references)
            match = re.match(
                r"(?:(\w+)\.)?(\w+)\s*=\s*(?:(\w+)\.)?(\w+)",
                on_clause.strip()
            )
            if not match:
                return None

            left_table, left_col, right_table, right_col = match.groups()

            # Determine from/to based on which side matches which alias
            # Convention: from = many side (fact), to = one side (dimension)
            if left_table == join_alias or (not left_table and not right_table):
                # Left side is the joined table
                from_table = parent_alias
                from_col = right_col
                to_table = join_alias
                to_col = left_col
            else:
                # Right side is the joined table
                from_table = parent_alias
                from_col = left_col
                to_table = join_alias
                to_col = right_col

            # Convert aliases to actual table names
            if alias_to_name:
                from_table = alias_to_name.get(from_table, from_table)
                to_table = alias_to_name.get(to_table, to_table)

            # Determine cardinality from join type
            cardinality = RelationshipCardinality.MANY_TO_ONE
            if join_type.lower() in ("inner", "cross"):
                cardinality = RelationshipCardinality.MANY_TO_MANY

            return IntermediateRelationship(
                name=f"Rel_{from_table}_{to_table}_{index}",
                from_table=from_table,
                from_column=from_col,
                to_table=to_table,
                to_column=to_col,
                cardinality=cardinality,
                is_active=True,
                cross_filter_direction="Single",
            )

        except Exception:
            return None

    def _parse_join_to_relationship(
        self, join: dict, index: int
    ) -> IntermediateRelationship | None:
        """Parse a single join definition to a relationship (legacy method)."""
        try:
            join_table = join.get("table", "")
            join_on = join.get("on", "")
            join_type = join.get("type", "left")

            if not join_table or not join_on:
                return None

            # Parse the ON clause to extract columns
            # Expected format: "table1.column1 = table2.column2"
            match = re.match(r"(\w+)\.(\w+)\s*=\s*(\w+)\.(\w+)", join_on)
            if not match:
                return None

            from_table, from_col, to_table, to_col = match.groups()

            # Determine cardinality from join type
            cardinality = RelationshipCardinality.MANY_TO_ONE
            if join_type.lower() in ("inner", "cross"):
                cardinality = RelationshipCardinality.MANY_TO_MANY

            return IntermediateRelationship(
                name=f"Relationship_{index}_{from_table}_{to_table}",
                from_table=from_table,
                from_column=from_col,
                to_table=to_table,
                to_column=to_col,
                cardinality=cardinality,
                is_active=True,
                cross_filter_direction="Single",
            )

        except Exception:
            return None

    def transform_all(
        self, intermediate_models: list[IntermediateSemanticModel]
    ) -> list[FabricSemanticModel]:
        """
        Transform all intermediate models to Fabric semantic model format.

        Takes a list of intermediate models (one per Metric View from source)
        and converts them all to Fabric format for deployment.

        Args:
            intermediate_models: List of intermediate semantic models to transform.

        Returns:
            list[FabricSemanticModel]: List of models ready for Fabric deployment.

        Raises:
            TransformationError: If transformation of any model fails.
        """
        fabric_models = []
        for intermediate in intermediate_models:
            fabric_model = self.to_fabric_model(intermediate)
            fabric_models.append(fabric_model)
        return fabric_models

    def to_fabric_model(self, intermediate: IntermediateSemanticModel) -> FabricSemanticModel:
        """
        Convert Fabric semantic model representation to final Fabric deployment format.

        Args:
            intermediate: The intermediate semantic model representation.

        Returns:
            FabricSemanticModel: The model ready for Fabric deployment.

        Raises:
            TransformationError: If conversion fails.
        """
        try:
            # Apply name prefix if configured
            model_name = intermediate.name
            if self.name_prefix:
                model_name = f"{self.name_prefix}{intermediate.name}"

            # Convert tables
            fabric_tables = [
                self._intermediate_table_to_fabric(table) for table in intermediate.tables
            ]

            # Convert relationships
            fabric_relationships = [
                self._intermediate_relationship_to_fabric(rel)
                for rel in intermediate.relationships
            ]

            return FabricSemanticModel(
                name=model_name,
                description=intermediate.description,
                tables=fabric_tables,
                relationships=fabric_relationships,
                defaultMode="import",
                culture="en-US",
            )

        except Exception as e:
            raise TransformationError(
                f"Failed to convert intermediate model '{intermediate.name}' to Fabric format: {e}"
            ) from e

    def _intermediate_table_to_fabric(self, table: IntermediateTable) -> FabricTable:
        """Convert an intermediate table to a Fabric table."""
        # Convert columns
        fabric_columns = [
            FabricColumn(
                name=col.name,
                dataType=col.data_type.value,
                sourceColumn=col.source_column,
                isHidden=col.is_hidden,
                description=col.description,
                formatString=col.format_string,
                displayFolder=col.display_folder,
                summarizeBy="none",
            )
            for col in table.columns
        ]

        # Convert measures
        fabric_measures = [
            FabricMeasure(
                name=measure.name,
                expression=measure.expression,
                description=measure.description,
                formatString=measure.format_string,
                displayFolder=measure.display_folder,
                isHidden=measure.is_hidden,
            )
            for measure in table.measures
        ]

        # Create partition for the source
        partitions = []
        if table.source_table:
            partition_source = {
                "type": "m",
                "expression": self._create_m_expression(table),
            }
            partitions.append(
                FabricPartition(
                    name=f"{table.name}_Partition",
                    mode="import",
                    source=partition_source,
                )
            )

        return FabricTable(
            name=table.name,
            columns=fabric_columns,
            measures=fabric_measures,
            partitions=partitions,
            isHidden=table.is_hidden,
            description=table.description,
        )

    def _create_m_expression(self, table: IntermediateTable) -> str:
        """Create an M (Power Query) expression for the table source."""
        if table.source_schema and table.source_table:
            return f'let\n    Source = Sql.Database("server", "database"),\n    Data = Source{{[Schema="{table.source_schema}",Item="{table.source_table}"]}}[Data]\nin\n    Data'
        elif table.source_table:
            return f'let\n    Source = #"{table.source_table}"\nin\n    Source'
        else:
            return 'let\n    Source = #"Source"\nin\n    Source'

    def _intermediate_relationship_to_fabric(
        self, rel: IntermediateRelationship
    ) -> FabricRelationship:
        """Convert an intermediate relationship to a Fabric relationship."""
        # Map cardinality
        from_card = "many"
        to_card = "one"

        if rel.cardinality == RelationshipCardinality.ONE_TO_ONE:
            from_card = "one"
            to_card = "one"
        elif rel.cardinality == RelationshipCardinality.ONE_TO_MANY:
            from_card = "one"
            to_card = "many"
        elif rel.cardinality == RelationshipCardinality.MANY_TO_MANY:
            from_card = "many"
            to_card = "many"
        # MANY_TO_ONE is the default

        # Map cross filter direction
        cross_filter = "singleDirection"
        if rel.cross_filter_direction.lower() in ("both", "bidirectional"):
            cross_filter = "bothDirections"

        return FabricRelationship(
            name=rel.name,
            fromTable=rel.from_table,
            fromColumn=rel.from_column,
            toTable=rel.to_table,
            toColumn=rel.to_column,
            fromCardinality=from_card,
            toCardinality=to_card,
            isActive=rel.is_active,
            crossFilteringBehavior=cross_filter,
        )
