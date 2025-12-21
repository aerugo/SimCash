# Phase 5: Integration Tests

**Status**: Pending
**Started**:

---

## Objective

Verify end-to-end reasoning capture from LLM call through to database persistence. Ensure reasoning can be retrieved after an experiment completes.

---

## Invariants Enforced in This Phase

- INV-2: Determinism - Reasoning doesn't affect simulation results
- INV-9: Policy Evaluation Identity - Same policy with/without reasoning produces same evaluation

---

## TDD Steps

### Step 5.1: Write Integration Tests

Create `api/tests/integration/test_reasoning_persistence.py`:

**Test Cases**:
1. `test_reasoning_persisted_to_database` - Reasoning stored in llm_interaction_log
2. `test_reasoning_queryable_by_game_id` - Can query reasoning after experiment
3. `test_reasoning_preserved_across_iterations` - Each iteration has its own reasoning

```python
"""Integration tests for LLM reasoning persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import tempfile
from pathlib import Path

from payment_simulator.ai_cash_mgmt.persistence.models import (
    GameSessionRecord,
    LLMInteractionRecord,
)
from payment_simulator.ai_cash_mgmt.persistence.repository import GameRepository
from payment_simulator.llm.audit_wrapper import AuditCaptureLLMClient, LLMInteraction
from payment_simulator.llm.result import LLMResult


class TestReasoningPersistence:
    """Integration tests for reasoning persistence."""

    @pytest.fixture
    def temp_db(self) -> Path:
        """Create a temporary database file."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            return Path(f.name)

    @pytest.fixture
    def repository(self, temp_db: Path) -> GameRepository:
        """Create a repository with initialized schema."""
        repo = GameRepository(temp_db)
        repo.initialize_schema()
        return repo

    @pytest.fixture
    def game_session(self, repository: GameRepository) -> GameSessionRecord:
        """Create a test game session."""
        session = GameSessionRecord(
            game_id="test-game-001",
            scenario_config="test.yaml",
            master_seed=12345,
            game_mode="rl_optimization",
            config_json="{}",
            started_at=datetime.now(),
            status="running",
            optimized_agents=["BANK_A"],
        )
        repository.save_game_session(session)
        return session

    def test_reasoning_persisted_to_database(
        self,
        repository: GameRepository,
        game_session: GameSessionRecord,
    ) -> None:
        """Verify reasoning is stored in llm_interaction_log."""
        # Create an LLM interaction record with reasoning
        interaction_record = LLMInteractionRecord(
            interaction_id="int-001",
            game_id=game_session.game_id,
            agent_id="BANK_A",
            iteration_number=1,
            system_prompt="You are a policy optimizer.",
            user_prompt="Optimize the payment policy.",
            raw_response='{"policy": "fifo"}',
            parsed_policy_json='{"policy": "fifo"}',
            parsing_error=None,
            llm_reasoning="I analyzed the current policy and determined that...",
            request_timestamp=datetime.now(),
            response_timestamp=datetime.now(),
        )

        repository.save_llm_interaction(interaction_record)

        # Retrieve and verify
        retrieved = repository.get_llm_interaction(
            game_session.game_id, "BANK_A", 1
        )
        assert retrieved is not None
        assert retrieved.llm_reasoning == "I analyzed the current policy and determined that..."

    def test_reasoning_queryable_by_game_id(
        self,
        repository: GameRepository,
        game_session: GameSessionRecord,
    ) -> None:
        """Verify reasoning can be queried by game_id."""
        # Create multiple interactions
        for i in range(3):
            interaction = LLMInteractionRecord(
                interaction_id=f"int-{i:03d}",
                game_id=game_session.game_id,
                agent_id="BANK_A",
                iteration_number=i + 1,
                system_prompt="system",
                user_prompt=f"prompt {i}",
                raw_response="response",
                parsed_policy_json=None,
                parsing_error=None,
                llm_reasoning=f"Reasoning for iteration {i + 1}",
                request_timestamp=datetime.now(),
                response_timestamp=datetime.now(),
            )
            repository.save_llm_interaction(interaction)

        # Query all interactions for the game
        interactions = repository.get_llm_interactions_for_game(game_session.game_id)
        assert len(interactions) == 3
        for i, interaction in enumerate(interactions):
            assert interaction.llm_reasoning == f"Reasoning for iteration {i + 1}"

    def test_reasoning_preserved_across_agents(
        self,
        repository: GameRepository,
        game_session: GameSessionRecord,
    ) -> None:
        """Verify each agent's reasoning is stored separately."""
        for agent in ["BANK_A", "BANK_B"]:
            interaction = LLMInteractionRecord(
                interaction_id=f"int-{agent}",
                game_id=game_session.game_id,
                agent_id=agent,
                iteration_number=1,
                system_prompt="system",
                user_prompt="prompt",
                raw_response="response",
                parsed_policy_json=None,
                parsing_error=None,
                llm_reasoning=f"Reasoning for {agent}",
                request_timestamp=datetime.now(),
                response_timestamp=datetime.now(),
            )
            repository.save_llm_interaction(interaction)

        # Query for each agent
        bank_a_int = repository.get_llm_interaction(
            game_session.game_id, "BANK_A", 1
        )
        bank_b_int = repository.get_llm_interaction(
            game_session.game_id, "BANK_B", 1
        )

        assert bank_a_int.llm_reasoning == "Reasoning for BANK_A"
        assert bank_b_int.llm_reasoning == "Reasoning for BANK_B"

    def test_null_reasoning_handled(
        self,
        repository: GameRepository,
        game_session: GameSessionRecord,
    ) -> None:
        """Verify NULL reasoning is handled correctly."""
        interaction = LLMInteractionRecord(
            interaction_id="int-null",
            game_id=game_session.game_id,
            agent_id="BANK_A",
            iteration_number=1,
            system_prompt="system",
            user_prompt="prompt",
            raw_response="response",
            parsed_policy_json=None,
            parsing_error=None,
            llm_reasoning=None,  # No reasoning
            request_timestamp=datetime.now(),
            response_timestamp=datetime.now(),
        )
        repository.save_llm_interaction(interaction)

        retrieved = repository.get_llm_interaction(
            game_session.game_id, "BANK_A", 1
        )
        assert retrieved is not None
        assert retrieved.llm_reasoning is None
```

