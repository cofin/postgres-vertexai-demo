# SPDX-FileCopyrightText: 2026 Google LLC
# SPDX-License-Identifier: Apache-2.0

"""Generic fixture management utilities for database operations.

This module provides a clean, generic approach to loading and exporting fixtures
without table-specific logic. Uses SQLSpec for database operations.
"""

import gzip
import re
from collections.abc import Mapping
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

from sqlspec import sql

from app.utils.serialization import from_json, to_json

_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _validate_identifier(name: str) -> str:
    """Validate and normalize an SQL identifier.

    Args:
        name: Potential identifier value

    Returns:
        The cleaned identifier

    Raises:
        ValueError: If identifier contains unsafe characters.
    """
    normalized = name.strip().strip('"')
    if not _IDENTIFIER_RE.fullmatch(normalized):
        msg = f"Invalid identifier: {name!r}"
        raise ValueError(msg)
    return normalized


class FixtureProcessor:
    """Handles fixture data processing with proper serialization."""

    def __init__(self, fixtures_dir: Path) -> None:
        """Initialize the fixture processor.

        Args:
            fixtures_dir: Path to the fixtures directory
        """
        self.fixtures_dir = fixtures_dir

    def load_fixture_data(self, filepath: Path) -> list[dict[str, Any]]:
        """Load fixture data from file, handling compression.

        Args:
            filepath: Path to fixture file

        Returns:
            List of fixture records
        """
        if filepath.suffix == ".gz":
            with gzip.open(filepath, "rb") as f:
                data = f.read()
        else:
            with filepath.open("rb") as f:
                data = f.read()

        data_list = from_json(data)
        if isinstance(data_list, list):
            return [dict(item) if isinstance(item, Mapping) else item for item in data_list]
        return []

    def prepare_record(self, record: dict[str, Any]) -> Mapping[str, Any]:
        """Prepare a record for insertion by handling None values and data types properly.

        Args:
            record: Raw fixture record

        Returns:
            Processed record ready for insertion
        """
        prepared: dict[str, Any] = {}
        for key, value in record.items():
            if value is None:
                if key == "is_enabled":
                    prepared[key] = True
                continue
            if key == "embedding":
                if isinstance(value, list):
                    prepared[key] = str(value)
                elif isinstance(value, str):
                    cleaned = value.replace("\n", " ")
                    cleaned = re.sub(r"\s+", " ", cleaned).strip()
                    try:
                        if cleaned.startswith("[") and cleaned.endswith("]"):
                            numbers_str = cleaned[1:-1].strip()
                            float_values = [float(x) for x in numbers_str.split() if x.strip()]
                            prepared[key] = str(float_values)
                        else:
                            float_values = [float(x) for x in cleaned.split() if x.strip()]
                            prepared[key] = str(float_values)
                    except (ValueError, TypeError):
                        continue
            elif key in {"created_at", "updated_at", "last_activity", "expires_at", "last_accessed"} and isinstance(
                value, str
            ):
                prepared[key] = datetime.fromisoformat(value)
            elif isinstance(value, (datetime, date, time)):
                prepared[key] = value.isoformat()
            else:
                prepared[key] = value
        return prepared

    def get_fixture_files(self, table_order: list[str] | None = None) -> list[Path]:
        """Get all available fixture files sorted by dependency order.

        Args:
            table_order: Optional list defining table loading order

        Returns:
            List of fixture file paths in dependency order
        """
        if not self.fixtures_dir.exists():
            return []

        files = list(self.fixtures_dir.glob("*.json")) + list(self.fixtures_dir.glob("*.json.gz"))

        if table_order is None:
            return files

        def sort_key(filepath: Path) -> int:
            try:
                return table_order.index(self.get_table_name(filepath.name))
            except ValueError:
                # tables not in table_order sort after all known ones
                return len(table_order)

        return sorted(files, key=sort_key)

    def get_table_name(self, filename: str) -> str:
        """Extract table name from fixture filename.

        Args:
            filename: Fixture filename

        Returns:
            Table name
        """
        return filename.replace(".json.gz", "").replace(".json", "")


