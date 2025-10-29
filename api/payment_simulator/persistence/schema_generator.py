"""
DDL Generation from Pydantic Models

Automatically generates CREATE TABLE and CREATE INDEX statements from Pydantic models.
This ensures the database schema stays in sync with the model definitions.
"""

import inspect
from datetime import datetime
from enum import Enum
from typing import Any, Optional, Type, get_args, get_origin

from pydantic import BaseModel


# ============================================================================
# Type Mapping
# ============================================================================

PYTHON_TO_SQL_TYPE_MAP = {
    str: "VARCHAR",
    int: "BIGINT",
    float: "DOUBLE",
    bool: "BOOLEAN",
    datetime: "TIMESTAMP",
}


def python_type_to_sql_type(py_type: Any) -> str:
    """Convert Python type annotation to SQL type.

    Args:
        py_type: Python type annotation (can be Optional, Enum, etc.)

    Returns:
        SQL type string (VARCHAR, BIGINT, etc.)

    Examples:
        >>> python_type_to_sql_type(str)
        'VARCHAR'
        >>> python_type_to_sql_type(int)
        'BIGINT'
        >>> python_type_to_sql_type(Optional[str])
        'VARCHAR'
    """
    # Handle Optional types (Union[X, None])
    origin = get_origin(py_type)
    if origin is type(None):
        # This is just None type
        return "VARCHAR"

    if origin is not None:
        # This is a generic type like Optional[X] or Union[X, Y]
        args = get_args(py_type)
        if args:
            # For Optional[X], get the first non-None type
            for arg in args:
                if arg is not type(None):
                    py_type = arg
                    break

    # Handle enums
    if inspect.isclass(py_type) and issubclass(py_type, Enum):
        return "VARCHAR"

    # Direct mapping
    return PYTHON_TO_SQL_TYPE_MAP.get(py_type, "VARCHAR")


# ============================================================================
# DDL Generation
# ============================================================================


def generate_create_table_ddl(model: Type[BaseModel]) -> str:
    """Generate CREATE TABLE DDL from Pydantic model.

    Args:
        model: Pydantic model class with model_config["table_name"]

    Returns:
        SQL CREATE TABLE statement

    Raises:
        ValueError: If model is missing required configuration

    Examples:
        >>> from payment_simulator.persistence.models import TransactionRecord
        >>> ddl = generate_create_table_ddl(TransactionRecord)
        >>> "CREATE TABLE IF NOT EXISTS transactions" in ddl
        True
    """
    # Validate model has required config
    if not hasattr(model, "model_config"):
        raise ValueError(f"Model {model.__name__} missing model_config attribute")

    config = model.model_config
    if "table_name" not in config:
        raise ValueError(f"Model {model.__name__} missing model_config['table_name']")

    table_name = config["table_name"]
    primary_key = config.get("primary_key", [])

    # Get field definitions
    fields = model.model_fields
    columns = []

    for field_name, field_info in fields.items():
        py_type = field_info.annotation
        sql_type = python_type_to_sql_type(py_type)

        # Check if field is optional (nullable)
        is_optional = _is_field_optional(py_type, field_info)

        null_constraint = "" if is_optional else " NOT NULL"

        # Special handling for auto-increment id fields
        auto_increment = ""
        if field_name == "id" and _is_int_type(py_type):
            # For DuckDB, use INTEGER for auto-increment
            sql_type = "INTEGER"
            # Note: DuckDB doesn't use AUTOINCREMENT keyword like SQLite
            # Instead, we rely on PRIMARY KEY behavior

        columns.append(f"    {field_name} {sql_type}{null_constraint}{auto_increment}")

    # Add primary key constraint
    if primary_key:
        pk_cols = ", ".join(primary_key)
        columns.append(f"    PRIMARY KEY ({pk_cols})")

    ddl = f"CREATE TABLE IF NOT EXISTS {table_name} (\n"
    ddl += ",\n".join(columns)
    ddl += "\n);"

    return ddl


def generate_create_indexes_ddl(model: Type[BaseModel]) -> list[str]:
    """Generate CREATE INDEX statements from Pydantic model.

    Args:
        model: Pydantic model class with model_config["indexes"]

    Returns:
        List of SQL CREATE INDEX statements

    Examples:
        >>> from payment_simulator.persistence.models import TransactionRecord
        >>> indexes = generate_create_indexes_ddl(TransactionRecord)
        >>> len(indexes) > 0
        True
    """
    if not hasattr(model, "model_config"):
        return []

    config = model.model_config
    if "indexes" not in config or not config["indexes"]:
        return []

    table_name = config.get("table_name", "unknown")
    indexes = config["indexes"]

    ddl_statements = []
    for index_name, columns in indexes:
        cols = ", ".join(columns)
        ddl = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({cols});"
        ddl_statements.append(ddl)

    return ddl_statements


