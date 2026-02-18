"""Tests for the scenario editor API."""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

VALID_YAML = """\
simulation:
  ticks_per_day: 12
  num_days: 1
  rng_seed: 42

agents:
  - id: BANK_A
    opening_balance: 0
    liquidity_pool: 1000000
    arrival_config:
      rate_per_tick: 2.0
      amount_distribution:
        type: LogNormal
        mean: 10000
        std_dev: 5000
      counterparty_weights:
        BANK_B: 1.0
      deadline_range: [3, 8]
  - id: BANK_B
    opening_balance: 0
    liquidity_pool: 1000000
    arrival_config:
      rate_per_tick: 2.0
      amount_distribution:
        type: LogNormal
        mean: 10000
        std_dev: 5000
      counterparty_weights:
        BANK_A: 1.0
      deadline_range: [3, 8]

cost_rates:
  delay_cost_per_tick_per_cent: 0.2
  eod_penalty_per_transaction: 100000
  deadline_penalty: 50000
  liquidity_cost_per_tick_bps: 83
"""

CRISIS_YAML = """\
simulation:
  ticks_per_day: 12
  num_days: 3
  rng_seed: 99

agents:
  - id: BANK_A
    opening_balance: 0
    liquidity_pool: 2000000
    arrival_config:
      rate_per_tick: 3.0
      amount_distribution:
        type: LogNormal
        mean: 15000
        std_dev: 8000
      counterparty_weights:
        BANK_B: 0.6
        BANK_C: 0.4
      deadline_range: [2, 6]
  - id: BANK_B
    opening_balance: 0
    liquidity_pool: 1500000
    arrival_config:
      rate_per_tick: 2.5
      amount_distribution:
        type: LogNormal
        mean: 12000
        std_dev: 6000
      counterparty_weights:
        BANK_A: 0.7
        BANK_C: 0.3
      deadline_range: [2, 6]
  - id: BANK_C
    opening_balance: 0
    liquidity_pool: 1000000
    arrival_config:
      rate_per_tick: 2.0
      amount_distribution:
        type: LogNormal
        mean: 10000
        std_dev: 5000
      counterparty_weights:
        BANK_A: 0.5
        BANK_B: 0.5
      deadline_range: [3, 8]

scenario_events:
  - type: DirectTransfer
    from_agent: BANK_A
    to_agent: BANK_C
    amount: 500000
    schedule:
      type: OneTime
      tick: 12
  - type: DirectTransfer
    from_agent: BANK_B
    to_agent: BANK_A
    amount: 300000
    schedule:
      type: OneTime
      tick: 24

cost_rates:
  delay_cost_per_tick_per_cent: 0.3
  eod_penalty_per_transaction: 150000
  deadline_penalty: 75000
  liquidity_cost_per_tick_bps: 100
"""


def test_validate_valid_yaml():
    res = client.post("/api/scenarios/validate", json={"yaml_string": VALID_YAML})
    assert res.status_code == 200
    data = res.json()
    assert data["valid"] is True
    assert data["summary"]["num_agents"] == 2
    assert data["summary"]["ticks_per_day"] == 12
    assert data["summary"]["num_days"] == 1


def test_validate_invalid_yaml_syntax():
    res = client.post("/api/scenarios/validate", json={"yaml_string": "{{not yaml"})
    assert res.status_code == 200
    data = res.json()
    assert data["valid"] is False
    assert any("YAML" in e or "parse" in e.lower() for e in data["errors"])


def test_validate_missing_required_fields():
    res = client.post("/api/scenarios/validate", json={"yaml_string": "simulation:\n  ticks_per_day: 5"})
    assert res.status_code == 200
    data = res.json()
    assert data["valid"] is False
    assert len(data["errors"]) > 0


def test_validate_not_a_dict():
    res = client.post("/api/scenarios/validate", json={"yaml_string": "- item1\n- item2"})
    assert res.status_code == 200
    data = res.json()
    assert data["valid"] is False
    assert "mapping" in data["errors"][0].lower() or "dict" in data["errors"][0].lower()


