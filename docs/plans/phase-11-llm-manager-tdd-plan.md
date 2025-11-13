# Phase 11: LLM Manager Integration - TDD Implementation Plan

**Status**: Planning
**Priority**: High (P1)
**Created**: 2025-11-13
**Estimated Duration**: 3 weeks (15 working days)
**Dependencies**: Phase 9 (DSL) ✅, Phase 10 (Persistence) ✅

---

## Executive Summary

Implement an **asynchronous LLM Manager service** that improves agent policies between simulation episodes through code editing, with all changes validated via automated testing and Monte Carlo shadow replay before deployment.

**Core Innovation**: Policies evolve through LLM-driven iteration, with strict validation guardrails ensuring safety and performance improvements.

**Key Principle**: The LLM Manager is **decoupled** from the simulator—it runs independently, never blocks simulation execution, and all policy changes go through rigorous validation before deployment.

---

## Current State Assessment

### ✅ What's Complete (Enables This Phase)

**Phase 9 (DSL Infrastructure)**:
- ✅ JSON decision tree format with 50+ field accessors
- ✅ Expression evaluator with safe arithmetic/boolean operations
- ✅ Validation pipeline (schema, cycles, depth, field references)
- ✅ `TreePolicy::from_file()` for hot-reloading
- ✅ 940+ lines of DSL tests passing

**Phase 10 (Persistence)**:
- ✅ DuckDB storage with simulation_events, transactions, daily_agent_metrics
- ✅ Policy snapshot tracking (SHA256 hashing, provenance)
- ✅ Query interface with 9 analytical functions
- ✅ Checkpoint save/load for state restoration
- ✅ 71 persistence tests passing

**Phase 14-15 (Scenario Events)**:
- ✅ 7 event types for controlled interventions
- ✅ Replay identity support
- ✅ 29 scenario event tests passing

### ❌ What's Missing (This Phase Will Build)

1. **LLM Service Integration**: No code generation or policy proposal logic
2. **Shadow Replay Engine**: Can replay from DB, but no policy swapping logic
3. **Validation Pipeline**: No automated policy comparison or guardrail checking
4. **Episode Collection**: No systematic storage of seed+opponent combinations
5. **Deployment Automation**: No git-based policy versioning or rollback
6. **Learning Loop**: No continuous improvement workflow

### 🐛 Known Issues to Fix First

**Test Failures** (2 failing in test_queue2_events.py):
- Tests expect `RtgsQueue2Settle` event type
- System actually emits `Queue2LiquidityRelease` event
- **Resolution**: Update test expectations to match actual event naming
- **Effort**: 30 minutes
- **Priority**: P0 (blocks clean baseline)

**Action**: Fix these tests BEFORE starting Phase 11 implementation.

---

## Success Criteria

### Functional Requirements

1. **Policy Proposal Generation** ✅
   - LLM receives episode history (seeds, KPIs, opponent policies)
   - LLM proposes candidate policy as valid JSON DSL
   - Proposal includes description of changes and expected improvement

2. **Automated Validation** ✅
   - Schema validation (syntax correctness via DSL validator)
   - Property tests (no negative amounts, valid field references)
   - Shadow replay against 10+ historical episodes
   - Guardrail enforcement (<10% cost increase allowed)

3. **Monte Carlo Shadow Replay** ✅
   - Load historical episode from database
   - Swap in new policy for target agent
   - Re-run deterministically with same seed
   - Compare KPIs (cost, settlement_rate, delays)

4. **Deployment Pipeline** ✅
   - Git commit for approved policy
   - Tag with version (e.g., `agent_A_policy_v24`)
   - Rollback mechanism (revert to previous commit)
   - Atomic swap (old policy → new policy with zero downtime)

5. **Learning Loop** ✅
   - Collect episodes with new policy
   - Update LLM context with outcomes
   - Iterate improvement proposals
   - Track convergence metrics

### Non-Functional Requirements

1. **Determinism**: Same seed + same policies = identical replay
2. **Isolation**: LLM service crashes don't affect simulator
3. **Performance**: Shadow replay runs at full speed (1000+ ticks/sec)
4. **Safety**: No policy deployed without passing all guardrails
5. **Auditability**: Every policy change logged with provenance

---

## Phase 0: Clean Baseline (Day 1, 2-3 hours)

**Goal**: Fix failing tests to establish clean test baseline before new work.

### Task 0.1: Fix Queue2 Event Test Naming

