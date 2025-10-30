"""
Integration tests for Cost & Metrics API endpoints (TDD - tests written first).

These tests verify that the REST API endpoints correctly expose cost data
and system metrics from the Rust backend via FFI.
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client."""
    from payment_simulator.api.main import app
    return TestClient(app)


@pytest.fixture
def simple_config():
    """Simple simulation configuration."""
    return {
        "simulation": {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 12345,
        },
        "agents": [
            {
                "id": "BANK_A",
                "opening_balance": 100_000,
                "credit_limit": 50_000,
                "collateral_pledged": 20_000,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 200_000,
                "credit_limit": 0,
                "collateral_pledged": 0,
                "policy": {"type": "Fifo"},
            },
        ],
        "costs": {
            "overdraft_bps_per_day": 100,
            "collateral_opportunity_bps_per_day": 20,
            "queue1_delay_per_tick": 10,
            "split_fee": 500,
            "deadline_base_penalty": 10_000,
            "deadline_penalty_per_tick": 1_000,
        },
    }


@pytest.fixture
def config_with_activity():
    """Configuration designed to generate costs and activity."""
    return {
        "simulation": {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 54321,
        },
        "agents": [
            {
                "id": "BANK_A",
                "opening_balance": 50_000,  # Small balance
                "credit_limit": 100_000,
                "collateral_pledged": 30_000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 3.0,
                    "amount_distribution": {
                        "type": "Uniform",
                        "min": 20_000,
                        "max": 50_000,
                    },
                    "counterparty_weights": {"BANK_B": 1.0},
                    "deadline_range": [10, 50],
                    "priority": 5,
                    "divisible": True,
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 500_000,
                "credit_limit": 0,
                "collateral_pledged": 0,
                "policy": {"type": "Fifo"},
            },
        ],
        "costs": {
            "overdraft_bps_per_day": 100,
            "collateral_opportunity_bps_per_day": 50,
            "queue1_delay_per_tick": 100,
            "split_fee": 500,
            "deadline_base_penalty": 10_000,
            "deadline_penalty_per_tick": 1_000,
        },
    }


