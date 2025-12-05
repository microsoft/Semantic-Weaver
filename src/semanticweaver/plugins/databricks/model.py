"""
Databricks-specific configuration models.

This module defines Pydantic models for Databricks configuration
and Unity Catalog semantic model definitions based on the
Databricks Metric Views YAML specification v1.1.

Reference: https://learn.microsoft.com/en-us/azure/databricks/metric-views/data-modeling/syntax
"""


from pydantic import BaseModel, Field

from semanticweaver.models.base import BaseSourceMap
from semanticweaver.plugins.base import BaseSourcePlugin


class CatalogConfig(BaseModel):
    """Configuration for a catalog with optional schema filtering."""

    name: str = Field(..., description="Unity Catalog name")
    schemas: list[str] | None = Field(
        None,
        description="List of schema names to include. None or omitted means all schemas.",
    )


class DatabricksConfig(BaseModel):
    """Databricks-specific configuration."""

    workspace_url: str = Field(
        ...,
        description="Databricks workspace URL (e.g., https://adb-xxx.azuredatabricks.net/)",
    )
    account_id: str = Field(..., description="Databricks account ID")
    account_api_token: str = Field(..., description="Databricks API token or OAuth secret")

    # Catalog configuration - at least one catalog is required
    catalogs: list[CatalogConfig] = Field(
        ...,
        min_length=1,
        description="List of catalogs to process. Each catalog can optionally filter schemas.",
    )

    # Optional settings
    http_timeout: int = Field(30, description="HTTP request timeout in seconds")

    @property
    def default_catalog(self) -> str:
        """Get the first catalog name (for backward compatibility)."""
        return self.catalogs[0].name

    def get_catalog_names(self) -> list[str]:
        """Get list of all catalog names."""
        return [c.name for c in self.catalogs]

    def get_schemas_for_catalog(self, catalog_name: str) -> list[str] | None:
        """
        Get the schema filter for a specific catalog.

        Returns:
            List of schema names to filter, or None if all schemas should be included.
        """
        for catalog in self.catalogs:
            if catalog.name == catalog_name:
                return catalog.schemas
        return None


class DatabricksSourceMap(BaseSourceMap):
    """
    Configuration model for Databricks source.

    Extends BaseSourceMap with Databricks-specific settings.
    """

    databricks: DatabricksConfig = Field(..., description="Databricks configuration")

    def get_plugin(self) -> "BaseSourcePlugin":
        """
        Get the Databricks source plugin.

        Returns:
            DatabricksPlugin instance configured for extraction.
        """
        from semanticweaver.plugins.databricks.plugin import DatabricksPlugin

        return DatabricksPlugin(self)


# ============================================================================
# Databricks Metric Views Format Specification Models (YAML v1.1)
# Reference: https://learn.microsoft.com/en-us/azure/databricks/metric-views/data-modeling/syntax
# ============================================================================


class DecimalPlaces(BaseModel):
    """Decimal places configuration for numeric formats."""

    type: str = Field(
        ...,
        description="Decimal places type: 'max', 'exact', or 'all'",
    )
    places: int | None = Field(
        None,
        ge=0,
        le=10,
        description="Number of decimal places (0-10, required if type is 'max' or 'exact')",
    )


class NumberFormat(BaseModel):
    """Number format specification for measures."""

    type: str = Field("number", description="Format type: 'number'")
    decimal_places: DecimalPlaces | None = Field(None, description="Decimal places configuration")
    hide_group_separator: bool | None = Field(
        None,
        description="When true, removes number grouping separator (e.g., comma)",
    )
    abbreviation: str | None = Field(
        None,
        description="Abbreviation style: 'none', 'compact', or 'scientific'",
    )


class CurrencyFormat(BaseModel):
    """Currency format specification for monetary measures."""

    type: str = Field("currency", description="Format type: 'currency'")
    currency_code: str = Field(
        ...,
        description="ISO-4217 currency code (e.g., 'USD', 'EUR', 'JPY')",
    )
    decimal_places: DecimalPlaces | None = Field(None, description="Decimal places configuration")
    hide_group_separator: bool | None = Field(
        None,
        description="When true, removes number grouping separator",
    )
    abbreviation: str | None = Field(
        None,
        description="Abbreviation style: 'none', 'compact', or 'scientific'",
    )


class PercentageFormat(BaseModel):
    """Percentage format specification for ratio measures."""

    type: str = Field("percentage", description="Format type: 'percentage'")
    decimal_places: DecimalPlaces | None = Field(None, description="Decimal places configuration")
    hide_group_separator: bool | None = Field(
        None,
        description="When true, removes number grouping separator",
    )


class DateFormat(BaseModel):
    """Date format specification for date dimensions."""

    type: str = Field("date", description="Format type: 'date'")
    date_format: str = Field(
        ...,
        description=(
            "Date display format: 'locale_short_month', 'locale_long_month', "
            "'year_month_day', 'locale_number_month', or 'year_week'"
        ),
    )
    leading_zeros: bool | None = Field(
        None,
        description="Whether single digit numbers are preceded by a zero",
    )


class DateTimeFormat(BaseModel):
    """DateTime format specification for timestamp dimensions."""

    type: str = Field("date_time", description="Format type: 'date_time'")
    date_format: str | None = Field(
        None,
        description=(
            "Date display format: 'no_date', 'locale_short_month', 'locale_long_month', "
            "'year_month_day', 'locale_number_month', or 'year_week'"
        ),
    )
    time_format: str | None = Field(
        None,
        description=(
            "Time display format: 'no_time', 'locale_hour_minute', or 'locale_hour_minute_second'"
        ),
    )
    leading_zeros: bool | None = Field(
        None,
        description="Whether single digit numbers are preceded by a zero",
    )


