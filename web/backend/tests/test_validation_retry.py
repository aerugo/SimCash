"""Tests for the validation retry loop in streaming_optimizer.stream_optimization().

Covers: valid on first try, invalid then valid, parse error then valid,
all retries exhausted, and error feedback in prompt.
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch, ANY

import pytest

# We test stream_optimize() which is an async generator.
# We mock: pydantic_ai.Agent, ConstraintValidator, _parse_policy_response,
# and the prompt-building helpers.

VALID_POLICY = {
    "version": "2.0",
    "policy_id": "test_policy",
    "parameters": {"initial_liquidity_fraction": 0.5},
    "payment_tree": {"type": "action", "node_id": "root", "action": "Release"},
    "bank_tree": {"type": "action", "node_id": "bank", "action": "NoAction"},
}

AGENT_ID = "BANK_A"
CURRENT_POLICY = {
    "version": "2.0",
    "policy_id": "current",
    "parameters": {"initial_liquidity_fraction": 0.8},
    "payment_tree": {"type": "action", "node_id": "root", "action": "Release"},
    "bank_tree": {"type": "action", "node_id": "bank", "action": "NoAction"},
}


def _make_mock_day():
    day = MagicMock()
    day.per_agent_costs = {"BANK_A": 1000, "BANK_B": 500}
    day.costs = {"BANK_A": {"delay_cost": 100, "liquidity_cost": 200, "penalty_cost": 50, "total": 1000}}
    day.events = []
    day.seed = 42
    day.policies = {"BANK_A": CURRENT_POLICY}
    return day


def _mock_stream_result(full_text: str):
    """Create a mock for agent.run_stream() context manager."""
    from unittest.mock import MagicMock

    # Mock TextPart
    text_part = MagicMock()
    text_part.content = full_text
    type(text_part).__name__ = "TextPart"

    response = MagicMock()
    response.parts = [text_part]

    async def _stream_responses(debounce_by=None):
        yield response, True

    stream = MagicMock()
    stream.stream_responses = _stream_responses
    stream.usage.return_value = MagicMock(input_tokens=10, output_tokens=20, details={})

    return stream


def _mock_run_result(full_text: str):
    """Create a mock for agent.run() (non-streaming, used in validation retries)."""
    result = MagicMock()
    result.output = full_text
    result.data = full_text
    result.usage = MagicMock(request_tokens=10, response_tokens=20)
    return result


class _AsyncContextManager:
    def __init__(self, val):
        self.val = val
    async def __aenter__(self):
        return self.val
    async def __aexit__(self, *args):
        pass


async def _collect_events(async_gen):
    """Collect all events from an async generator."""
    events = []
    async for event in async_gen:
        events.append(event)
    return events


def _valid_validation_result():
    r = MagicMock()
    r.is_valid = True
    r.errors = []
    return r


def _invalid_validation_result(errors=None):
    r = MagicMock()
    r.is_valid = False
    r.errors = errors or ["fraction out of range"]
    return r


# Common patches for all tests
_PATCHES = {
    "build_prompt": "app.streaming_optimizer._build_optimization_prompt",
    "create_agent": "app.streaming_optimizer._create_agent",
    "parse_policy": "app.streaming_optimizer._parse_policy_response",
    "load_dotenv": "dotenv.load_dotenv",
    "settings_mod": "app.settings.settings_manager",
    "constraint_presets": "app.constraint_presets.build_constraints",
}

# Inject ConstraintValidator into the constraints module so the lazy import works
import payment_simulator.ai_cash_mgmt.constraints as _constraints_mod
if not hasattr(_constraints_mod, "ConstraintValidator"):
    _constraints_mod.ConstraintValidator = MagicMock()


@pytest.fixture
def mock_env():
    """Set up common mocks for stream_optimize tests."""
    with patch(_PATCHES["build_prompt"]) as mock_build, \
         patch(_PATCHES["settings_mod"]) as mock_settings, \
         patch(_PATCHES["create_agent"]) as mock_create, \
         patch(_PATCHES["parse_policy"]) as mock_parse, \
         patch(_PATCHES["constraint_presets"]) as mock_bc, \
         patch("payment_simulator.ai_cash_mgmt.optimization.constraint_validator.ConstraintValidator") as mock_cv_cls, \
         patch(_PATCHES["load_dotenv"]):

        # Build prompt returns (system, user, context)
        mock_build.return_value = (
            "system prompt",
            "user prompt",
            {"current_fraction": 0.8, "agent_cost": 1000, "cost_breakdown": {"delay_cost": 100, "deadline_penalty": 50}},
        )

        # LLM config
        llm_cfg = MagicMock()
        llm_cfg.model = "openai:test"
        llm_cfg.provider = "openai"
        llm_cfg.thinking_config = None
        llm_cfg.to_model_settings.return_value = {}
        mock_settings.get_llm_config.return_value = llm_cfg

        yield {
            "build_prompt": mock_build,
            "settings": mock_settings,
            "create_agent": mock_create,
            "parse_policy": mock_parse,
            "build_constraints": mock_bc,
            "cv_cls": mock_cv_cls,
            "llm_cfg": llm_cfg,
        }


@pytest.mark.asyncio
async def test_valid_policy_first_try(mock_env):
    """No retries needed — result has accepted=True."""
    from app.streaming_optimizer import stream_optimize

    agent = MagicMock()
    stream = _mock_stream_result(json.dumps(VALID_POLICY))
    agent.run_stream.return_value = _AsyncContextManager(stream)
    mock_env["create_agent"].return_value = agent

    mock_env["parse_policy"].return_value = VALID_POLICY

    validator = MagicMock()
    validator.validate.return_value = _valid_validation_result()
    mock_env["cv_cls"].return_value = validator

    events = await _collect_events(
        stream_optimize(AGENT_ID, CURRENT_POLICY, _make_mock_day(), [_make_mock_day()], {})
    )

    results = [e for e in events if e["type"] == "result"]
    assert len(results) == 1
    assert results[0]["data"]["accepted"] is True
    assert results[0]["data"]["new_policy"] == VALID_POLICY
    # No validation_attempts key or it's 1
    assert results[0]["data"].get("validation_attempts", 1) == 1


@pytest.mark.asyncio
async def test_invalid_then_valid(mock_env):
    """First LLM response fails validation, second succeeds → validation_attempts=2."""
    from app.streaming_optimizer import stream_optimize

    agent = MagicMock()
    stream = _mock_stream_result(json.dumps(VALID_POLICY))
    agent.run_stream.return_value = _AsyncContextManager(stream)

    # Second call (validation retry) returns valid policy
    rerun_result = _mock_run_result(json.dumps(VALID_POLICY))
    agent.run = AsyncMock(return_value=rerun_result)
    mock_env["create_agent"].return_value = agent

    # parse always succeeds
    mock_env["parse_policy"].return_value = VALID_POLICY

    # First validation fails, second succeeds
    validator = MagicMock()
    validator.validate.side_effect = [
        _invalid_validation_result(["fraction too low"]),
        _valid_validation_result(),
    ]
    mock_env["cv_cls"].return_value = validator

    events = await _collect_events(
        stream_optimize(AGENT_ID, CURRENT_POLICY, _make_mock_day(), [_make_mock_day()], {})
    )

    results = [e for e in events if e["type"] == "result"]
    assert len(results) == 1
    assert results[0]["data"]["accepted"] is True
    assert results[0]["data"]["validation_attempts"] == 2


@pytest.mark.asyncio
async def test_parse_error_then_valid(mock_env):
    """First response unparseable, retry with feedback succeeds."""
    from app.streaming_optimizer import stream_optimize

    agent = MagicMock()
    stream = _mock_stream_result("not json at all")
    agent.run_stream.return_value = _AsyncContextManager(stream)

    rerun_result = _mock_run_result(json.dumps(VALID_POLICY))
    agent.run = AsyncMock(return_value=rerun_result)
    mock_env["create_agent"].return_value = agent

    # First parse fails, second succeeds
    mock_env["parse_policy"].side_effect = [
        ValueError("No JSON found"),
        VALID_POLICY,
    ]

    validator = MagicMock()
    validator.validate.return_value = _valid_validation_result()
    mock_env["cv_cls"].return_value = validator

    events = await _collect_events(
        stream_optimize(AGENT_ID, CURRENT_POLICY, _make_mock_day(), [_make_mock_day()], {})
    )

    results = [e for e in events if e["type"] == "result"]
    assert len(results) == 1
    assert results[0]["data"]["accepted"] is True
    assert results[0]["data"]["validation_attempts"] == 2


@pytest.mark.asyncio
async def test_all_retries_exhausted(mock_env):
    """5 consecutive validation failures → accepted=False, new_policy=None."""
    from app.streaming_optimizer import stream_optimize

    agent = MagicMock()
    stream = _mock_stream_result(json.dumps(VALID_POLICY))
    agent.run_stream.return_value = _AsyncContextManager(stream)

    rerun_result = _mock_run_result(json.dumps(VALID_POLICY))
    agent.run = AsyncMock(return_value=rerun_result)
    mock_env["create_agent"].return_value = agent

    mock_env["parse_policy"].return_value = VALID_POLICY

    # All validations fail
    validator = MagicMock()
    validator.validate.return_value = _invalid_validation_result(["always invalid"])
    mock_env["cv_cls"].return_value = validator

    events = await _collect_events(
        stream_optimize(AGENT_ID, CURRENT_POLICY, _make_mock_day(), [_make_mock_day()], {})
    )

    results = [e for e in events if e["type"] == "result"]
    assert len(results) == 1
    assert results[0]["data"]["accepted"] is False
    assert results[0]["data"]["new_policy"] is None
    assert results[0]["data"]["validation_attempts"] == 5


@pytest.mark.asyncio
async def test_error_feedback_in_prompt(mock_env):
    """Retry appends validation errors to the user prompt."""
    from app.streaming_optimizer import stream_optimize

    agent = MagicMock()
    stream = _mock_stream_result(json.dumps(VALID_POLICY))
    agent.run_stream.return_value = _AsyncContextManager(stream)

    # Capture the prompt sent to agent.run on retry
    captured_prompts = []
    async def _capture_run(prompt, **kwargs):
        captured_prompts.append(prompt)
        return _mock_run_result(json.dumps(VALID_POLICY))

    agent.run = _capture_run
    mock_env["create_agent"].return_value = agent

    mock_env["parse_policy"].return_value = VALID_POLICY

    # First validation fails, second succeeds
    validator = MagicMock()
    validator.validate.side_effect = [
        _invalid_validation_result(["fraction must be between 0.01 and 1.0"]),
        _valid_validation_result(),
    ]
    mock_env["cv_cls"].return_value = validator

    events = await _collect_events(
        stream_optimize(AGENT_ID, CURRENT_POLICY, _make_mock_day(), [_make_mock_day()], {})
    )

    assert len(captured_prompts) == 1
    assert "VALIDATION ERROR" in captured_prompts[0]
    assert "fraction must be between 0.01 and 1.0" in captured_prompts[0]
