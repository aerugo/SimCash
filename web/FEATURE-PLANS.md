# Feature Plans — Scenario Editor UX

Based on Stefan's testing feedback (2026-02-22). He created 3 complex 25-day scenarios with 4-8 banks and found the form works great for 2-4 banks but needs quality-of-life improvements for larger scenarios.

---

## 1. Clone Agent Button

**Problem:** Creating 6-8 bank scenarios requires manually configuring each agent from scratch. Banks in the same "tier" (e.g., mid-tier banks) share most settings — balance, payment amounts, arrival rates. Copy-pasting is tedious.

**Solution:** Add a "Clone" button (📋) next to each agent's remove button. Cloning duplicates all config with an auto-generated unique ID.

**Implementation:**
- Add clone icon button in `AgentCard` header, between edit and remove
- On click: deep-copy the agent's config, generate next available ID (`BANK_C` → `BANK_C_2` or next letter)
- Auto-update all existing agents' `counterparty_weights` to include the new agent (default weight 1.0)
- Auto-set the cloned agent's `counterparty_weights` to include all existing agents (default weight 1.0)
- Focus/scroll to the new agent card

**Files:** `web/frontend/src/components/ScenarioForm.tsx` (add clone handler + button)

**Effort:** Small — ~30 lines. Pure frontend.

---

## 2. Bulk Counterparty Presets

**Problem:** With N agents, there are N×(N-1) counterparty weight fields. For 6 banks that's 30 fields. Stefan's scenarios use heterogeneous weights (major bank gets more traffic), but setting each one manually is painful.

**Solution:** Add preset buttons above the counterparty weights section: "Equal", "Proportional to Balance", "Hub-and-Spoke", plus a "Set All" quick-fill input.

**Presets:**
- **Equal** — all weights = 1.0 (uniform distribution)
- **Proportional to Balance** — weight ∝ `opening_balance / max(opening_balance)` across counterparties. Major banks attract more payments.
- **Hub-and-Spoke** — first agent gets weight 3.0, rest get 1.0. Models a dominant clearing bank.
- **Set All to X** — single input field + apply button, sets every weight to the entered value

**Implementation:**
- Add a row of small buttons above the counterparty weights grid in `AgentCard`
- Each preset iterates `allAgentIds` (excluding self) and sets weights
- "Proportional" reads `opening_balance` from other agents in the form state
- Optionally: add a global-level preset that applies to ALL agents at once (in `ScenarioForm`, not per-card)

**Files:** `web/frontend/src/components/ScenarioForm.tsx` (preset buttons + logic in AgentCard)

**Effort:** Medium — ~80 lines. Needs access to all agents' balances for proportional preset.

---

## 3. Agent Templates (Bank Profiles)

**Problem:** Real payment systems have bank archetypes: major clearing banks (high balance, high volume), mid-tier commercial banks, small specialist banks. Users recreate these from scratch each time.

**Solution:** When adding a new agent, offer a template dropdown instead of always starting with defaults.

**Templates:**
- **Default** — current behavior (10000 balance, 1000 mean, etc.)
- **Major Bank** — high balance (50000), high volume (mean 3000), 12 payments/tick
- **Mid-Tier Bank** — moderate balance (20000), moderate volume (mean 1500), 8 payments/tick
- **Small Bank** — low balance (5000), low volume (mean 500), 4 payments/tick
- **Central Counterparty** — very high balance (100000), high volume, acts as hub

**Implementation:**
- Define template configs as a const object in `ScenarioForm.tsx`
- Replace the "Add Agent" button with a split button: click = default, dropdown arrow = template picker
- Template sets: `opening_balance`, `arrival_config.mean_amount`, `arrival_config.std_dev`, `arrival_config.payments_per_tick`
- User can still edit everything after creation — templates are just starting points
- Show template name as a subtle badge on the agent card (fades after first edit)

**Files:** `web/frontend/src/components/ScenarioForm.tsx` (template data + split button + AgentCard badge)

**Effort:** Medium — ~100 lines. Split button dropdown needs a small UI component.

---

## 4. Import/Export Agents (Copy Between Scenarios)

**Problem:** Stefan built 3 scenarios that share similar bank configurations (Lehman Month, Large Network, Periodic Shocks all have heterogeneous 4-6 bank setups). No way to reuse agent configs across scenarios.

**Solution:** Add "Copy Agent JSON" and "Paste Agent" buttons. Uses clipboard for simple cross-scenario transfer.

**Implementation:**
- **Copy:** Button on each agent card copies the agent's config as JSON to clipboard. Shows toast "Copied BANK_A config".
- **Paste:** Button next to "Add Agent" that reads clipboard, validates it's a valid agent config, adds it with a new unique ID if the ID already exists.
- Clipboard JSON is the same format as the YAML agent config (so it's also pasteable into the YAML editor).
- Handles counterparty weight fixup: removes references to agents not in current scenario, adds missing ones with default weight.

**Files:** `web/frontend/src/components/ScenarioForm.tsx` (copy/paste handlers + buttons)

**Effort:** Medium — ~60 lines. Clipboard API + validation + counterparty fixup.

---

## Priority Order

1. **Clone Agent** — highest impact, lowest effort. Unblocks fast multi-bank scenario creation.
2. **Bulk Counterparty Presets** — second biggest pain point for large scenarios.
3. **Agent Templates** — nice quality-of-life, but users can clone + edit which covers most cases.
4. **Import/Export Agents** — useful for power users, lowest priority.