**File**: `api/tests/unit/test_queue2_events.py`

**Issue**: Tests expect `RtgsQueue2Settle` but system emits `Queue2LiquidityRelease`

**Solution**:
```python
# Line 93: Change from
queue2_settle_events = [e for e in tick1_events if e.get("event_type") == "RtgsQueue2Settle"]

# To
queue2_settle_events = [e for e in tick1_events if e.get("event_type") == "Queue2LiquidityRelease"]

# Line 203: Similar change
queue2_settle_events = [e for e in tick1_events if e.get("event_type") == "Queue2LiquidityRelease"]
```

**Test**:
```bash
.venv/bin/python -m pytest tests/unit/test_queue2_events.py -v
# Expected: 2 passed, 1 skipped
```

**Acceptance Criteria**:
- ✅ All unit tests pass (224 passed)
- ✅ All FFI tests pass (35 passed)
- ✅ All integration tests pass
- ✅ All E2E tests pass
- ✅ Zero test failures

**Commit**: `fix(tests): update Queue2 event test expectations to match Queue2LiquidityRelease`

---

## Phase 1: Episode Collection Infrastructure (Days 2-3, 2 days)

**Goal**: Systematically store simulation episodes with full provenance for shadow replay.

### Architecture

```
SimulationEpisode:
  - episode_id (UUID)
  - seed (int)
  - config_hash (SHA256)
  - agent_policies (Dict[agent_id, policy_hash])
  - opponent_snapshot (frozen policy versions)
  - final_kpis (Dict[agent_id, metrics])
  - tick_count (int)
  - timestamp (datetime)
```

### Task 1.1: Database Schema Extension (TDD)

**Test First** (`tests/unit/test_episode_schema.py`):
```python
def test_episode_record_has_required_fields():
    """Episode record must have all fields for shadow replay."""
    from payment_simulator.persistence.models import EpisodeRecord

    episode = EpisodeRecord(
        episode_id="ep-abc123",
        simulation_id="sim-xyz789",
        seed=12345,
        config_hash="sha256:abc...",
        agent_policies={"BANK_A": "sha256:def...", "BANK_B": "sha256:ghi..."},
        final_kpis={"BANK_A": {"total_cost": 50000, "settlement_rate": 0.95}},
        tick_count=100,
        created_at="2025-11-13T00:00:00Z"
    )

    assert episode.episode_id is not None
    assert episode.seed > 0
    assert len(episode.agent_policies) > 0
    assert "BANK_A" in episode.final_kpis
```

**Implementation** (`api/payment_simulator/persistence/models.py`):
```python
class EpisodeRecord(BaseModel):
    """Simulation episode record for LLM Manager replay."""

    episode_id: str = Field(..., description="Unique episode identifier")
    simulation_id: str = Field(..., description="Parent simulation ID")
    seed: int = Field(..., description="RNG seed for deterministic replay")
    config_hash: str = Field(..., description="SHA256 of simulation config")
    agent_policies: Dict[str, str] = Field(..., description="Policy hash per agent")
    opponent_snapshot: Dict[str, Any] = Field(..., description="Frozen opponent policies")
    final_kpis: Dict[str, Dict[str, float]] = Field(..., description="Final KPIs per agent")
    tick_count: int = Field(..., description="Total ticks executed")
    created_at: str = Field(..., description="ISO timestamp")

    class Config:
        table_name = "episodes"
        primary_key = ["episode_id"]
        indexes = [
            ("idx_episode_config", ["config_hash"]),
            ("idx_episode_seed", ["seed"]),
            ("idx_episode_created", ["created_at"]),
        ]
```

**Acceptance Criteria**:
- ✅ 5+ tests for EpisodeRecord schema
- ✅ Migration applied successfully
- ✅ Can insert/query episodes from database

### Task 1.2: Episode Writer Integration (TDD)

**Test First** (`tests/integration/test_episode_writer.py`):
```python
def test_episode_saved_at_end_of_simulation():
    """Episode automatically saved when simulation completes."""
    config = create_test_config_2_agents()
    db = DatabaseManager("test_episodes.db")
    orch = Orchestrator.new(config)

    for _ in range(100):
        orch.tick()

    writer = EpisodeWriter(db, orch)
    episode_id = writer.save_episode()

    episode = db.get_episode(episode_id)
    assert episode["seed"] == config["rng_seed"]
    assert episode["tick_count"] == 100
```

