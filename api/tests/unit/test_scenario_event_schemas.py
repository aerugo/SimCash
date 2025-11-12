"""
Unit tests for scenario event Pydantic schemas.

Tests that scenario events can be validated via Pydantic and correctly converted
to FFI dict format.
"""
import pytest
from pydantic import ValidationError
from payment_simulator.config.schemas import (
    SimulationConfig,
    DirectTransferEvent,
    CollateralAdjustmentEvent,
    GlobalArrivalRateChangeEvent,
    AgentArrivalRateChangeEvent,
    CounterpartyWeightChangeEvent,
    DeadlineWindowChangeEvent,
    OneTimeSchedule,
    RepeatingSchedule,
)


def test_one_time_schedule_validation():
    """Test OneTimeSchedule validates tick correctly."""
    # Valid
    schedule = OneTimeSchedule(tick=10)
    assert schedule.tick == 10
    assert schedule.type == "OneTime"

    # Invalid - negative tick
    with pytest.raises(ValidationError) as exc_info:
        OneTimeSchedule(tick=-1)
    assert "greater than or equal to 0" in str(exc_info.value)


def test_repeating_schedule_validation():
    """Test RepeatingSchedule validates fields correctly."""
    # Valid
    schedule = RepeatingSchedule(start_tick=10, interval=5)
    assert schedule.start_tick == 10
    assert schedule.interval == 5
    assert schedule.type == "Repeating"

    # Invalid - zero interval
    with pytest.raises(ValidationError) as exc_info:
        RepeatingSchedule(start_tick=10, interval=0)
    assert "greater than 0" in str(exc_info.value)


def test_direct_transfer_event_validation():
    """Test DirectTransferEvent validation."""
    # Valid one-time
    event = DirectTransferEvent(
        from_agent="BANK_A",
        to_agent="BANK_B",
        amount=100_000,
        schedule=OneTimeSchedule(tick=10),
    )
    assert event.type == "DirectTransfer"
    assert event.amount == 100_000

    # Valid repeating
    event2 = DirectTransferEvent(
        from_agent="BANK_A",
        to_agent="BANK_B",
        amount=50_000,
        schedule=RepeatingSchedule(start_tick=10, interval=10),
    )
    assert event2.amount == 50_000

    # Invalid - negative amount
    with pytest.raises(ValidationError) as exc_info:
        DirectTransferEvent(
            from_agent="BANK_A",
            to_agent="BANK_B",
            amount=-100,
            schedule=OneTimeSchedule(tick=10),
        )
    assert "greater than 0" in str(exc_info.value)


def test_collateral_adjustment_event_validation():
    """Test CollateralAdjustmentEvent validation."""
    # Valid positive delta
    event = CollateralAdjustmentEvent(
        agent="BANK_A",
        delta=200_000,
        schedule=OneTimeSchedule(tick=10),
    )
    assert event.delta == 200_000

    # Valid negative delta (reducing collateral)
    event2 = CollateralAdjustmentEvent(
        agent="BANK_A",
        delta=-100_000,
        schedule=OneTimeSchedule(tick=10),
    )
    assert event2.delta == -100_000


def test_arrival_rate_change_events_validation():
    """Test arrival rate change event validation."""
    # GlobalArrivalRateChange
    global_event = GlobalArrivalRateChangeEvent(
        multiplier=0.5,
        schedule=OneTimeSchedule(tick=10),
    )
    assert global_event.multiplier == 0.5

    # AgentArrivalRateChange
    agent_event = AgentArrivalRateChangeEvent(
        agent="BANK_A",
        multiplier=3.0,
        schedule=OneTimeSchedule(tick=10),
    )
    assert agent_event.multiplier == 3.0

    # Invalid - zero multiplier
    with pytest.raises(ValidationError) as exc_info:
        GlobalArrivalRateChangeEvent(
            multiplier=0,
            schedule=OneTimeSchedule(tick=10),
        )
    assert "greater than 0" in str(exc_info.value)


