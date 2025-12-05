"""
Microsoft Fabric semantic model definitions.

This module defines Pydantic models that represent Power BI semantic models
in the format required by Microsoft Fabric APIs and TMDL (Tabular Model
Definition Language) specification.

Reference: https://learn.microsoft.com/en-us/analysis-services/tmdl/tmdl-overview
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from semanticweaver.models.intermediate import IntermediateSemanticModel


class FabricColumn(BaseModel):
    """A column in a Fabric semantic model table."""

    name: str
    dataType: str
    sourceColumn: str | None = None
    isHidden: bool = False
    description: str | None = None
    formatString: str | None = None
    displayFolder: str | None = None
    summarizeBy: str = "none"
    lineageTag: str | None = None
    isKey: bool = False
    isNullable: bool = True

    def to_tmdl(self, indent: str = "\t") -> str:
        """
        Convert column to TMDL format.

        Returns:
            TMDL string representation of the column.
        """
        lines = []

        # Column declaration - quote names with special characters
        col_name = self._quote_name(self.name)
        lines.append(f"{indent}column {col_name}")

        # Properties (nested with additional indent)
        prop_indent = indent + "\t"

        lines.append(f"{prop_indent}dataType: {self.dataType}")

        if self.sourceColumn:
            lines.append(f"{prop_indent}sourceColumn: {self._quote_name(self.sourceColumn)}")

        if self.isHidden:
            lines.append(f"{prop_indent}isHidden: true")

        if self.isKey:
            lines.append(f"{prop_indent}isKey: true")

        if not self.isNullable:
            lines.append(f"{prop_indent}isNullable: false")

        if self.description:
            lines.append(f"{prop_indent}description: '''{self._escape_multiline(self.description)}'''")

        if self.formatString:
            lines.append(f"{prop_indent}formatString: {self.formatString}")

        if self.displayFolder:
            lines.append(f"{prop_indent}displayFolder: {self.displayFolder}")

        if self.summarizeBy and self.summarizeBy != "none":
            lines.append(f"{prop_indent}summarizeBy: {self.summarizeBy}")

        if self.lineageTag:
            lines.append(f"{prop_indent}lineageTag: {self.lineageTag}")

        return "\n".join(lines)

    def _quote_name(self, name: str) -> str:
        """Quote a name if it contains special characters or spaces."""
        if " " in name or any(c in name for c in "[]{}().,-+*/=<>!@#$%^&"):
            return f"'{name}'"
        return name

    def _escape_multiline(self, text: str) -> str:
        """Escape text for TMDL multiline string."""
        return text.replace("'''", "'''")


class FabricMeasure(BaseModel):
    """A measure in a Fabric semantic model."""

    name: str
    expression: str  # DAX expression
    description: str | None = None
    formatString: str | None = None
    displayFolder: str | None = None
    isHidden: bool = False
    lineageTag: str | None = None

    def to_tmdl(self, indent: str = "\t") -> str:
        """
        Convert measure to TMDL format.

        Returns:
            TMDL string representation of the measure.
        """
        lines = []

        # Measure declaration with expression
        measure_name = self._quote_name(self.name)

        # Single-line or multi-line expression
        if "\n" in self.expression:
            lines.append(f"{indent}measure {measure_name} =")
            lines.append(f"{indent}\t```")
            for expr_line in self.expression.split("\n"):
                lines.append(f"{indent}\t{expr_line}")
            lines.append(f"{indent}\t```")
        else:
            lines.append(f"{indent}measure {measure_name} = {self.expression}")

        # Properties
        prop_indent = indent + "\t"

        if self.description:
            lines.append(f"{prop_indent}description: '''{self._escape_multiline(self.description)}'''")

        if self.formatString:
            lines.append(f"{prop_indent}formatString: {self.formatString}")

        if self.displayFolder:
            lines.append(f"{prop_indent}displayFolder: {self.displayFolder}")

        if self.isHidden:
            lines.append(f"{prop_indent}isHidden: true")

        if self.lineageTag:
            lines.append(f"{prop_indent}lineageTag: {self.lineageTag}")

        return "\n".join(lines)

    def _quote_name(self, name: str) -> str:
        """Quote a name if it contains special characters or spaces."""
        if " " in name or any(c in name for c in "[]{}().,-+*/=<>!@#$%^&"):
            return f"'{name}'"
        return name

    def _escape_multiline(self, text: str) -> str:
        """Escape text for TMDL multiline string."""
        return text.replace("'''", "'''")


class FabricPartition(BaseModel):
    """A partition (data source) for a table."""

    name: str
    mode: str = "import"  # import, directQuery, dual
    source: dict[str, Any] = Field(default_factory=dict)

    def to_tmdl(self, indent: str = "\t") -> str:
        """
        Convert partition to TMDL format.

        Returns:
            TMDL string representation of the partition.
        """
        lines = []

        partition_name = self._quote_name(self.name)
        lines.append(f"{indent}partition {partition_name} = m")

        prop_indent = indent + "\t"

        lines.append(f"{prop_indent}mode: {self.mode}")

        # M expression
        if self.source.get("expression"):
            lines.append(f"{prop_indent}source =")
            lines.append(f"{prop_indent}\t```")
            for expr_line in self.source["expression"].split("\n"):
                lines.append(f"{prop_indent}\t{expr_line}")
            lines.append(f"{prop_indent}\t```")

        return "\n".join(lines)

    def _quote_name(self, name: str) -> str:
        """Quote a name if it contains special characters or spaces."""
        if " " in name or any(c in name for c in "[]{}().,-+*/=<>!@#$%^&"):
            return f"'{name}'"
        return name


class FabricTable(BaseModel):
    """A table in a Fabric semantic model."""

    name: str
    columns: list[FabricColumn] = Field(default_factory=list)
    measures: list[FabricMeasure] = Field(default_factory=list)
    partitions: list[FabricPartition] = Field(default_factory=list)
    isHidden: bool = False
    description: str | None = None
    lineageTag: str | None = None

    def to_tmdl(self) -> str:
        """
        Convert table to TMDL format.

        Returns:
            Complete TMDL file content for the table.
        """
        lines = []

        # Table declaration
        table_name = self._quote_name(self.name)
        lines.append(f"table {table_name}")

        # Table-level properties
        if self.description:
            lines.append(f"\tdescription: '''{self._escape_multiline(self.description)}'''")

        if self.isHidden:
            lines.append(f"\tisHidden: true")

        if self.lineageTag:
            lines.append(f"\tlineageTag: {self.lineageTag}")

        lines.append("")  # Empty line before columns

        # Columns
        for column in self.columns:
            lines.append(column.to_tmdl("\t"))
            lines.append("")

        # Measures
        for measure in self.measures:
            lines.append(measure.to_tmdl("\t"))
            lines.append("")

        # Partitions
        for partition in self.partitions:
            lines.append(partition.to_tmdl("\t"))
            lines.append("")

        return "\n".join(lines)

    def _quote_name(self, name: str) -> str:
        """Quote a name if it contains special characters or spaces."""
        if " " in name or any(c in name for c in "[]{}().,-+*/=<>!@#$%^&"):
            return f"'{name}'"
        return name

    def _escape_multiline(self, text: str) -> str:
        """Escape text for TMDL multiline string."""
        return text.replace("'''", "'''")


class FabricRelationship(BaseModel):
    """A relationship between tables in the semantic model."""

    name: str
    fromTable: str
    fromColumn: str
    toTable: str
    toColumn: str
    fromCardinality: str = "many"  # one, many
    toCardinality: str = "one"  # one, many
    isActive: bool = True
    crossFilteringBehavior: str = "singleDirection"  # singleDirection, bothDirections

    def to_tmdl(self, indent: str = "") -> str:
        """
        Convert relationship to TMDL format.

        Returns:
            TMDL string representation of the relationship.
        """
        lines = []

        # Relationship declaration with from/to specification
        from_table = self._quote_name(self.fromTable)
        from_col = self._quote_name(self.fromColumn)
        to_table = self._quote_name(self.toTable)
        to_col = self._quote_name(self.toColumn)

        lines.append(f"{indent}relationship {self._quote_name(self.name)}")
        lines.append(f"{indent}\tfromColumn: {from_table}[{from_col}]")
        lines.append(f"{indent}\ttoColumn: {to_table}[{to_col}]")

        # Cardinality
        lines.append(f"{indent}\tfromCardinality: {self.fromCardinality}")
        lines.append(f"{indent}\ttoCardinality: {self.toCardinality}")

        if not self.isActive:
            lines.append(f"{indent}\tisActive: false")

        if self.crossFilteringBehavior != "singleDirection":
            lines.append(f"{indent}\tcrossFilteringBehavior: {self.crossFilteringBehavior}")

        return "\n".join(lines)

    def _quote_name(self, name: str) -> str:
        """Quote a name if it contains special characters or spaces."""
        if " " in name or any(c in name for c in "[]{}().,-+*/=<>!@#$%^&"):
            return f"'{name}'"
        return name


class FabricSemanticModel(BaseModel):
    """
    A complete Fabric semantic model definition.

    This model can be serialized to JSON/TMSL format for deployment
    to Microsoft Fabric via REST APIs, or to TMDL folder format for
    source control and human-readable representation.
    """

    name: str
    description: str | None = None
    tables: list[FabricTable] = Field(default_factory=list)
    relationships: list[FabricRelationship] = Field(default_factory=list)

    # Model configuration
    defaultMode: str = "import"  # import, directQuery
    culture: str = "en-US"

    def to_tmsl(self) -> dict[str, Any]:
        """
        Convert to TMSL (Tabular Model Scripting Language) format.

        Returns:
            Dictionary representation in TMSL format for Fabric API.
        """
        return {
            "createOrReplace": {
                "object": {
                    "database": self.name
                },
                "database": {
                    "name": self.name,
                    "model": {
                        "culture": self.culture,
                        "defaultMode": self.defaultMode,
                        "tables": [self._table_to_tmsl(table) for table in self.tables],
                        "relationships": [self._relationship_to_tmsl(rel) for rel in self.relationships]
                    }
                }
            }
        }

    def _table_to_tmsl(self, table: FabricTable) -> dict[str, Any]:
        """Convert a table to TMSL format."""
        result: dict[str, Any] = {
            "name": table.name,
            "columns": [
                {
                    "name": col.name,
                    "dataType": col.dataType,
                    "sourceColumn": col.sourceColumn,
                    "isHidden": col.isHidden,
                    "summarizeBy": col.summarizeBy,
                }
                for col in table.columns
            ],
            "measures": [
                {
                    "name": measure.name,
                    "expression": measure.expression,
                    "formatString": measure.formatString,
                    "isHidden": measure.isHidden,
                }
                for measure in table.measures
            ],
            "partitions": [
                {
                    "name": partition.name,
                    "mode": partition.mode,
                    "source": partition.source,
                }
                for partition in table.partitions
            ],
        }

        if table.description:
            result["description"] = table.description

        return result

    def _relationship_to_tmsl(self, rel: FabricRelationship) -> dict[str, Any]:
        """Convert a relationship to TMSL format."""
        return {
            "name": rel.name,
            "fromTable": rel.fromTable,
            "fromColumn": rel.fromColumn,
            "toTable": rel.toTable,
            "toColumn": rel.toColumn,
            "fromCardinality": rel.fromCardinality,
            "toCardinality": rel.toCardinality,
            "isActive": rel.isActive,
            "crossFilteringBehavior": rel.crossFilteringBehavior,
        }

    def to_tmdl(self) -> dict[str, str]:
        """
        Convert to TMDL (Tabular Model Definition Language) format.

        Returns:
            Dictionary mapping file paths to TMDL content.
            Keys are relative paths like 'model.tmdl', 'tables/TableName.tmdl'
        """
        files: dict[str, str] = {}

        # Generate database.tmdl
        files["database.tmdl"] = self._generate_database_tmdl()

        # Generate model.tmdl
        files["model.tmdl"] = self._generate_model_tmdl()

        # Generate table files
        for table in self.tables:
            table_filename = self._sanitize_filename(table.name)
            files[f"tables/{table_filename}.tmdl"] = table.to_tmdl()

        # Generate relationships.tmdl (if any relationships)
        if self.relationships:
            files["relationships.tmdl"] = self._generate_relationships_tmdl()

        return files

    def _generate_database_tmdl(self) -> str:
        """Generate the database.tmdl file content."""
        lines = [
            f"database {self._quote_name(self.name)}",
            "",
        ]

        if self.description:
            lines.insert(1, f"\tdescription: '''{self._escape_multiline(self.description)}'''")

        return "\n".join(lines)

    def _generate_model_tmdl(self) -> str:
        """Generate the model.tmdl file content."""
        lines = [
            "model Model",
            f"\tculture: {self.culture}",
            f"\tdefaultPowerBIDataSourceVersion: powerBI_V3",
        ]

        if self.defaultMode:
            mode_map = {"import": "import", "directQuery": "directQuery", "dual": "dual"}
            lines.append(f"\tdefaultMode: {mode_map.get(self.defaultMode, 'import')}")

        lines.append("")
        return "\n".join(lines)

    def _generate_relationships_tmdl(self) -> str:
        """Generate the relationships.tmdl file content."""
        lines = []

        for rel in self.relationships:
            lines.append(rel.to_tmdl())
            lines.append("")

        return "\n".join(lines)

    def write_tmdl_folder(self, output_path: str | Path) -> None:
        """
        Write the semantic model to a TMDL folder structure.

        Creates the standard TMDL folder layout:
        - database.tmdl
        - model.tmdl
        - tables/
          - TableName.tmdl
        - relationships.tmdl (if relationships exist)

        Args:
            output_path: Path to the output folder.
        """
        output_path = Path(output_path)
        output_path.mkdir(parents=True, exist_ok=True)

        # Create tables subfolder
        tables_path = output_path / "tables"
        tables_path.mkdir(exist_ok=True)

        # Get all TMDL files
        tmdl_files = self.to_tmdl()

        # Write each file
        for relative_path, content in tmdl_files.items():
            file_path = output_path / relative_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")

    def _quote_name(self, name: str) -> str:
        """Quote a name if it contains special characters or spaces."""
        if " " in name or any(c in name for c in "[]{}().,-+*/=<>!@#$%^&"):
            return f"'{name}'"
        return name

    def _escape_multiline(self, text: str) -> str:
        """Escape text for TMDL multiline string."""
        return text.replace("'''", "'''")

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize a name for use as a filename."""
        # Replace invalid filename characters
        invalid_chars = '<>:"/\\|?*'
        result = name
        for char in invalid_chars:
            result = result.replace(char, "_")
        return result

    @classmethod
    def from_intermediate(cls, intermediate: IntermediateSemanticModel) -> FabricSemanticModel:
        """
        Create a Fabric semantic model from intermediate representation.

        Args:
            intermediate: The intermediate semantic model.

        Returns:
            FabricSemanticModel ready for deployment.
        """
        # This is a convenience method - the actual transformation
        # logic is in SemanticModelTransformer.to_fabric_model()
        from semanticweaver.core.transformer import SemanticModelTransformer

        transformer = SemanticModelTransformer()
        return transformer.to_fabric_model(intermediate)
