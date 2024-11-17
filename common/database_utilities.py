"""Utilities for connecting to and querying against a sqlite3 database."""

import os
import sqlite3
from typing import Any


class SqliteDatabase:
    """Makes connections to & queries against a valid sqlite3 database.

    Attributes:
        database_directory: Directory to a valid sqlite database file.
    """

    def __init__(self, database_directory: str):
        """Initialize SqliteDatabase instance.

        Args:
            database_directory: Directory to a valid sqlite database file.

        Raises:
            FIleNotFoundError: If the directory provided cannot be found.
        """
        if not os.path.exists(database_directory):
            raise FileNotFoundError(f"{database_directory} does not exist.")

        self.database_directory = database_directory

    def execute_query(self, query: str, *parameters: Any) -> list[tuple]:
        """Execute a sqlite query against the database.

        Args:
            query: SQL query to execute.
            *parameters: Optional parameters to be passed to the query.

        Returns:
            A list of tuples, where each tuple represents a row of results.
        """
        # Connect to database
        with sqlite3.connect(self.database_directory) as conn:
            # Execute query & get results
            cursor = conn.cursor()
            cursor.execute(query, parameters)
            results = cursor.fetchall()
            conn.commit()

        return results