def test_counterparty_weight_change_validation():
    """Test CounterpartyWeightChangeEvent validation."""
    # Valid
    event = CounterpartyWeightChangeEvent(
        agent="BANK_A",
        counterparty="BANK_B",
        new_weight=0.7,
        auto_balance_others=False,
        schedule=OneTimeSchedule(tick=10),
    )
    assert event.counterparty == "BANK_B"
    assert event.new_weight == 0.7

    # Invalid - weight out of range
    with pytest.raises(ValidationError) as exc_info:
        CounterpartyWeightChangeEvent(
            agent="BANK_A",
            counterparty="BANK_B",
            new_weight=1.5,  # > 1
            schedule=OneTimeSchedule(tick=10),
        )
    assert "less than or equal to 1" in str(exc_info.value)

    # Invalid - negative weight
    with pytest.raises(ValidationError) as exc_info:
        CounterpartyWeightChangeEvent(
            agent="BANK_A",
            counterparty="BANK_B",
            new_weight=-0.5,
            schedule=OneTimeSchedule(tick=10),
        )
    assert "greater than or equal to 0" in str(exc_info.value)


def test_deadline_window_change_validation():
    """Test DeadlineWindowChangeEvent validation."""
    # Valid - both multipliers
    event = DeadlineWindowChangeEvent(
        min_ticks_multiplier=1.5,
        max_ticks_multiplier=2.0,
        schedule=OneTimeSchedule(tick=10),
    )
    assert event.min_ticks_multiplier == 1.5
    assert event.max_ticks_multiplier == 2.0

    # Valid - only min multiplier
    event = DeadlineWindowChangeEvent(
        min_ticks_multiplier=0.5,
        schedule=OneTimeSchedule(tick=10),
    )
    assert event.min_ticks_multiplier == 0.5
    assert event.max_ticks_multiplier is None

    # Valid - only max multiplier
    event = DeadlineWindowChangeEvent(
        max_ticks_multiplier=1.5,
        schedule=OneTimeSchedule(tick=10),
    )
    assert event.min_ticks_multiplier is None
    assert event.max_ticks_multiplier == 1.5

    # Invalid - no multipliers
    with pytest.raises(ValidationError) as exc_info:
        DeadlineWindowChangeEvent(
            schedule=OneTimeSchedule(tick=10),
        )
    assert "At least one" in str(exc_info.value)

    # Invalid - negative multiplier
    with pytest.raises(ValidationError) as exc_info:
        DeadlineWindowChangeEvent(
            min_ticks_multiplier=-0.5,
            schedule=OneTimeSchedule(tick=10),
        )
    assert "greater than 0" in str(exc_info.value)


def test_simulation_config_with_scenario_events():
    """Test SimulationConfig validates scenario events."""
    config_dict = {
        "simulation": {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 12345,
        },
        "agents": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "credit_limit": 500_000,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 1_000_000,
                "credit_limit": 500_000,
                "policy": {"type": "Fifo"},
            },
        ],
        "scenario_events": [
            {
                "type": "DirectTransfer",
                "from_agent": "BANK_A",
                "to_agent": "BANK_B",
                "amount": 100_000,
                "schedule": {"type": "OneTime", "tick": 10},
            }
        ],
    }

    config = SimulationConfig.from_dict(config_dict)
    assert config.scenario_events is not None
    assert len(config.scenario_events) == 1
    assert isinstance(config.scenario_events[0], DirectTransferEvent)


def test_simulation_config_validates_agent_references():
    """Test that SimulationConfig validates agent references in events."""
    config_dict = {
        "simulation": {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 12345,
        },
        "agents": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "credit_limit": 500_000,
                "policy": {"type": "Fifo"},
            },
        ],
        "scenario_events": [
            {
                "type": "DirectTransfer",
                "from_agent": "BANK_A",
                "to_agent": "UNKNOWN_BANK",  # Invalid reference
                "amount": 100_000,
                "schedule": {"type": "OneTime", "tick": 10},
            }
        ],
    }

    with pytest.raises(ValidationError) as exc_info:
        SimulationConfig.from_dict(config_dict)
    assert "unknown to_agent: UNKNOWN_BANK" in str(exc_info.value)


