# Penalty Mode — Handover to Frontend

**Branch:** `feature/penalty-mode`
**Author:** Dennis (backend)
**Date:** 2025-07-11

---

## What changed and why

Previously, deadline and end-of-day (EOD) penalties were always **fixed amounts in cents** — e.g. a $500 penalty regardless of whether the transaction was $100 or $10 million. This creates a problem for researchers: the cost ordering `liquidity < delay < penalty` breaks for large transactions, where a flat penalty becomes negligible relative to transaction size.

We added a **rate-based mode** where penalties are expressed in **basis points (bps)** applied to the transaction amount. This keeps penalties proportional to value and preserves the intended cost hierarchy across all transaction sizes.

## The `PenaltyMode` type

Both `deadline_penalty` and `eod_penalty` in `CostRates` now accept a `PenaltyMode` instead of a bare integer.

### Two modes

| Mode | Fields | Behavior |
|------|--------|----------|
| `fixed` | `amount` (int, cents) | Flat penalty regardless of tx size (old behavior) |
| `rate` | `bps_per_event` (float, ≥ 0) | `tx_amount × bps / 10,000` per event |

### Config examples (YAML)

```yaml
cost_rates:
  # Old style still works — bare int → fixed mode
  deadline_penalty: 50000

  # Explicit fixed
  eod_penalty:
    mode: fixed
    amount: 10000

  # Rate-based: 50 bps (0.5%) of transaction amount
  deadline_penalty:
    mode: rate
    bps_per_event: 50.0
```

### Python model

```python
from payment_simulator.config.schemas import PenaltyMode, CostRates

# Bare int still works (backwards compat)
cr = CostRates(deadline_penalty=50000)
assert cr.deadline_penalty.mode == "fixed"
assert cr.deadline_penalty.amount == 50000

# Rate mode
cr = CostRates(deadline_penalty={"mode": "rate", "bps_per_event": 50.0})
assert cr.deadline_penalty.mode == "rate"

# Serialization for FFI
cr.deadline_penalty.to_ffi_dict()
# → {"mode": "rate", "bps_per_event": 50.0}
```

### Backwards compatibility

- **Bare integers** in config YAML or Python dicts are auto-converted to `PenaltyMode(mode="fixed", amount=<value>)`.
- The old field name `eod_penalty_per_transaction` is accepted as an alias for `eod_penalty` (Pydantic alias + `populate_by_name=True`).
- Existing configs require **zero changes**.

## What the frontend needs to handle

### 1. Config UI for penalty fields

`deadline_penalty` and `eod_penalty` are no longer plain number inputs. The UI should let users choose between:

- **Fixed** — amount input (integer, cents)
- **Rate** — bps input (float, ≥ 0)

A mode toggle/dropdown with a contextual input field is the natural pattern.

### 2. Display in results/reports

When displaying cost configuration, show the mode:
- Fixed: `$500.00 (fixed)`
- Rate: `50.0 bps`

### 3. Validation

The Python model enforces:
- `mode` must be `"fixed"` or `"rate"`
- `fixed` requires `amount` (int)
- `rate` requires `bps_per_event` (float, ≥ 0)

The frontend can mirror these rules or rely on backend validation errors.

### 4. Cost ordering warning

A new validation warning fires when rate-mode penalties might violate the `liquidity < delay < penalty` cost ordering for typical transaction sizes. This is **informational only** — it doesn't block anything. If you surface validation warnings in the UI, include this one.

## What stays the same

- `split_friction_cost` — still a plain integer (operational cost, not value-dependent)
- `overdraft_bps_per_tick`, `delay_cost_per_tick_per_cent`, etc. — unchanged
- All other config shapes — unchanged

## Key files changed (backend)

| Layer | File | What |
|-------|------|------|
| Rust core | `simulator/src/costs/rates.rs` | `PenaltyMode` enum, `resolve()` method |
| Rust engine | `simulator/src/orchestrator/engine.rs` | Penalty accrual wiring |
| Rust FFI | `simulator/src/ffi/types.rs` | `parse_penalty_mode()` — accepts i64 or dict |
| Rust FFI | `simulator/src/ffi/orchestrator.rs` | Overdue query resolution |
| Rust policy | `simulator/src/policy/tree/context.rs` | Policy context penalty exposure |
| Python config | `api/payment_simulator/config/schemas.py` | `PenaltyMode` Pydantic model, `CostRates` fields |

## Design notes

- **EOD penalty base amount**: Uses the **remaining unsettled amount** at end of day (not original transaction amount). This is more realistic — partially settled transactions incur proportionally less penalty.
- **Bank-level policy context**: When rate mode is used, the bank-level penalty context resolves to 0 (since there's no single transaction to reference). Per-transaction context resolves correctly. This is an interim design — may be revisited if AI agents need aggregate penalty info.
- **All money is i64 cents** (INV-1). Rate mode computes via u128 intermediate to prevent overflow, then truncates to i64.
- **Deterministic** (INV-2). Same seed + config = identical results, including rate-mode penalties.

## Tests

- **Rust**: 1241 tests pass (`cd simulator && cargo test --no-default-features`)
- **Python**: 3369 pass, 43 fail (all 43 are pre-existing on `main`, unrelated to this work)
- **New test files**: `simulator/tests/test_penalty_mode.rs`, `api/tests/unit/test_penalty_mode.py`
