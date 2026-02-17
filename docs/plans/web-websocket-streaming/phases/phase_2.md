# Phase 2: Backend — Granular Message Types for Simulation Phases

**Status**: Pending

---

## Objective

Add fine-grained progress messages within each day: simulation start/complete, and per-agent LLM call status. Define the complete message type enum for the protocol.

---

## Invariants Enforced in This Phase

- INV-2: Determinism — progress messages are observational, don't affect results
- INV-GAME-2: Agent Isolation — LLM progress per agent, not leaked across agents

---

## TDD Steps

### Step 2.1: Define Message Types (RED)

**Create `web/backend/app/ws_protocol.py`:**

```python
"""WebSocket message protocol for game streaming."""
from __future__ import annotations
from enum import Enum
from typing import Any


class WSMessageType(str, Enum):
    # Connection
    GAME_STATE = "game_state"
    ERROR = "error"

    # Day lifecycle
    SIMULATION_START = "simulation_start"
    DAY_COMPLETE = "day_complete"

    # Optimization lifecycle
    OPTIMIZATION_START = "optimization_start"
    LLM_CALLING = "llm_calling"
    LLM_COMPLETE = "llm_complete"
    OPTIMIZATION_COMPLETE = "optimization_complete"

    # Game lifecycle
    GAME_COMPLETE = "game_complete"


def ws_msg(msg_type: WSMessageType, **kwargs) -> dict[str, Any]:
    """Build a typed WebSocket message."""
    return {"type": msg_type.value, **kwargs}
```

### Step 2.2: Wire into Game (GREEN)

Add optional callback to `Game` for progress reporting:

```python
# In game.py
class Game:
    def __init__(self, ..., progress_callback=None):
        self._progress = progress_callback or (lambda msg: None)

    def run_day(self) -> GameDay:
        self._progress({"type": "simulation_start", "day": self.current_day})
        # ... existing simulation code ...
        self._progress({"type": "day_complete", "day": day.day_num})
        return day

    async def optimize_policies(self) -> dict:
        for aid in self.agent_ids:
            self._progress({"type": "optimization_start", "day": self.current_day - 1, "agent_id": aid})
            # ... optimization ...
            self._progress({"type": "optimization_complete", "day": self.current_day - 1, "agent_id": aid})
```

### Step 2.3: Update WS handler to use protocol

```python
# In main.py WS handler
from .ws_protocol import WSMessageType, ws_msg

async def send_progress(msg):
    await websocket.send_json(msg)

game._progress = send_progress
```

### Step 2.4: Refactor

- Use `ws_msg()` builder everywhere for consistency
- Ensure callback is async-safe (wrap sync game methods)

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `web/backend/app/ws_protocol.py` | Create | Message type enum + builder |
| `web/backend/app/game.py` | Modify | Add progress callback support |
| `web/backend/app/main.py` | Modify | Wire callback in WS handler |

## Verification

```bash
$HOME/Library/Python/3.9/bin/uv run --directory api python -m pytest /Users/ned/.openclaw/workspace-nash/SimCash/web/backend/tests/test_ws_streaming.py -v --tb=short
```

## Completion Criteria

- [ ] `WSMessageType` enum covers all message types
- [ ] `ws_msg()` builder produces valid messages
- [ ] Game emits `simulation_start` before running simulation
- [ ] Game emits per-agent `optimization_start`/`optimization_complete`
- [ ] Progress callback is optional (REST endpoints unaffected)