def test_simulation_config_to_ffi_dict_with_events():
    """Test that SimulationConfig converts scenario events to FFI dict format."""
    config_dict = {
        "simulation": {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 12345,
        },
        "agents": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "credit_limit": 500_000,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 1_000_000,
                "credit_limit": 500_000,
                "policy": {"type": "Fifo"},
            },
        ],
        "scenario_events": [
            {
                "type": "DirectTransfer",
                "from_agent": "BANK_A",
                "to_agent": "BANK_B",
                "amount": 100_000,
                "schedule": {"type": "OneTime", "tick": 10},
            },
            {
                "type": "CollateralAdjustment",
                "agent": "BANK_A",
                "delta": 200_000,
                "schedule": {"type": "Repeating", "start_tick": 20, "interval": 10},
            },
        ],
    }

    config = SimulationConfig.from_dict(config_dict)
    ffi_dict = config.to_ffi_dict()

    # Verify scenario_events is in FFI dict
    assert "scenario_events" in ffi_dict
    assert len(ffi_dict["scenario_events"]) == 2

    # Verify first event (DirectTransfer, OneTime)
    event1 = ffi_dict["scenario_events"][0]
    assert event1["type"] == "DirectTransfer"
    assert event1["from_agent"] == "BANK_A"
    assert event1["to_agent"] == "BANK_B"
    assert event1["amount"] == 100_000
    assert event1["schedule"] == "OneTime"
    assert event1["tick"] == 10

    # Verify second event (CollateralAdjustment, Repeating)
    event2 = ffi_dict["scenario_events"][1]
    assert event2["type"] == "CollateralAdjustment"
    assert event2["agent"] == "BANK_A"
    assert event2["delta"] == 200_000
    assert event2["schedule"] == "Repeating"
    assert event2["start_tick"] == 20
    assert event2["interval"] == 10


def test_simulation_config_without_scenario_events():
    """Test that scenario_events is optional."""
    config_dict = {
        "simulation": {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 12345,
        },
        "agents": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "credit_limit": 500_000,
                "policy": {"type": "Fifo"},
            },
        ],
    }

    config = SimulationConfig.from_dict(config_dict)
    assert config.scenario_events is None

    ffi_dict = config.to_ffi_dict()
    assert "scenario_events" not in ffi_dict


def test_all_event_types_to_ffi():
    """Test that all event types convert correctly to FFI dict."""
    config_dict = {
        "simulation": {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 12345,
        },
        "agents": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "credit_limit": 500_000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 1.0,
                    "amount_distribution": {"type": "Uniform", "min": 10000, "max": 50000},
                    "counterparty_weights": {"BANK_B": 1.0},
                    "deadline_range": [10, 50],
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 1_000_000,
                "credit_limit": 500_000,
                "policy": {"type": "Fifo"},
            },
        ],
        "scenario_events": [
            {
                "type": "DirectTransfer",
                "from_agent": "BANK_A",
                "to_agent": "BANK_B",
                "amount": 100_000,
                "schedule": {"type": "OneTime", "tick": 10},
            },
            {
                "type": "CollateralAdjustment",
                "agent": "BANK_A",
                "delta": 200_000,
                "schedule": {"type": "OneTime", "tick": 15},
            },
            {
                "type": "GlobalArrivalRateChange",
                "multiplier": 0.5,
                "schedule": {"type": "OneTime", "tick": 20},
            },
            {
                "type": "AgentArrivalRateChange",
                "agent": "BANK_A",
                "multiplier": 2.0,
                "schedule": {"type": "OneTime", "tick": 25},
            },
            {
                "type": "CounterpartyWeightChange",
                "agent": "BANK_A",
                "counterparty": "BANK_B",
                "new_weight": 1.0,
                "auto_balance_others": False,
                "schedule": {"type": "OneTime", "tick": 30},
            },
            {
                "type": "DeadlineWindowChange",
                "min_ticks_multiplier": 0.5,
                "max_ticks_multiplier": 0.5,
                "schedule": {"type": "OneTime", "tick": 35},
            },
        ],
    }

    config = SimulationConfig.from_dict(config_dict)
    ffi_dict = config.to_ffi_dict()

    assert "scenario_events" in ffi_dict
    assert len(ffi_dict["scenario_events"]) == 6

    # Verify each event type is present and correctly formatted
    event_types = [e["type"] for e in ffi_dict["scenario_events"]]
    assert "DirectTransfer" in event_types
    assert "CollateralAdjustment" in event_types
    assert "GlobalArrivalRateChange" in event_types
    assert "AgentArrivalRateChange" in event_types
    assert "CounterpartyWeightChange" in event_types
    assert "DeadlineWindowChange" in event_types