class FixtureLoader:
    """Generic fixture loader that works with any table using SQLSpec."""

    def __init__(
        self,
        fixtures_dir: Path,
        driver: Any,
        table_order: list[str] | None = None,
        conflict_keys: dict[str, str] | None = None,
    ) -> None:
        """Initialize the fixture loader.

        Args:
            fixtures_dir: Path to fixtures directory
            driver: SQLSpec driver instance for database operations
            table_order: Optional list defining table loading order for dependencies
            conflict_keys: Per-table conflict column for upsert (defaults to ``"id"``).
        """
        self.processor = FixtureProcessor(fixtures_dir)
        self.driver = driver
        self.table_order = table_order or []
        self.conflict_keys = conflict_keys or {}

    async def load_all_fixtures(self, specific_tables: list[str] | None = None) -> dict[str, dict[str, Any] | str]:
        """Load all available fixtures into the database.

        Args:
            specific_tables: Optional list of specific tables to load

        Returns:
            Dictionary mapping table names to loading results
        """
        results: dict[str, dict[str, Any] | str] = {}
        fixture_files = self.processor.get_fixture_files(self.table_order)

        if not fixture_files and not specific_tables:
            return self._generate_missing_fixtures_results()

        for fixture_file in fixture_files:
            table_name = self.processor.get_table_name(fixture_file.name)

            if specific_tables and table_name not in specific_tables:
                continue

            try:
                result = await self._load_table_fixtures(table_name, fixture_file)
                results[table_name] = result
            except Exception as e:  # noqa: BLE001
                results[table_name] = f"Error: {e!s}"

        return results

    async def _load_table_fixtures(self, table_name: str, fixture_file: Path) -> dict[str, Any]:
        """Load fixtures for a table using an idempotent upsert strategy.

        For PostgreSQL, this uses `INSERT ... ON CONFLICT ... DO UPDATE`.

        Args:
            table_name: Name of the table
            fixture_file: Path to fixture file

        Returns:
            Loading result statistics with keys: upserted, failed, total
        """
        fixture_data = self.processor.load_fixture_data(fixture_file)

        if not fixture_data:
            return {"upserted": 0, "failed": 0, "total": 0}

        total = len(fixture_data)
        processed_records = [dict(self.processor.prepare_record(record)) for record in fixture_data]

        if not processed_records:
            return {"upserted": 0, "failed": 0, "total": 0}

        conflict_col = self.conflict_keys.get(table_name, "id")

        for record in processed_records:
            if conflict_col not in record:
                msg = f"Fixture records for '{table_name}' must have a '{conflict_col}' column for upserting."
                raise ValueError(msg)

        records_by_columns: dict[tuple[str, ...], list[dict[str, Any]]] = {}
        for record in processed_records:
            columns = tuple(sorted(record.keys()))
            records_by_columns.setdefault(columns, []).append(record)

        async with self.driver.connection.transaction():
            for columns, records in records_by_columns.items():
                insert_cols_str = ", ".join(f'"{c}"' for c in columns)
                insert_vals_str = ", ".join(f"${i + 1}" for i in range(len(columns)))
                update_columns = [col for col in columns if col != conflict_col]

                if update_columns:
                    update_set_str = ", ".join(f'"{col}" = EXCLUDED."{col}"' for col in update_columns)
                    conflict_clause = f"ON CONFLICT ({conflict_col}) DO UPDATE SET {update_set_str}"
                else:
                    conflict_clause = f"ON CONFLICT ({conflict_col}) DO NOTHING"

                validated_table = _validate_identifier(table_name)
                upsert_sql = f"""
                    INSERT INTO "{validated_table}" ({insert_cols_str})
                    VALUES ({insert_vals_str})
                    {conflict_clause}
                """

                data_to_insert = [tuple(record.get(col) for col in columns) for record in records]
                await self.driver.execute_many(upsert_sql, data_to_insert)
        return {"upserted": total, "failed": 0, "total": total}

    def _generate_missing_fixtures_results(self) -> dict[str, dict[str, Any] | str]:
        """Generate error results for missing fixture files.

        Returns:
            Dictionary with error messages for default tables
        """
        return {table_name: f"Error: Could not find the {table_name} fixture" for table_name in self.table_order}


class FixtureExporter:
    """Generic fixture exporter that works with any table using SQLSpec."""

    def __init__(self, fixtures_dir: Path, driver: Any, table_order: list[str] | None = None) -> None:
        """Initialize the fixture exporter.

        Args:
            fixtures_dir: Path to fixtures directory
            driver: SQLSpec driver instance for database operations
            table_order: Optional list of tables to export
        """
        self.processor = FixtureProcessor(fixtures_dir)
        self.driver = driver
        self.table_order = table_order or []

    async def export_all_fixtures(
        self, tables: list[str] | None = None, output_dir: Path | None = None, compress: bool = True
    ) -> dict[str, str]:
        """Export database tables to fixture files.

        Args:
            tables: Optional list of specific tables to export
            output_dir: Output directory (defaults to fixtures dir)
            compress: Whether to gzip compress output

        Returns:
            Dictionary mapping table names to output paths or error messages
        """
        if output_dir is None:
            output_dir = self.processor.fixtures_dir

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        results = {}

        if tables is None:
            tables = self.table_order

        for table_name in tables:
            try:
                result = await self._export_table(table_name, output_dir, compress)
                results[table_name] = result
            except Exception as e:  # noqa: BLE001
                results[table_name] = f"Error: {e!s}"

        return results

    async def _export_table(self, table_name: str, output_dir: Path, compress: bool) -> str:
        """Export a specific table to fixture file.

        Args:
            table_name: Name of table to export
            output_dir: Output directory
            compress: Whether to compress output

        Returns:
            Path to output file or "No data found"
        """
        records = await self.driver.select(sql.select("*").from_(table_name))

        if not records:
            return "No data found"

        json_data = []
        for record in records:
            record_dict = dict(record)
            for key, value in record_dict.items():
                if hasattr(value, "isoformat"):
                    record_dict[key] = value.isoformat()
                elif isinstance(value, bytes):
                    try:
                        record_dict[key] = value.decode("utf-8")
                    except UnicodeDecodeError:
                        record_dict[key] = value.hex()
            json_data.append(record_dict)
        filename = f"{table_name}.json"
        if compress:
            filename = f"{filename}.gz"

        output_file = output_dir / filename

        json_bytes = to_json(json_data, as_bytes=True)

        if compress:
            with gzip.open(output_file, "wb") as f:
                f.write(json_bytes)
        else:
            with output_file.open("wb") as f:
                f.write(json_bytes)

        return str(output_file)