**Acceptance Criteria**:
- ✅ 8+ tests for episode writer
- ✅ Episodes saved automatically at simulation end
- ✅ Final KPIs match orchestrator state

### Task 1.3: Episode Query Interface (TDD)

**Implementation** (`api/payment_simulator/persistence/queries.py`):
```python
def sample_episodes(
    conn: duckdb.DuckDBPyConnection,
    n: int,
    config_hash: Optional[str] = None,
) -> List[Dict]:
    """Sample random episodes matching criteria."""
    query = "SELECT * FROM episodes WHERE 1=1"
    params = []

    if config_hash:
        query += " AND config_hash = ?"
        params.append(config_hash)

    query += f" ORDER BY RANDOM() LIMIT {n}"
    return conn.execute(query, params).fetchdf().to_dict(orient="records")
```

**Acceptance Criteria**:
- ✅ 6+ tests for episode queries
- ✅ Can sample random episodes efficiently
- ✅ Query performance <100ms for 10K episodes

**Phase 1 Deliverable**: 19+ tests passing

---

## Phase 2: Shadow Replay Engine (Days 4-5, 2 days)

**Goal**: Re-run historical episodes with swapped policies for validation.

### Task 2.1: Policy Swap Logic (TDD)

**Test First** (`tests/unit/test_policy_swapper.py`):
```python
def test_swap_agent_policy_in_config():
    """Can replace agent's policy in config without mutating original."""
    original_config = {
        "agents": [
            {"id": "BANK_A", "policy": {"type": "Fifo"}},
            {"id": "BANK_B", "policy": {"type": "LiquidityAware"}},
        ]
    }

    new_policy_json = {"type": "TreePolicy", "tree": {...}}
    swapper = PolicySwapper()
    modified_config = swapper.swap_policy(
        original_config, agent_id="BANK_A", new_policy=new_policy_json
    )

    assert original_config["agents"][0]["policy"]["type"] == "Fifo"
    assert modified_config["agents"][0]["policy"]["type"] == "TreePolicy"
```

**Acceptance Criteria**:
- ✅ 5+ tests for policy swapper
- ✅ Original config never mutated

### Task 2.2: Shadow Replay Executor (TDD)

**Implementation** (`api/payment_simulator/llm/shadow_replayer.py`):
```python
class ShadowReplayer:
    """Re-run historical episodes with new policies."""

    def replay_episode(
        self,
        episode_id: str,
        agent_id: str,
        new_policy: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Replay episode with optionally swapped policy."""
        episode = self.db.get_episode(episode_id)
        config = self._reconstruct_config(episode)

        if new_policy:
            swapper = PolicySwapper()
            config = swapper.swap_policy(config, agent_id, new_policy)

        orch = Orchestrator.new(config)
        for _ in range(episode["tick_count"]):
            orch.tick()

        new_kpis = self._extract_kpis(orch, agent_id)
        baseline_kpis = episode["final_kpis"][agent_id]
        kpi_delta = self._compute_delta(baseline_kpis, new_kpis)

        return {
            "episode_id": episode_id,
            "baseline_kpis": baseline_kpis,
            "new_kpis": new_kpis,
            "kpi_delta": kpi_delta,
        }
```

**Acceptance Criteria**:
- ✅ 6+ tests for shadow replayer
- ✅ Deterministic replay verified
- ✅ Performance: replay runs at full speed

### Task 2.3: Monte Carlo Validation (TDD)

**Implementation** (`api/payment_simulator/llm/monte_carlo_validator.py`):
```python
class MonteCarloValidator:
    """Validate policies via Monte Carlo shadow replay."""

    def validate_policy(
        self,
        agent_id: str,
        new_policy: Dict[str, Any],
        n_episodes: int = 10,
    ) -> Dict[str, Any]:
        """Validate policy against N random episodes."""
        episodes = self.db.sample_episodes(n=n_episodes)
        results = []

        for ep in episodes:
            result = self.replayer.replay_episode(
                episode_id=ep["episode_id"],
                agent_id=agent_id,
                new_policy=new_policy,
            )
            results.append(result)

        cost_changes = [r["kpi_delta"]["cost_change_pct"] for r in results]
        avg_cost_change = np.mean(cost_changes)
        improvement_count = sum(1 for c in cost_changes if c < 0)

        return {
            "avg_cost_change_pct": avg_cost_change,
            "improvement_count": improvement_count,
            "recommendation": self._make_recommendation(avg_cost_change, improvement_count, n_episodes),
        }
```