class TestCostsEndpoint:
    """Tests for GET /simulations/{sim_id}/costs endpoint."""

    def test_get_costs_endpoint_exists(self, client, simple_config):
        """Endpoint returns 200 OK for valid simulation."""
        # GIVEN: A simulation
        create_resp = client.post("/simulations", json=simple_config)
        sim_id = create_resp.json()["simulation_id"]

        # WHEN: Query costs endpoint
        response = client.get(f"/simulations/{sim_id}/costs")

        # THEN: Endpoint exists and returns success
        assert response.status_code == 200

    def test_get_costs_returns_required_fields(self, client, simple_config):
        """Response contains required top-level fields."""
        # GIVEN: A simulation
        create_resp = client.post("/simulations", json=simple_config)
        sim_id = create_resp.json()["simulation_id"]

        # WHEN: Query costs
        response = client.get(f"/simulations/{sim_id}/costs")
        data = response.json()

        # THEN: Contains required fields
        assert "simulation_id" in data
        assert "tick" in data
        assert "day" in data
        assert "agents" in data
        assert "total_system_cost" in data

    def test_get_costs_simulation_id_matches(self, client, simple_config):
        """Response simulation_id matches request."""
        # GIVEN: A simulation
        create_resp = client.post("/simulations", json=simple_config)
        sim_id = create_resp.json()["simulation_id"]

        # WHEN: Query costs
        response = client.get(f"/simulations/{sim_id}/costs")
        data = response.json()

        # THEN: simulation_id matches
        assert data["simulation_id"] == sim_id

    def test_get_costs_agents_is_dict(self, client, simple_config):
        """agents field is a dictionary."""
        # GIVEN: A simulation
        create_resp = client.post("/simulations", json=simple_config)
        sim_id = create_resp.json()["simulation_id"]

        # WHEN: Query costs
        response = client.get(f"/simulations/{sim_id}/costs")
        data = response.json()

        # THEN: agents is a dict
        assert isinstance(data["agents"], dict)

    def test_get_costs_all_agents_present(self, client, simple_config):
        """All agents have cost breakdowns."""
        # GIVEN: A simulation with 2 agents
        create_resp = client.post("/simulations", json=simple_config)
        sim_id = create_resp.json()["simulation_id"]

        # WHEN: Query costs
        response = client.get(f"/simulations/{sim_id}/costs")
        data = response.json()

        # THEN: Both agents present
        assert "BANK_A" in data["agents"]
        assert "BANK_B" in data["agents"]

    def test_get_costs_agent_breakdown_has_all_cost_types(self, client, simple_config):
        """Each agent breakdown contains all 5 cost types."""
        # GIVEN: A simulation
        create_resp = client.post("/simulations", json=simple_config)
        sim_id = create_resp.json()["simulation_id"]

        # WHEN: Query costs
        response = client.get(f"/simulations/{sim_id}/costs")
        data = response.json()

        agent_costs = data["agents"]["BANK_A"]

        # THEN: All cost types present
        assert "liquidity_cost" in agent_costs
        assert "collateral_cost" in agent_costs
        assert "delay_cost" in agent_costs
        assert "split_friction_cost" in agent_costs
        assert "deadline_penalty" in agent_costs
        assert "total_cost" in agent_costs

    def test_get_costs_all_values_are_integers(self, client, simple_config):
        """All cost values are integers (cents)."""
        # GIVEN: A simulation
        create_resp = client.post("/simulations", json=simple_config)
        sim_id = create_resp.json()["simulation_id"]

        # WHEN: Query costs
        response = client.get(f"/simulations/{sim_id}/costs")
        data = response.json()

        agent_costs = data["agents"]["BANK_A"]

        # THEN: All values are integers
        assert isinstance(agent_costs["liquidity_cost"], int)
        assert isinstance(agent_costs["collateral_cost"], int)
        assert isinstance(agent_costs["delay_cost"], int)
        assert isinstance(agent_costs["split_friction_cost"], int)
        assert isinstance(agent_costs["deadline_penalty"], int)
        assert isinstance(agent_costs["total_cost"], int)
        assert isinstance(data["total_system_cost"], int)

    def test_get_costs_total_system_cost_equals_sum(self, client, simple_config):
        """total_system_cost equals sum of all agent totals."""
        # GIVEN: A simulation
        create_resp = client.post("/simulations", json=simple_config)
        sim_id = create_resp.json()["simulation_id"]

        # WHEN: Query costs
        response = client.get(f"/simulations/{sim_id}/costs")
        data = response.json()

        # THEN: System total equals sum of agent totals
        agent_sum = sum(
            agent["total_cost"]
            for agent in data["agents"].values()
        )
        assert data["total_system_cost"] == agent_sum

    def test_get_costs_after_running_ticks(self, client, config_with_activity):
        """Costs accumulate after running simulation."""
        # GIVEN: A simulation with activity
        create_resp = client.post("/simulations", json=config_with_activity)
        sim_id = create_resp.json()["simulation_id"]

        # WHEN: Run 20 ticks
        client.post(f"/simulations/{sim_id}/tick", params={"count": 20})

        # THEN: Some costs accumulated
        response = client.get(f"/simulations/{sim_id}/costs")
        data = response.json()

        # At least one agent should have non-zero total cost
        total_costs = [agent["total_cost"] for agent in data["agents"].values()]
        assert any(cost > 0 for cost in total_costs)

    def test_get_costs_404_for_nonexistent_simulation(self, client):
        """Returns 404 for non-existent simulation."""
        # WHEN: Query costs for non-existent simulation
        response = client.get("/simulations/nonexistent-id/costs")

        # THEN: Returns 404
        assert response.status_code == 404

    def test_get_costs_tick_and_day_match_simulation_state(self, client, simple_config):
        """tick and day fields match simulation state."""
        # GIVEN: A simulation
        create_resp = client.post("/simulations", json=simple_config)
        sim_id = create_resp.json()["simulation_id"]

        # WHEN: Run 5 ticks
        client.post(f"/simulations/{sim_id}/tick", params={"count": 5})

        # Get current state
        state_resp = client.get(f"/simulations/{sim_id}/state")
        state = state_resp.json()

        # Get costs
        costs_resp = client.get(f"/simulations/{sim_id}/costs")
        costs = costs_resp.json()

        # THEN: tick and day match
        assert costs["tick"] == state["current_tick"]
        assert costs["day"] == state["current_day"]


