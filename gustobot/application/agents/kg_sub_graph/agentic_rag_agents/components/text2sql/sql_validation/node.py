"""Legacy compatibility wrapper for canonical Text2SQL SQL validation."""

from gustobot.application.agents.text2sql.components.sql_validation.node import (
    create_sql_validation_node,
)

__all__ = ["create_sql_validation_node"]