def generate_full_schema_ddl() -> str:
    """Generate complete schema DDL for all models.

    Returns:
        SQL DDL for all tables, indexes, and migrations table

    Examples:
        >>> ddl = generate_full_schema_ddl()
        >>> "transactions" in ddl
        True
        >>> "schema_migrations" in ddl
        True
    """
    from .models import (
        CollateralEventRecord,
        DailyAgentMetricsRecord,
        SimulationRunRecord,
        TransactionRecord,
    )

    models = [
        SimulationRunRecord,
        TransactionRecord,
        DailyAgentMetricsRecord,
        CollateralEventRecord,
    ]

    ddl_parts = []

    # Generate CREATE TABLE statements
    for model in models:
        ddl_parts.append(generate_create_table_ddl(model))
        # Add indexes immediately after table
        indexes = generate_create_indexes_ddl(model)
        if indexes:
            ddl_parts.extend(indexes)

    # Add schema_migrations table
    ddl_parts.append(
        """CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP NOT NULL,
    description VARCHAR NOT NULL
);"""
    )

    return "\n\n".join(ddl_parts)


# ============================================================================
# Helper Functions
# ============================================================================


def _is_field_optional(py_type: Any, field_info: Any) -> bool:
    """Check if a field is optional (nullable).

    Args:
        py_type: Field type annotation
        field_info: Pydantic FieldInfo object

    Returns:
        True if field can be None
    """
    # Check if type annotation includes None
    origin = get_origin(py_type)
    if origin is not None:
        args = get_args(py_type)
        if type(None) in args:
            return True

    # Check if field has a default value of None
    if hasattr(field_info, "default") and field_info.default is None:
        return True

    # Check if field has default_factory that returns None
    if hasattr(field_info, "default_factory") and field_info.default_factory is not None:
        return True

    return False


def _is_int_type(py_type: Any) -> bool:
    """Check if type is int or Optional[int].

    Args:
        py_type: Python type annotation

    Returns:
        True if type is int-based
    """
    # Direct int
    if py_type is int:
        return True

    # Optional[int]
    origin = get_origin(py_type)
    if origin is not None:
        args = get_args(py_type)
        return int in args

    return False


# ============================================================================
# Schema Validation
# ============================================================================


def validate_table_schema(conn: Any, model: Type[BaseModel]) -> tuple[bool, list[str]]:
    """Validate that database table schema matches Pydantic model.

    Args:
        conn: DuckDB connection
        model: Pydantic model to validate against

    Returns:
        Tuple of (is_valid, list of error messages)
        - is_valid: True if schema matches, False otherwise
        - errors: List of descriptive error messages (empty if valid)

    Examples:
        >>> import duckdb
        >>> from payment_simulator.persistence.models import TransactionRecord
        >>> conn = duckdb.connect(':memory:')
        >>> # ... create table ...
        >>> is_valid, errors = validate_table_schema(conn, TransactionRecord)
        >>> if not is_valid:
        ...     print(f"Schema errors: {errors}")
    """
    if not hasattr(model, "model_config"):
        return False, [f"Model {model.__name__} missing model_config attribute"]

    config = model.model_config
    if "table_name" not in config:
        return False, [f"Model {model.__name__} missing model_config['table_name']"]

    table_name = config["table_name"]
    errors = []

    # Try to get table schema from database
    try:
        # DuckDB DESCRIBE returns: column_name, column_type, null, key, default, extra
        result = conn.execute(f"DESCRIBE {table_name}").fetchall()
        db_columns = {row[0]: row[1] for row in result}  # column_name: column_type
    except Exception as e:
        # Table doesn't exist or other error
        return False, [f"Table {table_name} does not exist: {e}"]

    # Get model fields
    model_fields = set(model.model_fields.keys())
    db_fields = set(db_columns.keys())

    # Check for missing columns (in model but not in database)
    missing_columns = model_fields - db_fields
    if missing_columns:
        for col in sorted(missing_columns):
            errors.append(f"Column '{col}' missing from table {table_name}")

    # Check for extra columns (in database but not in model)
    extra_columns = db_fields - model_fields
    if extra_columns:
        errors.append(f"Unexpected columns in {table_name}: {sorted(extra_columns)}")

    # Return validation results
    is_valid = len(errors) == 0
    return is_valid, errors
