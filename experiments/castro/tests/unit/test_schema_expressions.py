"""Unit tests for policy schema expression types.

TDD: These tests are written BEFORE implementation.
Run with: pytest experiments/castro/tests/unit/test_schema_expressions.py -v
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError


class TestComparisonOperator:
    """Tests for comparison operators enum."""

    def test_valid_comparison_operators(self) -> None:
        """All standard comparison operators are valid."""
        from experiments.castro.schemas.expressions import ComparisonOperator

        valid_ops = ["==", "!=", "<", "<=", ">", ">="]
        for op in valid_ops:
            # Should not raise
            assert op in ComparisonOperator.__args__


class TestComparison:
    """Tests for Comparison expression - compares two values."""

    def test_simple_field_vs_literal(self) -> None:
        """Compare context field to literal value."""
        from experiments.castro.schemas.expressions import Comparison
        from experiments.castro.schemas.values import ContextField, LiteralValue

        comp = Comparison(
            op=">=",
            left=ContextField(field="effective_liquidity"),
            right=LiteralValue(value=10000),
        )
        assert comp.op == ">="
        assert comp.left.field == "effective_liquidity"
        assert comp.right.value == 10000

    def test_field_vs_field(self) -> None:
        """Compare two context fields."""
        from experiments.castro.schemas.expressions import Comparison
        from experiments.castro.schemas.values import ContextField

        comp = Comparison(
            op="<",
            left=ContextField(field="balance"),
            right=ContextField(field="remaining_amount"),
        )
        assert comp.op == "<"
        assert comp.left.field == "balance"
        assert comp.right.field == "remaining_amount"

    def test_field_vs_param(self) -> None:
        """Compare context field to parameter reference."""
        from experiments.castro.schemas.expressions import Comparison
        from experiments.castro.schemas.values import ContextField, ParameterRef

        comp = Comparison(
            op="<=",
            left=ContextField(field="ticks_to_deadline"),
            right=ParameterRef(param="urgency_threshold"),
        )
        assert comp.op == "<="
        assert comp.right.param == "urgency_threshold"

    def test_equality_comparison(self) -> None:
        """Test equality comparison operator."""
        from experiments.castro.schemas.expressions import Comparison
        from experiments.castro.schemas.values import ContextField, LiteralValue

        comp = Comparison(
            op="==",
            left=ContextField(field="system_tick_in_day"),
            right=LiteralValue(value=0),
        )
        assert comp.op == "=="

    def test_not_equal_comparison(self) -> None:
        """Test not-equal comparison operator."""
        from experiments.castro.schemas.expressions import Comparison
        from experiments.castro.schemas.values import ContextField, LiteralValue

        comp = Comparison(
            op="!=",
            left=ContextField(field="priority"),
            right=LiteralValue(value=5),
        )
        assert comp.op == "!="

    def test_comparison_json_serialization(self) -> None:
        """Comparison serializes to expected JSON structure."""
        from experiments.castro.schemas.expressions import Comparison
        from experiments.castro.schemas.values import ContextField, LiteralValue

        comp = Comparison(
            op=">=",
            left=ContextField(field="balance"),
            right=LiteralValue(value=0),
        )
        json_dict = comp.model_dump()
        assert json_dict == {
            "op": ">=",
            "left": {"field": "balance"},
            "right": {"value": 0},
        }

    def test_comparison_from_json(self) -> None:
        """Comparison can be parsed from JSON."""
        from experiments.castro.schemas.expressions import Comparison

        json_data = {
            "op": ">",
            "left": {"field": "effective_liquidity"},
            "right": {"value": 50000},
        }
        comp = Comparison.model_validate(json_data)
        assert comp.op == ">"
        assert comp.left.field == "effective_liquidity"
        assert comp.right.value == 50000

    def test_comparison_with_compute_value(self) -> None:
        """Comparison can use computed values."""
        from experiments.castro.schemas.expressions import Comparison
        from experiments.castro.schemas.values import ContextField, ComputeValue, ParameterRef

        comp = Comparison(
            op=">=",
            left=ContextField(field="effective_liquidity"),
            right=ComputeValue(
                compute={
                    "op": "*",
                    "left": ContextField(field="remaining_amount"),
                    "right": ParameterRef(param="liquidity_buffer_factor"),
                }
            ),
        )
        assert comp.right.compute["op"] == "*"


class TestAndExpression:
    """Tests for AND logical expression."""

    def test_and_with_two_conditions(self) -> None:
        """AND combines two comparison conditions."""
        from experiments.castro.schemas.expressions import AndExpression, Comparison
        from experiments.castro.schemas.values import ContextField, LiteralValue

        and_expr = AndExpression(
            op="and",
            conditions=[
                Comparison(
                    op=">=",
                    left=ContextField(field="balance"),
                    right=LiteralValue(value=0),
                ),
                Comparison(
                    op="<=",
                    left=ContextField(field="ticks_to_deadline"),
                    right=LiteralValue(value=5),
                ),
            ],
        )
        assert and_expr.op == "and"
        assert len(and_expr.conditions) == 2

    def test_and_with_multiple_conditions(self) -> None:
        """AND can combine multiple conditions."""
        from experiments.castro.schemas.expressions import AndExpression, Comparison
        from experiments.castro.schemas.values import ContextField, LiteralValue

        and_expr = AndExpression(
            op="and",
            conditions=[
                Comparison(op=">", left=ContextField(field="balance"), right=LiteralValue(value=0)),
                Comparison(op="<", left=ContextField(field="amount"), right=LiteralValue(value=100000)),
                Comparison(op="==", left=ContextField(field="is_overdue"), right=LiteralValue(value=0)),
            ],
        )
        assert len(and_expr.conditions) == 3

    def test_and_json_serialization(self) -> None:
        """AND expression serializes correctly."""
        from experiments.castro.schemas.expressions import AndExpression, Comparison
        from experiments.castro.schemas.values import ContextField, LiteralValue

        and_expr = AndExpression(
            op="and",
            conditions=[
                Comparison(op=">", left=ContextField(field="balance"), right=LiteralValue(value=0)),
            ],
        )
        json_dict = and_expr.model_dump()
        assert json_dict["op"] == "and"
        assert "conditions" in json_dict


class TestOrExpression:
    """Tests for OR logical expression."""

    def test_or_with_two_conditions(self) -> None:
        """OR combines two comparison conditions."""
        from experiments.castro.schemas.expressions import OrExpression, Comparison
        from experiments.castro.schemas.values import ContextField, LiteralValue

        or_expr = OrExpression(
            op="or",
            conditions=[
                Comparison(
                    op="<=",
                    left=ContextField(field="ticks_to_deadline"),
                    right=LiteralValue(value=3),
                ),
                Comparison(
                    op=">=",
                    left=ContextField(field="priority"),
                    right=LiteralValue(value=9),
                ),
            ],
        )
        assert or_expr.op == "or"
        assert len(or_expr.conditions) == 2

    def test_or_json_serialization(self) -> None:
        """OR expression serializes correctly."""
        from experiments.castro.schemas.expressions import OrExpression, Comparison
        from experiments.castro.schemas.values import ContextField, LiteralValue

        or_expr = OrExpression(
            op="or",
            conditions=[
                Comparison(op="==", left=ContextField(field="is_urgent"), right=LiteralValue(value=1)),
            ],
        )
        json_dict = or_expr.model_dump()
        assert json_dict["op"] == "or"


class TestNotExpression:
    """Tests for NOT logical expression."""

    def test_not_simple_condition(self) -> None:
        """NOT inverts a comparison."""
        from experiments.castro.schemas.expressions import NotExpression, Comparison
        from experiments.castro.schemas.values import ContextField, LiteralValue

        not_expr = NotExpression(
            op="not",
            condition=Comparison(
                op="==",
                left=ContextField(field="is_using_credit"),
                right=LiteralValue(value=1),
            ),
        )
        assert not_expr.op == "not"
        assert not_expr.condition.op == "=="

    def test_not_json_serialization(self) -> None:
        """NOT expression serializes correctly."""
        from experiments.castro.schemas.expressions import NotExpression, Comparison
        from experiments.castro.schemas.values import ContextField, LiteralValue

        not_expr = NotExpression(
            op="not",
            condition=Comparison(
                op="==",
                left=ContextField(field="is_overdue"),
                right=LiteralValue(value=1),
            ),
        )
        json_dict = not_expr.model_dump()
        assert json_dict["op"] == "not"
        assert "condition" in json_dict


class TestNestedExpressions:
    """Tests for nested/complex expressions."""

    def test_and_containing_or(self) -> None:
        """AND can contain OR expressions (nested)."""
        from experiments.castro.schemas.expressions import (
            AndExpression,
            OrExpression,
            Comparison,
        )
        from experiments.castro.schemas.values import ContextField, LiteralValue

        # (A OR B) AND C
        nested = AndExpression(
            op="and",
            conditions=[
                OrExpression(
                    op="or",
                    conditions=[
                        Comparison(op=">", left=ContextField(field="balance"), right=LiteralValue(value=0)),
                        Comparison(op=">", left=ContextField(field="credit_headroom"), right=LiteralValue(value=0)),
                    ],
                ),
                Comparison(op="<=", left=ContextField(field="ticks_to_deadline"), right=LiteralValue(value=10)),
            ],
        )
        assert nested.op == "and"
        assert len(nested.conditions) == 2
        assert nested.conditions[0].op == "or"

    def test_or_containing_and(self) -> None:
        """OR can contain AND expressions (nested)."""
        from experiments.castro.schemas.expressions import (
            AndExpression,
            OrExpression,
            Comparison,
        )
        from experiments.castro.schemas.values import ContextField, LiteralValue

        # (A AND B) OR (C AND D)
        nested = OrExpression(
            op="or",
            conditions=[
                AndExpression(
                    op="and",
                    conditions=[
                        Comparison(op=">", left=ContextField(field="balance"), right=LiteralValue(value=0)),
                        Comparison(op="<", left=ContextField(field="amount"), right=LiteralValue(value=100000)),
                    ],
                ),
                AndExpression(
                    op="and",
                    conditions=[
                        Comparison(op="<=", left=ContextField(field="balance"), right=LiteralValue(value=0)),
                        Comparison(op=">=", left=ContextField(field="priority"), right=LiteralValue(value=9)),
                    ],
                ),
            ],
        )
        assert nested.op == "or"
        assert len(nested.conditions) == 2
        assert all(c.op == "and" for c in nested.conditions)

    def test_not_containing_and(self) -> None:
        """NOT can wrap an AND expression."""
        from experiments.castro.schemas.expressions import (
            AndExpression,
            NotExpression,
            Comparison,
        )
        from experiments.castro.schemas.values import ContextField, LiteralValue

        # NOT (A AND B)
        nested = NotExpression(
            op="not",
            condition=AndExpression(
                op="and",
                conditions=[
                    Comparison(op="==", left=ContextField(field="is_overdue"), right=LiteralValue(value=1)),
                    Comparison(op="<", left=ContextField(field="balance"), right=LiteralValue(value=0)),
                ],
            ),
        )
        assert nested.op == "not"
        assert nested.condition.op == "and"


class TestExpressionUnion:
    """Tests for Expression union type."""

    def test_expression_accepts_comparison(self) -> None:
        """Expression union accepts Comparison."""
        from experiments.castro.schemas.expressions import Expression, Comparison
        from experiments.castro.schemas.values import ContextField, LiteralValue

        expr: Expression = Comparison(
            op=">=",
            left=ContextField(field="balance"),
            right=LiteralValue(value=0),
        )
        assert isinstance(expr, Comparison)

    def test_expression_accepts_and(self) -> None:
        """Expression union accepts AndExpression."""
        from experiments.castro.schemas.expressions import Expression, AndExpression, Comparison
        from experiments.castro.schemas.values import ContextField, LiteralValue

        expr: Expression = AndExpression(
            op="and",
            conditions=[
                Comparison(op=">", left=ContextField(field="a"), right=LiteralValue(value=0)),
            ],
        )
        assert isinstance(expr, AndExpression)

    def test_expression_accepts_or(self) -> None:
        """Expression union accepts OrExpression."""
        from experiments.castro.schemas.expressions import Expression, OrExpression, Comparison
        from experiments.castro.schemas.values import ContextField, LiteralValue

        expr: Expression = OrExpression(
            op="or",
            conditions=[
                Comparison(op="<", left=ContextField(field="a"), right=LiteralValue(value=0)),
            ],
        )
        assert isinstance(expr, OrExpression)

    def test_expression_accepts_not(self) -> None:
        """Expression union accepts NotExpression."""
        from experiments.castro.schemas.expressions import Expression, NotExpression, Comparison
        from experiments.castro.schemas.values import ContextField, LiteralValue

        expr: Expression = NotExpression(
            op="not",
            condition=Comparison(op="==", left=ContextField(field="a"), right=LiteralValue(value=0)),
        )
        assert isinstance(expr, NotExpression)