### Step 5.2: Verify Repository Methods Exist

Ensure `GameRepository` has methods for:
- `save_llm_interaction(record: LLMInteractionRecord) -> None`
- `get_llm_interaction(game_id, agent_id, iteration) -> LLMInteractionRecord | None`
- `get_llm_interactions_for_game(game_id) -> list[LLMInteractionRecord]`

If these don't exist, implement them.

### Step 5.3: End-to-End Test with Mock LLM

```python
"""End-to-end test with mock LLM for reasoning flow."""

@pytest.mark.asyncio
async def test_full_reasoning_capture_flow(
    repository: GameRepository,
    game_session: GameSessionRecord,
) -> None:
    """Test complete flow from LLM call to database."""
    # This would require setting up the full optimization loop
    # with a mock LLM that returns reasoning.
    #
    # Simplified version: verify the data structures work together

    # 1. Create LLMInteraction with reasoning
    interaction = LLMInteraction(
        system_prompt="system",
        user_prompt="user",
        raw_response="response",
        parsed_policy={"name": "test"},
        parsing_error=None,
        prompt_tokens=100,
        completion_tokens=50,
        latency_seconds=1.5,
        reasoning_summary="Full reasoning text...",
    )

    # 2. Convert to record for persistence
    record = LLMInteractionRecord(
        interaction_id="full-test-001",
        game_id=game_session.game_id,
        agent_id="BANK_A",
        iteration_number=1,
        system_prompt=interaction.system_prompt,
        user_prompt=interaction.user_prompt,
        raw_response=interaction.raw_response,
        parsed_policy_json=str(interaction.parsed_policy),
        parsing_error=interaction.parsing_error,
        llm_reasoning=interaction.reasoning_summary,
        request_timestamp=datetime.now(),
        response_timestamp=datetime.now(),
    )

    # 3. Save and retrieve
    repository.save_llm_interaction(record)
    retrieved = repository.get_llm_interaction(
        game_session.game_id, "BANK_A", 1
    )

    # 4. Verify reasoning preserved
    assert retrieved.llm_reasoning == "Full reasoning text..."
```

---

## Implementation Details

### Repository Method Signatures

```python
class GameRepository:
    def save_llm_interaction(
        self, record: LLMInteractionRecord
    ) -> None:
        """Save an LLM interaction record."""
        ...

    def get_llm_interaction(
        self,
        game_id: str,
        agent_id: str,
        iteration_number: int,
    ) -> LLMInteractionRecord | None:
        """Retrieve a specific LLM interaction."""
        ...

    def get_llm_interactions_for_game(
        self, game_id: str
    ) -> list[LLMInteractionRecord]:
        """Get all LLM interactions for a game."""
        ...
```

---

## Files

| File | Action |
|------|--------|
| `api/tests/integration/test_reasoning_persistence.py` | CREATE |
| `api/payment_simulator/ai_cash_mgmt/persistence/repository.py` | MODIFY (if needed) |

---

## Verification

```bash
# Run integration tests
cd api
.venv/bin/python -m pytest tests/integration/test_reasoning_persistence.py -v

# Type check
.venv/bin/python -m mypy payment_simulator/ai_cash_mgmt/persistence/repository.py
```

---

## Completion Criteria

- [ ] All integration tests pass
- [ ] Reasoning persisted to database correctly
- [ ] Reasoning queryable by game_id, agent_id, iteration
- [ ] NULL reasoning handled correctly
- [ ] No data loss or truncation of reasoning text