**Acceptance Criteria**:
- ✅ 8+ tests for Monte Carlo validator
- ✅ Runs 10 episodes in <10 seconds
- ✅ Guardrails enforced

**Phase 2 Deliverable**: 19+ tests passing

---

## Phase 3: LLM Policy Generator (Days 6-8, 3 days)

**Goal**: LLM service that proposes policy improvements.

### Task 3.1: Episode Analyzer (TDD)

**Implementation** (`api/payment_simulator/llm/episode_analyzer.py`):
```python
class EpisodeAnalyzer:
    """Analyze episode history to identify improvement opportunities."""

    def analyze_trends(self, episodes: List[Dict], agent_id: str) -> Dict:
        costs = [ep["final_kpis"][agent_id]["total_cost"] for ep in episodes]
        delays = [ep["final_kpis"][agent_id]["avg_delay"] for ep in episodes]

        return {
            "cost_trend": "INCREASING" if costs[-1] > costs[0] else "DECREASING",
            "avg_cost": np.mean(costs),
            "avg_delay": np.mean(delays),
            "problems": self._identify_problems(delays),
        }

    def suggest_optimizations(self, episodes, agent_id) -> Dict:
        analysis = self.analyze_trends(episodes, agent_id)
        suggestions = {}

        if np.mean([ep["final_kpis"][agent_id]["avg_delay"] for ep in episodes]) > 10:
            suggestions["reduce_delay_costs"] = {
                "priority": "HIGH",
                "strategy": "Submit transactions earlier to avoid Queue 1 delay costs",
            }

        return suggestions
```

**Acceptance Criteria**:
- ✅ 6+ tests for episode analyzer
- ✅ Trends correctly identified

### Task 3.2: LLM Prompt Builder (TDD)

**Implementation** (`api/payment_simulator/llm/prompt_builder.py`):
```python
class LLMPromptBuilder:
    """Build prompts for LLM policy generation."""

    def build_improvement_prompt(
        self,
        agent_id: str,
        current_policy: Dict[str, Any],
        episodes: List[Dict],
        goal: str = "reduce_total_cost",
    ) -> str:
        analyzer = EpisodeAnalyzer()
        analysis = analyzer.analyze_trends(episodes, agent_id)
        suggestions = analyzer.suggest_optimizations(episodes, agent_id)

        prompt = f"""You are an expert payment system policy optimizer.

Agent: {agent_id}

Current Policy:
```json
{json.dumps(current_policy, indent=2)}
```

Recent Performance (last {len(episodes)} episodes):
- Average Total Cost: ${analysis['avg_cost']/100:.2f}
- Cost Trend: {analysis['cost_trend']}

Task: Generate an improved policy that reduces total cost by 5-10%.

Output ONLY valid JSON:
```json
{{
  "description": "Brief explanation",
  "policy": {{ ... policy tree ... }}
}}
```
"""
        return prompt
```

**Acceptance Criteria**:
- ✅ 5+ tests for prompt builder
- ✅ Prompts include all required context

### Task 3.3: LLM Client Integration (TDD)

**Implementation** (`api/payment_simulator/llm/llm_client.py`):
```python
import anthropic

class LLMClient:
    """Client for LLM policy generation."""

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def generate_policy(self, prompt: str) -> Dict[str, Any]:
        message = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = message.content[0].text
        json_text = self._extract_json(response_text)
        return json.loads(json_text)
```

**Acceptance Criteria**:
- ✅ 5+ tests for LLM client
- ✅ Handles valid responses

### Task 3.4: Policy Generator Integration (TDD)

**Implementation** (`api/payment_simulator/llm/policy_generator.py`):
```python
class PolicyGenerator:
    """Generate improved policies via LLM."""

    def generate_improvement(self, agent_id: str, n_episodes: int = 5) -> Dict:
        episodes = self.db.get_recent_episodes(n=n_episodes)
        current_policy = self._get_current_policy(agent_id, episodes[0])

        prompt = self.prompt_builder.build_improvement_prompt(
            agent_id, current_policy, episodes
        )

        llm_response = self.llm_client.generate_policy(prompt)

        return {
            "candidate_policy": llm_response["policy"],
            "description": llm_response["description"],
            "validation_errors": self._validate_policy(llm_response["policy"]),
        }
```

**Acceptance Criteria**:
- ✅ 6+ tests for policy generator
- ✅ End-to-end pipeline operational