def test_summary_extracts_features():
    res = client.post("/api/scenarios/validate", json={"yaml_string": CRISIS_YAML})
    assert res.status_code == 200
    data = res.json()
    assert data["valid"] is True
    s = data["summary"]
    assert s["num_agents"] == 3
    assert s["ticks_per_day"] == 12
    assert s["num_days"] == 3
    assert any("DirectTransfer" in f for f in s["features"])
    assert s["cost_config"]["liquidity_cost_per_tick_bps"] == 100


def test_save_and_list_custom_scenario():
    res = client.post("/api/scenarios/custom", json={
        "name": "Test Scenario",
        "description": "A test",
        "yaml_string": VALID_YAML,
    })
    assert res.status_code == 200
    data = res.json()
    assert "id" in data
    assert data["name"] == "Test Scenario"
    assert data["summary"]["num_agents"] == 2

    # List
    res2 = client.get("/api/scenarios/custom")
    assert res2.status_code == 200
    ids = [s["id"] for s in res2.json()["scenarios"]]
    assert data["id"] in ids

    # Get by ID
    res3 = client.get(f"/api/scenarios/custom/{data['id']}")
    assert res3.status_code == 200
    assert res3.json()["name"] == "Test Scenario"


def test_save_invalid_yaml_rejected():
    res = client.post("/api/scenarios/custom", json={
        "name": "Bad",
        "description": "broken",
        "yaml_string": "not: valid: config",
    })
    assert res.status_code == 400


def test_template_yaml_validates():
    """Both the blank and crisis templates should pass validation."""
    for yaml_str in [VALID_YAML, CRISIS_YAML]:
        res = client.post("/api/scenarios/validate", json={"yaml_string": yaml_str})
        assert res.status_code == 200
        assert res.json()["valid"] is True


# ── Event Timeline Builder YAML format tests ─────────────────────────

# This matches what EventTimelineBuilder.eventsToYaml() now produces:
# flat fields + schedule (not trigger/params)
SCENARIO_WITH_BUILDER_EVENTS = """\
simulation:
  ticks_per_day: 12
  num_days: 2
  rng_seed: 42

agents:
  - id: BANK_A
    opening_balance: 0
    liquidity_pool: 1000000
    arrival_config:
      rate_per_tick: 2.0
      amount_distribution:
        type: LogNormal
        mean: 10000
        std_dev: 5000
      counterparty_weights:
        BANK_B: 1.0
      deadline_range: [3, 8]
  - id: BANK_B
    opening_balance: 0
    liquidity_pool: 1000000
    arrival_config:
      rate_per_tick: 2.0
      amount_distribution:
        type: LogNormal
        mean: 10000
        std_dev: 5000
      counterparty_weights:
        BANK_A: 1.0
      deadline_range: [3, 8]

cost_rates:
  delay_cost_per_tick_per_cent: 0.2
  eod_penalty_per_transaction: 100000
  deadline_penalty: 50000
  liquidity_cost_per_tick_bps: 83

scenario_events:
  - type: DirectTransfer
    from_agent: BANK_A
    to_agent: BANK_B
    amount: 500000
    schedule:
      type: OneTime
      tick: 5
  - type: GlobalArrivalRateChange
    multiplier: 2.0
    schedule:
      type: Repeating
      start_tick: 6
      interval: 12
  - type: CollateralAdjustment
    agent: BANK_A
    delta: 200000
    schedule:
      type: OneTime
      tick: 10
"""


def test_builder_format_events_validate():
    """Scenarios with events in the builder's new format pass SimulationConfig validation."""
    res = client.post("/api/scenarios/validate", json={"yaml_string": SCENARIO_WITH_BUILDER_EVENTS})
    assert res.status_code == 200
    data = res.json()
    assert data["valid"] is True, f"Validation errors: {data.get('errors')}"
    assert data["summary"]["num_agents"] == 2
    features = data["summary"]["features"]
    assert any("DirectTransfer" in f for f in features)
    assert any("GlobalArrivalRateChange" in f for f in features)
    assert any("CollateralAdjustment" in f for f in features)


def test_builder_format_events_save():
    """Scenarios with builder-format events can be saved as custom scenarios."""
    res = client.post("/api/scenarios/custom", json={
        "name": "Builder Events Test",
        "description": "Tests engine-compatible event format",
        "yaml_string": SCENARIO_WITH_BUILDER_EVENTS,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Builder Events Test"
    assert data["summary"]["num_agents"] == 2