class TestMetricsEndpoint:
    """Tests for GET /simulations/{sim_id}/metrics endpoint."""

    def test_get_metrics_endpoint_exists(self, client, simple_config):
        """Endpoint returns 200 OK for valid simulation."""
        # GIVEN: A simulation
        create_resp = client.post("/simulations", json=simple_config)
        sim_id = create_resp.json()["simulation_id"]

        # WHEN: Query metrics endpoint
        response = client.get(f"/simulations/{sim_id}/metrics")

        # THEN: Endpoint exists and returns success
        assert response.status_code == 200

    def test_get_metrics_returns_required_fields(self, client, simple_config):
        """Response contains required top-level fields."""
        # GIVEN: A simulation
        create_resp = client.post("/simulations", json=simple_config)
        sim_id = create_resp.json()["simulation_id"]

        # WHEN: Query metrics
        response = client.get(f"/simulations/{sim_id}/metrics")
        data = response.json()

        # THEN: Contains required fields
        assert "simulation_id" in data
        assert "tick" in data
        assert "day" in data
        assert "metrics" in data

    def test_get_metrics_simulation_id_matches(self, client, simple_config):
        """Response simulation_id matches request."""
        # GIVEN: A simulation
        create_resp = client.post("/simulations", json=simple_config)
        sim_id = create_resp.json()["simulation_id"]

        # WHEN: Query metrics
        response = client.get(f"/simulations/{sim_id}/metrics")
        data = response.json()

        # THEN: simulation_id matches
        assert data["simulation_id"] == sim_id

    def test_get_metrics_contains_all_metric_fields(self, client, simple_config):
        """metrics object contains all expected fields."""
        # GIVEN: A simulation
        create_resp = client.post("/simulations", json=simple_config)
        sim_id = create_resp.json()["simulation_id"]

        # WHEN: Query metrics
        response = client.get(f"/simulations/{sim_id}/metrics")
        data = response.json()

        metrics = data["metrics"]

        # THEN: All metric fields present
        assert "total_arrivals" in metrics
        assert "total_settlements" in metrics
        assert "settlement_rate" in metrics
        assert "avg_delay_ticks" in metrics
        assert "max_delay_ticks" in metrics
        assert "queue1_total_size" in metrics
        assert "queue2_total_size" in metrics
        assert "peak_overdraft" in metrics
        assert "agents_in_overdraft" in metrics

    def test_get_metrics_settlement_rate_is_float(self, client, simple_config):
        """settlement_rate is a float between 0 and 1."""
        # GIVEN: A simulation
        create_resp = client.post("/simulations", json=simple_config)
        sim_id = create_resp.json()["simulation_id"]

        # WHEN: Query metrics
        response = client.get(f"/simulations/{sim_id}/metrics")
        data = response.json()

        # THEN: settlement_rate is float in valid range
        assert isinstance(data["metrics"]["settlement_rate"], float)
        assert 0.0 <= data["metrics"]["settlement_rate"] <= 1.0

    def test_get_metrics_avg_delay_is_float(self, client, simple_config):
        """avg_delay_ticks is a float."""
        # GIVEN: A simulation
        create_resp = client.post("/simulations", json=simple_config)
        sim_id = create_resp.json()["simulation_id"]

        # WHEN: Query metrics
        response = client.get(f"/simulations/{sim_id}/metrics")
        data = response.json()

        # THEN: avg_delay_ticks is float
        assert isinstance(data["metrics"]["avg_delay_ticks"], float)

    def test_get_metrics_counts_are_integers(self, client, simple_config):
        """All count fields are integers."""
        # GIVEN: A simulation
        create_resp = client.post("/simulations", json=simple_config)
        sim_id = create_resp.json()["simulation_id"]

        # WHEN: Query metrics
        response = client.get(f"/simulations/{sim_id}/metrics")
        data = response.json()

        metrics = data["metrics"]

        # THEN: Count fields are integers
        assert isinstance(metrics["total_arrivals"], int)
        assert isinstance(metrics["total_settlements"], int)
        assert isinstance(metrics["max_delay_ticks"], int)
        assert isinstance(metrics["queue1_total_size"], int)
        assert isinstance(metrics["queue2_total_size"], int)
        assert isinstance(metrics["peak_overdraft"], int)
        assert isinstance(metrics["agents_in_overdraft"], int)

    def test_get_metrics_settlements_le_arrivals(self, client, config_with_activity):
        """Settlements cannot exceed arrivals."""
        # GIVEN: A simulation with activity
        create_resp = client.post("/simulations", json=config_with_activity)
        sim_id = create_resp.json()["simulation_id"]

        # WHEN: Run simulation
        client.post(f"/simulations/{sim_id}/tick", params={"count": 10})

        # THEN: Settlements <= arrivals
        response = client.get(f"/simulations/{sim_id}/metrics")
        data = response.json()
        metrics = data["metrics"]

        assert metrics["total_settlements"] <= metrics["total_arrivals"]

    def test_get_metrics_after_running_ticks(self, client, config_with_activity):
        """Metrics reflect simulation activity."""
        # GIVEN: A simulation with activity
        create_resp = client.post("/simulations", json=config_with_activity)
        sim_id = create_resp.json()["simulation_id"]

        # WHEN: Run 20 ticks
        client.post(f"/simulations/{sim_id}/tick", params={"count": 20})

        # THEN: Some arrivals occurred
        response = client.get(f"/simulations/{sim_id}/metrics")
        data = response.json()
        metrics = data["metrics"]

        assert metrics["total_arrivals"] > 0

    def test_get_metrics_404_for_nonexistent_simulation(self, client):
        """Returns 404 for non-existent simulation."""
        # WHEN: Query metrics for non-existent simulation
        response = client.get("/simulations/nonexistent-id/metrics")

        # THEN: Returns 404
        assert response.status_code == 404

    def test_get_metrics_tick_and_day_match_simulation_state(self, client, simple_config):
        """tick and day fields match simulation state."""
        # GIVEN: A simulation
        create_resp = client.post("/simulations", json=simple_config)
        sim_id = create_resp.json()["simulation_id"]

        # WHEN: Run 5 ticks
        client.post(f"/simulations/{sim_id}/tick", params={"count": 5})

        # Get current state
        state_resp = client.get(f"/simulations/{sim_id}/state")
        state = state_resp.json()

        # Get metrics
        metrics_resp = client.get(f"/simulations/{sim_id}/metrics")
        metrics_data = metrics_resp.json()

        # THEN: tick and day match
        assert metrics_data["tick"] == state["current_tick"]
        assert metrics_data["day"] == state["current_day"]


