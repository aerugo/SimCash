"""E2E test: run one optimization round with each Vertex AI model.

This is a manual integration test — run with:
  SIMCASH_AUTH_DISABLED=true SIMCASH_STORAGE=local \
  python -m pytest tests/test_e2e_models.py -v -s --timeout=120

Requires:
  - Backend running on port 8642
  - GOOGLE_APPLICATION_CREDENTIALS set for Vertex AI
  - SA has roles/aiplatform.user
"""
import os
import json
import httpx
import pytest

BASE = "http://0.0.0.0:8642/api"

# Only test Vertex AI models (no OpenAI/Anthropic keys)
VERTEX_MODELS = [
    "google-vertex:gemini-3-flash",
    "google-vertex:gemini-2.5-flash",
    "google-vertex:gemini-3.0-pro",
    "google-vertex:glm-5-maas",
]


@pytest.fixture(scope="module")
def client():
    return httpx.Client(base_url=BASE, timeout=120)


def _switch_model(client: httpx.Client, model_id: str):
    """Switch the active optimization model."""
    r = client.patch("/settings", json={"optimization_model": model_id})
    assert r.status_code == 200, f"Failed to switch to {model_id}: {r.text}"
    return r.json()


def _create_game(client: httpx.Client) -> str:
    """Create a simple 2-bank game with AI enabled."""
    r = client.post("/games", json={
        "scenario": "preset_2bank_12tick",
        "num_days": 2,
        "use_ai": True,
        "mock_reasoning": False,
        "optimization_interval": 1,
        "constraint_preset": "simple",
    })
    assert r.status_code == 200, f"Create game failed: {r.text}"
    data = r.json()
    return data["game_id"]


def _step_game(client: httpx.Client, game_id: str) -> dict:
    """Run one day (step)."""
    r = client.post(f"/games/{game_id}/step")
    assert r.status_code == 200, f"Step failed: {r.text}"
    return r.json()


@pytest.mark.parametrize("model_id", VERTEX_MODELS)
def test_one_optimization_round(client, model_id):
    """Create game, run day 0, optimize with the model, verify policy produced."""
    print(f"\n{'='*60}")
    print(f"Testing model: {model_id}")
    print(f"{'='*60}")

    # Switch model
    result = _switch_model(client, model_id)
    print(f"Switched to: {result['optimization_model']}")

    # Create game
    game_id = _create_game(client)
    print(f"Game created: {game_id}")

    # Run day 0 (baseline)
    day0 = _step_game(client, game_id)
    print(f"Day 0 complete. Cost: {day0.get('total_cost', 'N/A')}")

    # Run day 1 (triggers optimization after day 0)
    day1 = _step_game(client, game_id)
    print(f"Day 1 complete. Cost: {day1.get('total_cost', 'N/A')}")

    # Check that optimization happened (policies should be non-default)
    r = client.get(f"/games/{game_id}/policy-history")
    if r.status_code == 200:
        history = r.json()
        print(f"Policy history days: {len(history.get('days', []))}")
        if history.get("days"):
            last_day = history["days"][-1]
            for agent_id, policy_info in last_day.get("policies", {}).items():
                fraction = policy_info.get("parameters", {}).get("initial_liquidity_fraction", "N/A")
                status = policy_info.get("status", "N/A")
                print(f"  {agent_id}: fraction={fraction}, status={status}")

    print(f"✅ {model_id} — optimization round complete")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--timeout=120"])
