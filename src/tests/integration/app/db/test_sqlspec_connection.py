# SPDX-FileCopyrightText: 2026 Google LLC
# SPDX-License-Identifier: Apache-2.0

"""Integration tests for SQLSpec database connection and configuration using PostgreSQL."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlspec.adapters.asyncpg import AsyncpgDriver

pytestmark = pytest.mark.anyio


@dataclass(frozen=True)
class SelectCase:
    sql: str
    params: dict[str, Any]
    assert_result: Callable[[Any], None]


def _assert_basic_select(result: Any) -> None:
    assert result is not None
    assert result["test_value"] == 1


def _assert_dict_access(result: Any) -> None:
    assert result is not None
    assert result["str_value"] == "test"
    assert result["int_value"] == 123
    assert result["float_value"] == 45.67


def _assert_parameter_binding(result: Any) -> None:
    assert result is not None
    assert result["value"] == "test_value"


class TestSQLSpecConnection:
    """Test suite for SQLSpec database connection and pool configuration."""

    async def test_driver_connection(self, driver: AsyncpgDriver) -> None:
        """Test that SQLSpec driver connects successfully."""
        assert driver is not None
        assert hasattr(driver, "select")
        assert hasattr(driver, "execute")

    @pytest.mark.parametrize(
        "case",
        [
            SelectCase(
                sql="SELECT 1 as test_value",
                params={},
                assert_result=_assert_basic_select,
            ),
            SelectCase(
                sql="""
                SELECT
                    'test' as str_value,
                    123 as int_value,
                    45.67::double precision as float_value
                """,
                params={},
                assert_result=_assert_dict_access,
            ),
            SelectCase(
                sql="SELECT :param1 as value",
                params={"param1": "test_value"},
                assert_result=_assert_parameter_binding,
            ),
        ],
        ids=("basic-select", "dict-access", "parameter-binding"),
    )
    async def test_select_one_cases(self, driver: AsyncpgDriver, case: SelectCase) -> None:
        """Exercise representative SQLSpec select_one_or_none result contracts."""
        result = await driver.select_one_or_none(case.sql, **case.params)
        case.assert_result(result)

    async def test_select_multiple_rows(self, driver: AsyncpgDriver) -> None:
        """Test SELECT returning multiple rows using generate_series."""
        results = await driver.select(
            """
            SELECT i as row_num
            FROM generate_series(1, 5) AS t(i)
            """
        )

        assert isinstance(results, list)
        assert len(results) == 5
        # Verify dict access for each row
        for i, row in enumerate(results, 1):
            assert row["row_num"] == i

    async def test_execute_with_rowcount(self, driver: AsyncpgDriver) -> None:
        """Test execute returns SQLResult with rows_affected."""
        # Create a temp table for testing
        await driver.execute("DROP TABLE IF EXISTS test_sqlspec_tmp")
        await driver.execute("CREATE TABLE test_sqlspec_tmp (id INTEGER, value VARCHAR(100))")

        try:
            # Insert and check rowcount
            result = await driver.execute(
                "INSERT INTO test_sqlspec_tmp (id, value) VALUES (:id, :value)",
                id=1,
                value="test",
            )
            assert result.rows_affected == 1
        finally:
            # Cleanup
            await driver.execute("DROP TABLE IF EXISTS test_sqlspec_tmp")

    async def test_transaction_support(self, driver: AsyncpgDriver) -> None:
        """Test transaction begin/commit/rollback support."""
        assert hasattr(driver, "begin")
        assert hasattr(driver, "commit")
        assert hasattr(driver, "rollback")

    async def test_postgres_vector_type_support(self, driver: AsyncpgDriver) -> None:
        """Test that pgvector VECTOR type is supported in the database."""
        result = await driver.select_one_or_none(
            """
            SELECT column_name, data_type, udt_name
            FROM information_schema.columns
            WHERE table_name = 'product'
            AND column_name = 'embedding'
            """
        )

        assert result is not None
        assert result["column_name"] == "embedding"
        assert result["data_type"] == "USER-DEFINED"
        assert result["udt_name"] == "vector"

    async def test_postgres_upsert_statement_support(self, driver: AsyncpgDriver) -> None:
        """Test that PostgreSQL INSERT ... ON CONFLICT statements work."""
        # Create temp table
        await driver.execute("DROP TABLE IF EXISTS test_merge_tmp")
        await driver.execute("CREATE TABLE test_merge_tmp (id INTEGER PRIMARY KEY, value VARCHAR(100))")

        try:
            # Test INSERT (initial insert)
            await driver.execute(
                """
                INSERT INTO test_merge_tmp (id, value)
                VALUES (:id, :value)
                ON CONFLICT (id) DO UPDATE SET value = EXCLUDED.value
                """,
                id=1,
                value="first",
            )

            # Verify insert
            result = await driver.select_one_or_none(
                "SELECT value FROM test_merge_tmp WHERE id = :id",
                id=1,
            )
            assert result["value"] == "first"

            # Update via ON CONFLICT DO UPDATE
            await driver.execute(
                """
                INSERT INTO test_merge_tmp (id, value)
                VALUES (:id, :value)
                ON CONFLICT (id) DO UPDATE SET value = EXCLUDED.value
                """,
                id=1,
                value="updated",
            )

            # Verify update
            result = await driver.select_one_or_none(
                "SELECT value FROM test_merge_tmp WHERE id = :id",
                id=1,
            )
            assert result["value"] == "updated"
        finally:
            # Cleanup
            await driver.execute("DROP TABLE IF EXISTS test_merge_tmp")

    async def test_insert_and_fetch_generated_identity(self, driver: AsyncpgDriver) -> None:
        """Test identity insert by selecting the generated row."""
        # Create temp table
        await driver.execute("DROP TABLE IF EXISTS test_returning_tmp")
        await driver.execute("CREATE TABLE test_returning_tmp (id SERIAL PRIMARY KEY, value VARCHAR(100))")

        try:
            value = "test_returning"
            insert_result = await driver.execute(
                "INSERT INTO test_returning_tmp (value) VALUES (:value)",
                value=value,
            )
            assert insert_result.rows_affected == 1

            result = await driver.select_one_or_none(
                """
                SELECT id, value
                FROM test_returning_tmp
                WHERE value = :value
                ORDER BY id DESC
                LIMIT 1
                """,
                value=value,
            )

            assert result is not None
            assert "id" in result
            assert result["id"] > 0
            assert result["value"] == value
        finally:
            # Cleanup
            await driver.execute("DROP TABLE IF EXISTS test_returning_tmp")