**Phase 3 Deliverable**: 22+ tests passing

---

## Phase 4: Validation & Deployment Pipeline (Days 9-11, 3 days)

**Goal**: Automated validation and safe deployment of LLM-generated policies.

### Task 4.1: Validation Orchestrator (TDD)

**Implementation** (`api/payment_simulator/llm/validation_orchestrator.py`):
```python
class ValidationOrchestrator:
    """Orchestrate all validation steps."""

    def validate_candidate(
        self,
        agent_id: str,
        candidate_policy: Dict[str, Any],
        n_episodes: int = 10,
    ) -> Dict[str, Any]:
        results = {"agent_id": agent_id}

        # Schema validation
        results["schema_validation"] = self._validate_schema(candidate_policy)
        if not results["schema_validation"]["passed"]:
            results["final_decision"] = "REJECTED"
            return results

        # Monte Carlo validation
        results["monte_carlo_results"] = self.mc_validator.validate_policy(
            agent_id, candidate_policy, n_episodes
        )

        # Guardrail checks
        results["guardrail_checks"] = self.guardrail_checker.check_guardrails(
            results["monte_carlo_results"]
        )

        # Final decision
        if results["guardrail_checks"]["violations"]:
            results["final_decision"] = "REJECTED"
        else:
            results["final_decision"] = "APPROVED"

        return results
```

**Acceptance Criteria**:
- ✅ 8+ tests for validation orchestrator
- ✅ All validation steps executed

### Task 4.2: Guardrail Checker (TDD)

**Implementation** (`api/payment_simulator/llm/guardrail_checker.py`):
```python
class GuardrailChecker:
    """Check policy against safety guardrails."""

    def check_guardrails(self, monte_carlo_results: Dict) -> Dict:
        violations = []

        if monte_carlo_results["avg_cost_change_pct"] > 10.0:
            violations.append({
                "guardrail": "max_cost_increase",
                "value": monte_carlo_results["avg_cost_change_pct"],
                "threshold": 10.0,
            })

        return {"violations": violations, "all_passed": len(violations) == 0}
```

**Acceptance Criteria**:
- ✅ 6+ tests for guardrail checker
- ✅ All guardrails enforced

### Task 4.3: Git Deployment Manager (TDD)

**Implementation** (`api/payment_simulator/llm/git_deployment.py`):
```python
import git

class GitDeploymentManager:
    """Manage policy deployment via git."""

    def deploy_policy(self, agent_id: str, policy: Dict, description: str) -> Dict:
        version = self._get_next_version(agent_id)
        policy_path = self.repo_path / f"policies/{agent_id}_policy_v{version}.json"

        with open(policy_path, "w") as f:
            json.dump(policy, f, indent=2)

        self.repo.index.add([str(policy_path)])
        commit = self.repo.index.commit(f"[{agent_id}] {description}")

        tag_name = f"{agent_id}_policy_v{version}"
        self.repo.create_tag(tag_name, message=description)

        return {"version": version, "commit_sha": commit.hexsha}
```

**Acceptance Criteria**:
- ✅ 6+ tests for git deployment
- ✅ Policies committed with tags

**Phase 4 Deliverable**: 20+ tests passing

---

## Phase 5: Learning Loop & CLI Integration (Days 12-15, 4 days)

**Goal**: Continuous learning loop + CLI commands for policy evolution.

### Task 5.1: Learning Loop Coordinator (TDD)

**Implementation** (`api/payment_simulator/llm/learning_loop.py`):
```python
class LearningLoopCoordinator:
    """Coordinate continuous policy improvement loop."""

    def run_iteration(self, agent_id: str) -> Dict:
        # Generate candidate
        generation = self.policy_generator.generate_improvement(agent_id)

        # Validate
        validation = self.validator.validate_candidate(
            agent_id, generation["candidate_policy"]
        )

        # Deploy if approved
        if validation["final_decision"] == "APPROVED":
            deployment = self.git_manager.deploy_policy(
                agent_id, generation["candidate_policy"], generation["description"]
            )
            return {"deployed": True, "deployment": deployment}

        return {"deployed": False}
```

**Acceptance Criteria**:
- ✅ 6+ tests for learning loop
- ✅ Iterations execute correctly

### Task 5.2: CLI Commands (TDD)