# Union type for all format specifications
FormatSpecification = NumberFormat | CurrencyFormat | PercentageFormat | DateFormat | DateTimeFormat


class WindowSpecification(BaseModel):
    """
    Window specification for time-series measures.
    
    Reference: https://learn.microsoft.com/en-us/azure/databricks/metric-views/data-modeling/syntax#define-a-measure
    """

    order: str = Field(..., description="Dimension to order by (typically a date dimension)")
    semiadditive: str | None = Field(
        None,
        description="Semiadditive aggregation type: 'first' or 'last'",
    )
    range: str | None = Field(
        None,
        description="Time range specification (e.g., 'trailing 30 day', 'between 7 day ago and 1 day ago')",
    )


class DatabricksMeasure(BaseModel):
    """
    Represents a measure definition from Databricks Metric Views (YAML v1.1).

    Measures are aggregate expression columns that define calculations
    like SUM, COUNT, AVG, etc.

    Reference: https://learn.microsoft.com/en-us/azure/databricks/metric-views/data-modeling/syntax#define-a-measure
    """

    name: str = Field(..., description="Measure name (unique identifier)")
    expr: str = Field(
        ...,
        description=(
            "SQL aggregate expression (e.g., 'SUM(o_totalprice)', "
            "'COUNT(1)', 'SUM(revenue) / COUNT(DISTINCT customer_id)')"
        ),
    )
    comment: str | None = Field(None, description="Description of the measure (Unity Catalog comment)")
    display_name: str | None = Field(
        None,
        max_length=255,
        description="Human-readable label for visualization tools",
    )
    format: FormatSpecification | None = Field(
        None,
        description="Format specification for displaying the measure value",
    )
    window: list[WindowSpecification] = Field(
        default_factory=list,
        description="Window specifications for time-series aggregations",
    )
    synonyms: list[str] = Field(
        default_factory=list,
        max_length=10,
        description="Alternative names for LLM tools (max 10, each max 255 chars)",
    )


class DatabricksDimension(BaseModel):
    """
    Represents a dimension definition from Databricks Metric Views (YAML v1.1).

    Dimensions define the grouping/filtering columns for metrics.

    Reference: https://learn.microsoft.com/en-us/azure/databricks/metric-views/data-modeling/syntax#define-a-dimension
    """

    name: str = Field(..., description="Dimension name (unique identifier)")
    expr: str = Field(
        ...,
        description=(
            "Column reference or SQL expression "
            "(e.g., 'o_orderdate', 'DATE_TRUNC(\"MONTH\", order_date)')"
        ),
    )
    comment: str | None = Field(None, description="Description of the dimension (Unity Catalog comment)")
    display_name: str | None = Field(
        None,
        max_length=255,
        description="Human-readable label for visualization tools",
    )
    format: FormatSpecification | None = Field(
        None,
        description="Format specification for displaying the dimension value",
    )
    synonyms: list[str] = Field(
        default_factory=list,
        max_length=10,
        description="Alternative names for LLM tools (max 10, each max 255 chars)",
    )


class DatabricksMetricView(BaseModel):
    """
    Represents a Metric View object from Databricks Unity Catalog (YAML v1.1).

    Metric Views are semantic layer objects that define measures, dimensions,
    and filters on top of tables in Unity Catalog.

    Reference: https://learn.microsoft.com/en-us/azure/databricks/metric-views/data-modeling/syntax#yaml-overview
    """

    # Required fields
    version: str = Field("1.1", description="Metric View YAML specification version")
    source: str = Field(
        ...,
        description="Source data: table reference (catalog.schema.table) or SQL query",
    )

    # Arrays of dimensions and measures
    dimensions: list[DatabricksDimension] = Field(
        default_factory=list,
        description="Array of dimension definitions",
    )
    measures: list[DatabricksMeasure] = Field(
        default_factory=list,
        description="Array of measure (aggregate) definitions",
    )

    # Optional fields
    comment: str | None = Field(None, description="Description of the metric view")
    filter: str | None = Field(
        None,
        description="SQL boolean expression applied to all queries (WHERE clause)",
    )
    joins: list[dict] | None = Field(
        None,
        description="Star schema and snowflake schema join definitions",
    )

    # Metadata fields (not part of YAML spec, but useful for tracking)
    name: str | None = Field(None, description="Metric View name in Unity Catalog")
    catalog_name: str | None = Field(None, description="Unity Catalog name")
    schema_name: str | None = Field(None, description="Schema name containing the Metric View")


# ============================================================================
# Legacy models (kept for backward compatibility)
# ============================================================================


class DatabricksMetricDefinition(DatabricksMeasure):
    """
    Legacy alias for DatabricksMeasure.

    Deprecated: Use DatabricksMeasure instead.
    """

    pass


class DatabricksEntity(BaseModel):
    """Represents an entity (fact table) from Databricks Metric Views."""

    name: str = Field(..., description="Entity name")
    table_name: str = Field(..., description="Source table name")
    schema_name: str = Field(..., description="Schema name")
    catalog_name: str = Field(..., description="Catalog name")

    dimensions: list[DatabricksDimension] = Field(default_factory=list)
    measures: list[DatabricksMeasure] = Field(default_factory=list)


class DatabricksSemanticModel(BaseModel):
    """
    Represents the full semantic model definition from Databricks.

    This captures Metric Views, entities, dimensions, and metrics
    as defined in Unity Catalog.
    """

    name: str = Field(..., description="Model name")
    catalog_name: str = Field(..., description="Unity Catalog name")
    description: str | None = Field(None, description="Model description")

    entities: list[DatabricksEntity] = Field(default_factory=list)

    # Metric View this model was derived from (if applicable)
    source_metric_view: DatabricksMetricView | None = Field(
        None,
        description="The Metric View this model was created from",
    )