class TestEndpointIntegration:
    """Integration tests across multiple endpoints."""

    def test_costs_and_metrics_both_available(self, client, simple_config):
        """Both endpoints work for same simulation."""
        # GIVEN: A simulation
        create_resp = client.post("/simulations", json=simple_config)
        sim_id = create_resp.json()["simulation_id"]

        # WHEN: Query both endpoints
        costs_resp = client.get(f"/simulations/{sim_id}/costs")
        metrics_resp = client.get(f"/simulations/{sim_id}/metrics")

        # THEN: Both succeed
        assert costs_resp.status_code == 200
        assert metrics_resp.status_code == 200

    def test_costs_increase_over_time(self, client, config_with_activity):
        """Costs increase monotonically over ticks."""
        # GIVEN: A simulation
        create_resp = client.post("/simulations", json=config_with_activity)
        sim_id = create_resp.json()["simulation_id"]

        # Run 10 ticks
        client.post(f"/simulations/{sim_id}/tick", params={"count": 10})
        costs1 = client.get(f"/simulations/{sim_id}/costs").json()

        # WHEN: Run 10 more ticks
        client.post(f"/simulations/{sim_id}/tick", params={"count": 10})
        costs2 = client.get(f"/simulations/{sim_id}/costs").json()

        # THEN: Total system cost increased (or stayed same)
        assert costs2["total_system_cost"] >= costs1["total_system_cost"]

    def test_metrics_update_after_ticks(self, client, config_with_activity):
        """Metrics reflect new arrivals after ticking."""
        # GIVEN: A simulation
        create_resp = client.post("/simulations", json=config_with_activity)
        sim_id = create_resp.json()["simulation_id"]

        # Initial metrics
        metrics1 = client.get(f"/simulations/{sim_id}/metrics").json()["metrics"]

        # WHEN: Run ticks
        client.post(f"/simulations/{sim_id}/tick", params={"count": 15})

        # THEN: Arrivals increased
        metrics2 = client.get(f"/simulations/{sim_id}/metrics").json()["metrics"]
        assert metrics2["total_arrivals"] > metrics1["total_arrivals"]
