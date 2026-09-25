"""Utilities for connecting to and querying against a sqlite3 database."""

import os
from typing import Any

import aiosqlite


class AsyncSqliteDatabase:
    """Makes asynchonous connections to & queries against a valid sqlite3 database.

    Attributes:
        database_directory: Directory to a valid sqlite database file.
    """

    def __init__(self, database_path: str):
        """Initialize AsyncSqliteDatabase instance.

        Args:
            database_path: Path to a valid sqlite database file.

        Raises:
            FIleNotFoundError: If the directory provided cannot be found.
        """
        if not os.path.exists(database_path):
            raise FileNotFoundError(f"{database_path} does not exist.")

        self.database_path = database_path
        self._connection: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Connect to database asynchronously."""
        if self._connection is None:
            self._connection = await aiosqlite.connect(self.database_path)
            await self._connection.execute("PRAGMA journal_mode=WAL;")

    async def close(self) -> None:
        """Close database connection."""
        if self._connection is not None:
            await self._connection.close()
            self._connection = None

    async def execute_query(self, query: str, *parameters: Any) -> list[tuple]:
        """Execute a sqlite query against the database.

        Args:
            query: SQL query to execute.
            *parameters: Optional parameters to be passed to the query.

        Returns:
            A list of tuples, where each tuple represents a row of results.
        """
        if self._connection is None:
            raise RuntimeError("Database connection has not been made.")

        async with self._connection.execute(query, parameters) as cursor:
            results = await cursor.fetchall()

        await self._connection.commit()
        return results