**Implementation** (`api/payment_simulator/cli/commands/llm.py`):
```python
@app.command()
def generate(agent: str, episodes: int = 5):
    """Generate improved policy for agent."""
    generator = PolicyGenerator(db, llm_client)
    result = generator.generate_improvement(agent, episodes)

    output_path = f"{agent}_candidate_policy.json"
    with open(output_path, "w") as f:
        json.dump(result["candidate_policy"], f, indent=2)

    console.print(f"[green]✓ Policy saved to {output_path}[/green]")

@app.command()
def validate(policy: str, agent: str, episodes: int = 10):
    """Validate candidate policy."""
    with open(policy) as f:
        candidate = json.load(f)

    orchestrator = ValidationOrchestrator(db, llm_client)
    result = orchestrator.validate_candidate(agent, candidate, episodes)

    console.print(f"[bold]Decision: {result['final_decision']}[/bold]")

@app.command()
def learn(agent: str, max_iterations: int = 10):
    """Run continuous learning loop."""
    coordinator = LearningLoopCoordinator(db, llm_client, git_manager)
    result = coordinator.run_loop(agent, max_iterations)

    console.print(f"[green]Completed {result['iterations']} iterations[/green]")
```

**Acceptance Criteria**:
- ✅ 6+ tests for CLI commands
- ✅ All commands functional

### Task 5.3: Documentation & Examples

**Documentation** (`docs/llm_manager_guide.md`):
- Quick start guide
- Architecture overview
- Configuration reference
- Troubleshooting

**Acceptance Criteria**:
- ✅ User guide complete
- ✅ 3+ examples working

**Phase 5 Deliverable**: 12+ tests passing

---

## Testing Strategy

### Unit Tests (50+ tests)
- Episode schema and queries
- Policy swapper logic
- Episode analyzer
- LLM prompt builder
- Guardrail checker
- Git deployment

### Integration Tests (40+ tests)
- Episode writer integration
- Shadow replay with database
- Monte Carlo validation
- Policy generator end-to-end
- Validation orchestrator
- Learning loop

### End-to-End Tests (10+ tests)
- CLI commands
- Full learning loop
- Rollback scenarios

### Total: 100+ new tests

---

## Timeline Summary

| Phase | Days | Deliverable | Tests |
|-------|------|-------------|-------|
| 0: Clean Baseline | 0.5 | Fix test failures | 2 |
| 1: Episode Collection | 2 | Episode storage & queries | 19 |
| 2: Shadow Replay | 2 | Monte Carlo validation | 19 |
| 3: LLM Generator | 3 | Policy generation via LLM | 22 |
| 4: Validation Pipeline | 3 | Guardrails & deployment | 20 |
| 5: Learning Loop & CLI | 4 | Continuous improvement | 12 |
| **Total** | **14.5 days** | **Full LLM Manager** | **94+** |

---

## Success Metrics

**Functional**:
- ✅ LLM generates valid policy JSON (100% schema compliance)
- ✅ Shadow replay produces deterministic results
- ✅ Monte Carlo validation runs 10 episodes in <10 seconds
- ✅ Guardrails reject unsafe policies (zero false approvals)
- ✅ Git deployment atomic (no partial updates)

**Non-Functional**:
- ✅ Learning iteration completes in <2 minutes
- ✅ Zero simulator downtime during policy swap
- ✅ All policy changes auditable (git history)
- ✅ System handles LLM API failures gracefully

---

## Dependencies & Prerequisites

**External**:
- Anthropic API key (`ANTHROPIC_API_KEY` environment variable)
- Git repository initialized (`git init`)

**Internal**:
- ✅ Phase 9 DSL (policy validation)
- ✅ Phase 10 Persistence (episode storage)

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| LLM generates invalid policies | Multi-layer validation (schema + shadow replay) |
| Monte Carlo validation too slow | Parallelize replays, limit to 10 episodes |
| Policies degrade over time | Maintain policy zoo, enable rollback |
| LLM API failures | Retry with exponential backoff |

---

## Acceptance Criteria (Summary)

- ✅ 100+ tests passing (all phases)
- ✅ LLM Manager CLI operational
- ✅ Learning loop converges in realistic scenarios
- ✅ All policies versioned in git
- ✅ Documentation complete
- ✅ Zero test failures
- ✅ Determinism preserved (shadow replay = original)
- ✅ Guardrails enforce safety

---

## Next Steps After Phase 11

**Phase 12**: Multi-rail support (RTGS + DNS)
**Phase 13**: Enhanced shock scenarios
**Phase 16**: Production readiness (WebSocket, frontend, observability)
