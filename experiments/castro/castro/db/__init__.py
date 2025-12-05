"""Database layer for castro experiments.

Provides DuckDB-based persistence for experiment tracking.

Main components:
- ExperimentRepository: Implementation of Repository protocol
- SCHEMA_SQL: Database schema definition
"""

from experiments.castro.castro.db.repository import ExperimentRepository
from experiments.castro.castro.db.schema import SCHEMA_SQL

__all__ = [
    "ExperimentRepository",
    "SCHEMA_SQL",
]
