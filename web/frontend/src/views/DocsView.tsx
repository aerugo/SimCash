import { useState } from 'react';

type DocSection = 'overview' | 'how-it-works' | 'cost-model' | 'policy-optimization' | 'experiments' | 'game-theory' | 'architecture' | 'scenarios' | 'policies' | 'llm-optimization' | 'blog-convergence' | 'blog-coordination' | 'blog-bootstrap' | 'references';

interface NavItem {
  id: DocSection;
  label: string;
  icon: string;
  group: 'guide' | 'advanced' | 'blog' | 'reference';
}

const NAV: NavItem[] = [
  // Guides
  { id: 'overview', label: 'Overview', icon: '📖', group: 'guide' },
  { id: 'how-it-works', label: 'How the Simulator Works', icon: '⚙️', group: 'guide' },
  { id: 'cost-model', label: 'The Cost Model', icon: '💰', group: 'guide' },
  { id: 'policy-optimization', label: 'AI Policy Optimization', icon: '🤖', group: 'guide' },
  { id: 'experiments', label: 'Experiments', icon: '🧪', group: 'guide' },
  { id: 'game-theory', label: 'Game Theory Primer', icon: '♟️', group: 'guide' },
  { id: 'architecture', label: 'Technical Architecture', icon: '🏗️', group: 'guide' },
  // Advanced
  { id: 'scenarios', label: 'Scenario System', icon: '🎬', group: 'advanced' },
  { id: 'policies', label: 'Policy Decision Trees', icon: '🌳', group: 'advanced' },
  { id: 'llm-optimization', label: 'LLM Optimization Deep Dive', icon: '🧠', group: 'advanced' },
  // Blog
  { id: 'blog-convergence', label: 'Do LLM Agents Converge?', icon: '📝', group: 'blog' },
  { id: 'blog-coordination', label: 'Financial Stress Tests', icon: '📝', group: 'blog' },
  { id: 'blog-bootstrap', label: 'From FIFO to Nash', icon: '📝', group: 'blog' },
  // Reference
  { id: 'references', label: 'References & Reading', icon: '📚', group: 'reference' },
];

export function DocsView() {
  const [section, setSection] = useState<DocSection>('overview');

  const groups: { key: string; label: string; items: NavItem[] }[] = [
    { key: 'guide', label: 'Guides', items: NAV.filter(n => n.group === 'guide') },
    { key: 'advanced', label: 'Advanced Topics', items: NAV.filter(n => n.group === 'advanced') },
    { key: 'blog', label: 'Blog Posts', items: NAV.filter(n => n.group === 'blog') },
    { key: 'reference', label: 'Reference', items: NAV.filter(n => n.group === 'reference') },
  ];

  return (
    <div className="flex gap-6 max-w-6xl mx-auto">
      {/* Sidebar */}
      <nav className="w-56 shrink-0 hidden md:block">
        <div className="sticky top-24 space-y-5">
          {groups.map(g => (
            <div key={g.key}>
              <h4 className="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-2">{g.label}</h4>
              <div className="space-y-0.5">
                {g.items.map(item => (
                  <button
                    key={item.id}
                    onClick={() => setSection(item.id)}
                    className={`w-full text-left px-3 py-1.5 rounded-lg text-sm transition-colors ${
                      section === item.id
                        ? 'bg-sky-500/10 text-sky-400'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                    }`}
                  >
                    <span className="mr-2">{item.icon}</span>
                    {item.label}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </nav>

      {/* Mobile nav */}
      <div className="md:hidden w-full mb-4">
        <select
          value={section}
          onChange={e => setSection(e.target.value as DocSection)}
          className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-slate-200"
        >
          {NAV.map(n => (
            <option key={n.id} value={n.id}>{n.icon} {n.label}</option>
          ))}
        </select>
      </div>

      {/* Content */}
      <article className="flex-1 min-w-0">
        <div className="prose prose-invert prose-sm max-w-none">
          {section === 'overview' && <Overview />}
          {section === 'how-it-works' && <HowItWorks />}
          {section === 'cost-model' && <CostModel />}
          {section === 'policy-optimization' && <PolicyOptimization />}
          {section === 'experiments' && <Experiments />}
          {section === 'game-theory' && <GameTheory />}
          {section === 'architecture' && <Architecture />}
          {section === 'scenarios' && <Scenarios />}
          {section === 'policies' && <Policies />}
          {section === 'llm-optimization' && <LLMOptimization />}
          {section === 'blog-convergence' && <BlogConvergence />}
          {section === 'blog-coordination' && <BlogCoordination />}
          {section === 'blog-bootstrap' && <BlogBootstrap />}
          {section === 'references' && <References />}
        </div>
      </article>
    </div>
  );
}

/* ─── Guide Pages ─── */

function Overview() {
  return (
    <DocPage title="Overview" subtitle="What is SimCash and why does it exist?">
      <p>
        SimCash is an interactive research sandbox for exploring how AI agents learn to manage
        liquidity in payment systems. It models the fundamental coordination problem that banks
        face every day: <strong>how much cash should you keep ready?</strong>
      </p>

      <h3>The Problem</h3>
      <p>
        In a Real-Time Gross Settlement (RTGS) system, banks settle payments individually in real
        time. Each bank must decide how much liquidity to commit at the start of each day. This
        creates a strategic tradeoff:
      </p>
      <ul>
        <li><strong>Too much liquidity</strong> → expensive (opportunity cost of idle capital)</li>
        <li><strong>Too little liquidity</strong> → payments queue up, delays accumulate, deadlines are missed</li>
      </ul>
      <p>
        What makes this interesting is that each bank's optimal strategy depends on what other
        banks do. If your counterparty commits lots of liquidity, their payments to you settle
        quickly, giving you incoming cash to fund your own outgoing payments. This is a
        <em>coordination game</em>.
      </p>

      <h3>The Experiment</h3>
      <p>
        We let AI agents (powered by an LLM) play this game repeatedly. Each day, the Rust
        simulation engine runs the payment system with the agents' current policies. At the end
        of each day, each agent independently analyzes its own results — costs incurred, payments
        settled, delays suffered — and proposes an improved policy for the next day.
      </p>
      <p>
        Over many days, we watch whether these independently-optimizing agents converge to stable
        strategies, and whether those strategies resemble the game-theoretic equilibria predicted
        by economic theory.
      </p>

      <h3>Key Insight</h3>
      <Callout type="insight">
        <strong>Stability does not imply optimality.</strong> In our experiments, LLM agents
        reliably converge to <em>stable</em> policy profiles, but these aren't always
        Pareto-efficient. In deterministic scenarios, we observe <em>coordination failures</em>
        where one agent free-rides on the other's liquidity — the free-rider benefits while
        the exploited bank is worse off, and the system as a whole is less efficient than it
        could be. Stochastic environments with statistical evaluation produce more symmetric,
        near-optimal outcomes.
      </Callout>

      <h3>Context</h3>
      <p>
        SimCash was created by Hugi Aegisberg as a research tool for studying multi-agent
        coordination in payment systems. It implements and extends the experimental scenarios
        from the BIS Working Paper No. 1310, <em>"AI agents for cash management in payment
        systems"</em> (2025), which demonstrated that general-purpose LLMs can replicate key
        cash management practices even without domain-specific training.
      </p>
      <p>
        Where the BIS paper tested a single LLM agent's ability to make prudent liquidity
        decisions, SimCash asks the next question: what happens when <em>multiple</em> AI agents
        interact strategically? The answer involves coordination games, free-riding, and the
        surprising role of statistical evaluation in promoting cooperation.
      </p>
      <p>
        The simulation engine is built in Rust for speed and determinism, with a Python
        orchestration layer using PyO3 FFI. This work sits at the intersection of AI agents
        for economic research (Korinek, 2025) and computational game theory.
      </p>
    </DocPage>
  );
}

function HowItWorks() {
  return (
    <DocPage title="How the Simulator Works" subtitle="Ticks, queues, and settlement mechanics">
      <h3>Discrete-Time Simulation</h3>
      <p>
        Time in SimCash proceeds in <strong>ticks</strong> — atomic time units within a simulated
        trading day. A typical scenario has 12 ticks per day, representing the business hours of
        a payment system.
      </p>

      <h3>Payment Lifecycle</h3>
      <p>At each tick, the engine processes payments through these steps:</p>
      <ol>
        <li><strong>Arrivals</strong> — New payments arrive (stochastically or from a fixed schedule)</li>
        <li><strong>Policy Execution</strong> — Each bank's policy tree decides: Release or Hold each queued payment</li>
        <li><strong>Settlement</strong> — Released payments attempt RTGS settlement (requires sufficient balance)</li>
        <li><strong>Cost Accrual</strong> — Liquidity costs tick, delay costs accumulate on unsettled payments</li>
        <li><strong>End-of-Day</strong> — At the last tick, deadline penalties apply to unsettled payments</li>
      </ol>

      <h3>Two-Queue Architecture</h3>
      <p>
        The engine uses a two-queue design inspired by TARGET2:
      </p>
      <ul>
        <li><strong>Internal Queue (Q1)</strong> — Bank-controlled strategic queue. The policy tree decides what to release.</li>
        <li><strong>RTGS Queue (Q2)</strong> — Central system queue. Payments released from Q1 attempt immediate gross settlement.</li>
      </ul>

      <h3>Liquidity-Saving Mechanisms (LSM)</h3>
      <p>
        Optionally, the engine supports T2-compliant LSM features:
      </p>
      <ul>
        <li><strong>Bilateral Offsetting</strong> — Netted settlement when two banks owe each other</li>
        <li><strong>Multilateral Cycle Detection</strong> — Settles circular payment chains simultaneously</li>
      </ul>
      <p className="text-slate-500 text-xs">
        LSM features are available but not used in the current paper experiments.
      </p>

      <h3>Determinism</h3>
      <Callout type="info">
        SimCash is fully deterministic. Given the same seed and configuration, it produces
        byte-identical output. All randomness flows through a seeded xorshift64* RNG, and all
        money is represented as 64-bit integers (cents) — never floating point.
      </Callout>
    </DocPage>
  );
}

function CostModel() {
  return (
    <DocPage title="The Cost Model" subtitle="How banks are penalized — and why it matters">
      <p>
        The cost model creates the incentive structure that drives strategic behavior. It consists
        of three primary costs, ordered by severity:
      </p>

      <h3>1. Liquidity Cost (r<sub>c</sub>)</h3>
      <p>
        Proportional to committed funds per tick. Measured in basis points (bps). This represents
        the opportunity cost of holding reserves in the settlement account rather than investing
        them elsewhere.
      </p>
      <CodeBlock>{`cost = committed_balance × (bps / 10000) per tick`}</CodeBlock>
      <p>
        The rate depends on the scenario: Castro's r<sub>c</sub> = 0.1 is divided by ticks per day,
        giving 500 bps/tick (2-tick scenarios), 333 bps/tick (3-tick), or 83 bps/tick (12-tick).
        Always the cheapest cost — you prefer committing liquidity over the alternatives.
      </p>

      <h3>2. Delay Cost (r<sub>d</sub>)</h3>
      <p>
        Charged per cent of unsettled payment per tick. Represents the cost of failing to
        settle a payment on time — client dissatisfaction, SLA penalties, reputational damage.
      </p>
      <CodeBlock>{`cost = unsettled_amount × rate per tick`}</CodeBlock>
      <p>Castro baseline: r<sub>d</sub> = 0.2 per cent per tick. More expensive than liquidity cost.</p>

      <h3>3. Deadline Penalty</h3>
      <p>
        A flat fee for each payment that misses its individual deadline (each payment has
        a specific tick by which it should settle). Represents regulatory penalties or failed obligations.
      </p>
      <CodeBlock>{`cost = penalty_amount per unsettled payment at its deadline`}</CodeBlock>
      <p>Default: $500 (50,000 cents) per payment.</p>

      <h3>4. End-of-Day Penalty</h3>
      <p>
        A separate large penalty for any payment still unsettled when the day ends.
        Default: $1,000 (100,000 cents). This creates a hard deadline for all payments.
      </p>

      <h3>The Ordering Constraint</h3>
      <Callout type="important">
        <strong>r<sub>c</sub> &lt; r<sub>d</sub> &lt; r<sub>b</sub></strong> — Castro et al. require
        this ordering: liquidity cost &lt; delay cost &lt; borrowing/penalty cost. Banks should
        always prefer committing liquidity (cheapest) over delaying payments (medium) over missing
        deadlines entirely (most expensive). If this ordering is violated, the incentives break down.
      </Callout>

      <h3>Total Cost</h3>
      <p>
        Each agent's total cost is the sum across all ticks. The AI optimizer aims to minimize
        this total by choosing the right <code>initial_liquidity_fraction</code> — the fraction
        of the bank's liquidity pool to commit at the start of each day.
      </p>
    </DocPage>
  );
}

function PolicyOptimization() {
  return (
    <DocPage title="AI Policy Optimization" subtitle="How LLMs learn to be cash managers">
      <h3>The Multi-Day Loop</h3>
      <p>
        Each "game" runs for multiple simulated trading days. The optimization loop is:
      </p>
      <ol>
        <li>Day starts → banks commit liquidity according to their current policy</li>
        <li>Rust engine runs the full day (all ticks) with stochastic payment arrivals</li>
        <li>Day ends → costs tallied, events collected per agent</li>
        <li>AI analyzes each agent's results independently (information isolation)</li>
        <li>AI proposes improved policy (new <code>initial_liquidity_fraction</code> + decision tree)</li>
        <li>Optional: bootstrap evaluation compares new vs old policy statistically</li>
        <li>If accepted, next day uses new policy; if rejected, keeps old policy</li>
      </ol>

      <h3>Information Isolation</h3>
      <p>
        This is critical: each agent sees <strong>only its own</strong> costs, events, and
        transaction history. No counterparty balances, policies, or cost breakdowns. The only
        signal about other agents comes from incoming payment timing — just like in real RTGS
        systems where participants see settlement messages but not others' internal positions.
      </p>
      <Callout type="important">
        Crucially, agents are <strong>not told the environment is stationary</strong>. They don't
        know that iterations use the same payment parameters (or identical schedules in deterministic
        scenarios). Any regularity must be inferred from observed data. This is a realistic
        constraint — real cash managers don't have perfect knowledge of the data-generating process.
      </Callout>

      <h3>The Prompt</h3>
      <p>
        The PolicyOptimizer builds a 50,000+ token prompt containing:
      </p>
      <ul>
        <li>Current performance metrics and cost breakdown</li>
        <li>Verbose simulation output from best and worst performing seeds</li>
        <li>Full iteration history with acceptance status</li>
        <li>Parameter trajectories across iterations</li>
        <li>Optimization guidance based on cost analysis</li>
        <li>Policy schema (valid JSON structure)</li>
      </ul>

      <h3>Policy Format</h3>
      <p>
        The LLM outputs a JSON policy with two key components:
      </p>
      <CodeBlock>{`{
  "version": "2.0",
  "policy_id": "optimized_v5",
  "parameters": {
    "initial_liquidity_fraction": 0.085
  },
  "payment_tree": {
    "type": "condition", "field": "ticks_to_deadline",
    "operator": "<=", "value": 2,
    "true_branch": {"type": "action", "action": "Release"},
    "false_branch": {"type": "action", "action": "Hold"}
  },
  "bank_tree": {
    "type": "action", "action": "NoAction"
  }
}`}</CodeBlock>

      <h3>Constraint Validation</h3>
      <p>
        Every LLM output is validated against scenario constraints (parameter ranges, allowed
        fields, valid actions). Invalid policies trigger retry with error feedback — up to 3
        attempts before falling back to the current policy.
      </p>
    </DocPage>
  );
}

function Experiments() {
  return (
    <DocPage title="Experiments" subtitle="Replicating Castro et al. (2025)">
      <p>
        SimCash implements three canonical scenarios from Castro et al. (2025), each designed to
        test different aspects of multi-agent coordination:
      </p>

      <h3>Experiment 1: Asymmetric Equilibrium</h3>
      <table className="w-full text-sm">
        <tbody>
          <tr><td className="text-slate-400 pr-4">Ticks</td><td>2 per day</td></tr>
          <tr><td className="text-slate-400 pr-4">Payments</td><td>Asymmetric — A sends 15% at tick 1; B sends 15% at tick 0, 5% at tick 1</td></tr>
          <tr><td className="text-slate-400 pr-4">Mode</td><td>Deterministic-temporal</td></tr>
          <tr><td className="text-slate-400 pr-4">Expected</td><td>Asymmetric: A≈0%, B≈20%</td></tr>
          <tr><td className="text-slate-400 pr-4">Result</td><td>A=0.1%, B=17% — matches prediction ✓</td></tr>
        </tbody>
      </table>
      <p>
        Bank A free-rides on Bank B's liquidity provision. B must commit reserves to settle
        payments to A, which then gives A incoming liquidity to fund its own obligations.
      </p>

      <h3>Experiment 2: Stochastic Coordination</h3>
      <table className="w-full text-sm">
        <tbody>
          <tr><td className="text-slate-400 pr-4">Ticks</td><td>12 per day</td></tr>
          <tr><td className="text-slate-400 pr-4">Payments</td><td>Poisson arrivals (λ=2/tick), LogNormal amounts (μ=$100, σ=$50)</td></tr>
          <tr><td className="text-slate-400 pr-4">Mode</td><td>Bootstrap (50 paired samples)</td></tr>
          <tr><td className="text-slate-400 pr-4">Expected</td><td>Near-symmetric convergence</td></tr>
          <tr><td className="text-slate-400 pr-4">Result</td><td>A≈5.7–8.5%, B≈5.8–6.3% across 3 passes (near-symmetric)</td></tr>
        </tbody>
      </table>
      <p>
        The flagship experiment. Stochastic arrivals create genuine uncertainty, and bootstrap
        evaluation ensures statistical rigor in policy comparison.
      </p>

      <h3>Experiment 3: Symmetric Coordination</h3>
      <table className="w-full text-sm">
        <tbody>
          <tr><td className="text-slate-400 pr-4">Ticks</td><td>3 per day</td></tr>
          <tr><td className="text-slate-400 pr-4">Payments</td><td>Symmetric — both banks send 20% at ticks 0 and 1</td></tr>
          <tr><td className="text-slate-400 pr-4">Mode</td><td>Deterministic-temporal</td></tr>
          <tr><td className="text-slate-400 pr-4">Expected</td><td>Symmetric ≈20%</td></tr>
          <tr><td className="text-slate-400 pr-4">Result</td><td>Coordination failures in all 3 passes — one agent free-rides (1–10%) while the other overcommits (29–30%), but both end up worse off than the 50% baseline</td></tr>
        </tbody>
      </table>

      <Callout type="insight">
        The divergence between Experiments 2 and 3 is revealing: stochastic environments with
        statistical evaluation produce better coordination than deterministic environments.
        Bootstrap evaluation acts as a kind of "hedge" against greedy exploitation.
      </Callout>

      <h3>Methodology Differences from Castro et al.</h3>
      <ul>
        <li><strong>Implementation</strong>: Castro uses a custom simulator; SimCash reimplements the model in Rust with Python orchestration</li>
        <li><strong>Action space</strong>: Castro discretizes to 21 values (0%, 5%, ..., 100%); SimCash allows continuous values in [0,1]</li>
        <li><strong>Evaluation</strong>: Both use bootstrap paired comparison for stochastic scenarios; SimCash adds CV and CI acceptance criteria</li>
        <li><strong>Agent dynamics</strong>: Both optimize agents sequentially within iterations</li>
      </ul>
    </DocPage>
  );
}

function GameTheory() {
  return (
    <DocPage title="Game Theory Primer" subtitle="Nash equilibria, coordination, and free-riding">
      <h3>The Coordination Game</h3>
      <p>
        RTGS liquidity management is a <strong>coordination game</strong>. Each bank's optimal
        strategy depends on what other banks do. Unlike zero-sum games, there are mutual gains
        from coordination — if all banks commit appropriate liquidity, everyone benefits from
        faster settlement and lower delay costs.
      </p>

      <h3>Nash Equilibrium</h3>
      <p>
        A Nash equilibrium is a strategy profile where no player can improve their outcome by
        unilaterally changing their strategy. In payment systems, this means: given what every
        other bank is doing, each bank's liquidity allocation is already optimal for them.
      </p>
      <p>
        Castro et al. (2025) characterize the equilibria for several stylized scenarios. Our
        experiments test whether LLM agents can <em>discover</em> these equilibria through
        independent optimization without any explicit game-theoretic reasoning.
      </p>

      <h3>Free-Riding</h3>
      <p>
        A persistent phenomenon in our experiments: when one bank commits lots of liquidity, its
        payments to counterparties settle quickly, giving those counterparties incoming cash. The
        counterparties can then get away with committing less of their own liquidity — they're
        "free-riding" on the generous bank's reserves.
      </p>

      <h3>Pareto Efficiency</h3>
      <p>
        A stable outcome isn't necessarily a <em>good</em> outcome. A Pareto-efficient allocation
        means no one can be made better off without making someone worse off. Our coordination
        failures in Experiment 3 show agents converging to Pareto-<em>dominated</em> outcomes —
        both agents could be better off, but neither has an individual incentive to change.
      </p>

      <h3>Stochastic Environments Help</h3>
      <Callout type="insight">
        Stochastic payment arrivals + bootstrap evaluation seem to discourage free-riding.
        The statistical evaluation introduces a form of "noise" that makes greedy exploitation
        harder to sustain, pushing agents toward more symmetric, cooperative allocations.
      </Callout>

      <h3>AI Agents as Game Players</h3>
      <p>
        SimCash's agents follow what Korinek (2025) describes as the core agent loop:
        {' '}<strong>Think → Act → Observe → Respond</strong>. Each iteration, the LLM reasons
        about its cost history (Think), proposes a new policy (Act), the simulation runs (Observe),
        and results feed back into the next iteration (Respond). Unlike traditional game-theoretic
        agents with explicit utility maximization, these agents reason in natural language —
        making them both more flexible and more prone to the kinds of bounded rationality
        that produce coordination failures.
      </p>
    </DocPage>
  );
}

function Architecture() {
  return (
    <DocPage title="Technical Architecture" subtitle="Rust, Python, and the FFI boundary">
      <h3>Stack Overview</h3>
      <CodeBlock>{`┌─────────────────────────────────────────────┐
│  Web Frontend (React + TypeScript + Vite)   │
│  • Interactive UI, WebSocket streaming      │
└──────────────────┬──────────────────────────┘
                   │ HTTP/WS
┌──────────────────▼──────────────────────────┐
│  Web Backend (FastAPI)                      │
│  • Game orchestration, LLM calls            │
│  • PolicyOptimizer, bootstrap evaluation    │
└──────────────────┬──────────────────────────┘
                   │ PyO3 FFI
┌──────────────────▼──────────────────────────┐
│  Rust Simulation Engine                     │
│  • Tick loop, RTGS settlement, LSM          │
│  • Deterministic RNG, i64 arithmetic        │
└─────────────────────────────────────────────┘`}</CodeBlock>

      <h3>Design Principles</h3>
      <ul>
        <li><strong>Rust owns state; Python orchestrates.</strong> The simulation engine is a Rust library compiled as a Python extension via PyO3.</li>
        <li><strong>FFI boundary is minimal.</strong> Only primitives cross the boundary. Policies enter as JSON strings, results come back as dicts.</li>
        <li><strong>Money is i64.</strong> All monetary values are 64-bit integers representing cents. No floating-point arithmetic, no rounding errors.</li>
        <li><strong>Determinism is sacred.</strong> Same seed = identical output, always. The RNG is xorshift64*, and seeds are persisted after each use.</li>
        <li><strong>Replay identity.</strong> Running a simulation and replaying from checkpoint produce byte-identical output.</li>
      </ul>

      <h3>Policy Pipeline</h3>
      <p>How an LLM decision becomes a simulated outcome:</p>
      <ol>
        <li>LLM generates JSON policy (via PolicyOptimizer)</li>
        <li>ConstraintValidator checks against scenario constraints</li>
        <li>Extract <code>initial_liquidity_fraction</code> → set on agent config</li>
        <li>Wrap policy tree → <code>{`{"type": "InlineJson", "json_string": "..."}`}</code></li>
        <li><code>SimulationConfig.from_dict()</code> → <code>to_ffi_dict()</code></li>
        <li><code>Orchestrator.new(ffi_config)</code> → run ticks</li>
      </ol>

      <h3>LLM Configuration</h3>
      <p>
        The paper experiments used a large language model with reasoning effort <code>high</code>,
        temperature 0.5, and up to 25 iterations per experiment pass. Each experiment
        was run 3 times (independent passes) to assess reproducibility. The web sandbox
        defaults to algorithmic mode for zero-cost exploration, with optional LLM mode
        (currently Gemini 2.5 Flash via Google Vertex AI, admin-switchable).
      </p>

      <h3>Performance</h3>
      <p>
        The Rust engine achieves 1,000+ ticks/second and has been tested at 200+ agents.
        A typical 12-tick scenario with 2 banks runs in under 1ms. Bootstrap evaluation
        (50 samples × 2 policies) completes in ~100ms.
      </p>
    </DocPage>
  );
}

/* ─── Advanced Topics ─── */

function Scenarios() {
  return (
    <DocPage title="Scenario System" subtitle="Configuring simulated payment environments">
      <p>
        A <strong>scenario</strong> defines everything about a simulated payment environment:
        how many banks exist, when payments arrive, what they cost, and what events shake up the
        system. Scenarios are written in YAML and fully control the Rust simulation engine.
      </p>

      <h3>What a Scenario Configures</h3>
      <p>Every scenario specifies these core elements:</p>
      <ul>
        <li><strong>Simulation timing</strong> — ticks per day, number of days, RNG seed</li>
        <li><strong>Agents</strong> — bank identities, opening balances, credit limits, policies</li>
        <li><strong>Payment generation</strong> — how transactions arrive (stochastic or deterministic)</li>
        <li><strong>Cost rates</strong> — delay costs, overdraft rates, penalties</li>
        <li><strong>LSM settings</strong> — bilateral/multilateral offsetting configuration</li>
        <li><strong>Custom events</strong> — scheduled interventions (transfers, rate changes, collateral shocks)</li>
      </ul>

      <CodeBlock>{`# Minimal scenario example
simulation:
  ticks_per_day: 12
  num_days: 5
  rng_seed: 42

agents:
  - id: BANK_A
    opening_balance: 5000000  # $50,000 in cents
    unsecured_cap: 2000000
    policy:
      type: Fifo
    arrival_config:
      rate_per_tick: 2.0
      amount_distribution:
        type: LogNormal
        mean: 10.0
        std_dev: 1.0
      deadline_range: [5, 20]

  - id: BANK_B
    opening_balance: 5000000
    unsecured_cap: 2000000
    policy:
      type: Deadline
      urgency_threshold: 3
    arrival_config:
      rate_per_tick: 2.0
      amount_distribution:
        type: Uniform
        min: 5000
        max: 50000
      deadline_range: [5, 20]

cost_rates:
  delay_cost_per_tick_per_cent: 0.0001
  overdraft_bps_per_tick: 0.001
  eod_penalty_per_transaction: 100000
  deadline_penalty: 50000`}</CodeBlock>

      <h3>Payment Generation Modes</h3>
      <p>
        SimCash supports three modes for generating payment arrivals, which can be combined
        within a single scenario:
      </p>

      <h4>Deterministic (Custom Events Only)</h4>
      <p>
        No stochastic arrivals — every transaction is a <code>CustomTransactionArrival</code> event
        placed at a specific tick. Used for BIS paper replication and isolated feature tests where
        you need exact control over every payment.
      </p>

      <h4>Poisson Arrivals</h4>
      <p>
        Each tick, the number of new payments is drawn from a Poisson distribution with
        rate <code>λ = rate_per_tick</code>. This models realistic payment flow where arrivals
        are random but have a known average rate. Rates can be modified mid-simulation
        via <code>GlobalArrivalRateChange</code> or <code>AgentArrivalRateChange</code> events.
      </p>

      <h4>Amount Distributions</h4>
      <p>Payment amounts are sampled independently from one of four distributions:</p>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-700">
            <th className="text-left py-2 text-slate-300">Type</th>
            <th className="text-left py-2 text-slate-300">Parameters</th>
            <th className="text-left py-2 text-slate-300">Use Case</th>
          </tr>
        </thead>
        <tbody className="text-slate-400">
          <tr className="border-b border-slate-800"><td className="py-1.5 pr-4 font-mono text-sky-400">LogNormal</td><td>mean, std_dev (log-scale)</td><td>Realistic: many small, few large payments</td></tr>
          <tr className="border-b border-slate-800"><td className="py-1.5 pr-4 font-mono text-sky-400">Normal</td><td>mean, std_dev (cents)</td><td>Symmetric distribution around mean</td></tr>
          <tr className="border-b border-slate-800"><td className="py-1.5 pr-4 font-mono text-sky-400">Uniform</td><td>min, max (cents)</td><td>Equal probability in range</td></tr>
          <tr><td className="py-1.5 pr-4 font-mono text-sky-400">Exponential</td><td>lambda</td><td>Many small, exponentially fewer large</td></tr>
        </tbody>
      </table>

      <h3>Custom Events</h3>
      <p>
        Scenario events are deterministic interventions injected at specific ticks. They let you
        create crisis narratives, central bank interventions, and controlled stress tests.
      </p>

      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-700">
            <th className="text-left py-2 text-slate-300">Event Type</th>
            <th className="text-left py-2 text-slate-300">Effect</th>
          </tr>
        </thead>
        <tbody className="text-slate-400">
          <tr className="border-b border-slate-800"><td className="py-1.5 pr-4 font-mono text-sky-400">DirectTransfer</td><td>Instant balance move between agents, bypasses all queues</td></tr>
          <tr className="border-b border-slate-800"><td className="py-1.5 pr-4 font-mono text-sky-400">CustomTransactionArrival</td><td>Inject a transaction that flows through normal settlement</td></tr>
          <tr className="border-b border-slate-800"><td className="py-1.5 pr-4 font-mono text-sky-400">CollateralAdjustment</td><td>Add or remove collateral from an agent</td></tr>
          <tr className="border-b border-slate-800"><td className="py-1.5 pr-4 font-mono text-sky-400">GlobalArrivalRateChange</td><td>Multiply all agents' arrival rates (persists until next change)</td></tr>
          <tr className="border-b border-slate-800"><td className="py-1.5 pr-4 font-mono text-sky-400">AgentArrivalRateChange</td><td>Multiply one agent's arrival rate</td></tr>
          <tr className="border-b border-slate-800"><td className="py-1.5 pr-4 font-mono text-sky-400">CounterpartyWeightChange</td><td>Redirect payment flows by adjusting routing probabilities</td></tr>
          <tr><td className="py-1.5 pr-4 font-mono text-sky-400">DeadlineWindowChange</td><td>Tighten or loosen deadline pressure globally</td></tr>
        </tbody>
      </table>

      <p>Events use two scheduling modes:</p>
      <CodeBlock>{`# One-time event at tick 150 (day 2 of a 100-tick-per-day scenario)
scenario_events:
  - type: DirectTransfer
    from_agent: CENTRAL_BANK
    to_agent: STRESSED_BANK
    amount: 50000000  # $500K emergency injection
    schedule:
      type: OneTime
      tick: 150

  # Repeating event: collateral adjustments every 50 ticks
  - type: CollateralAdjustment
    agent: BANK_A
    delta: 1000000  # +$10K collateral
    schedule:
      type: Repeating
      start_tick: 100
      interval: 50
      end_tick: 400`}</CodeBlock>

      <h3>Scenario Design: Building a Stress Test</h3>
      <p>A realistic multi-phase crisis scenario follows this pattern:</p>
      <ol>
        <li><strong>Baseline phase</strong> (days 1–3) — Normal operations, establish cost baseline</li>
        <li><strong>Pressure phase</strong> (days 4–6) — Increase arrival rates (1.5–2×), inject large payments</li>
        <li><strong>Crisis phase</strong> (days 7–8) — Remove collateral, cut counterparty weights, spike rates</li>
        <li><strong>Intervention</strong> (day 9) — DirectTransfer liquidity injection, restore collateral</li>
        <li><strong>Recovery phase</strong> (days 10+) — Gradually restore rates to 1.0×, measure recovery speed</li>
      </ol>

      <Callout type="info">
        All events are deterministic and tick-based — there's no conditional logic
        ("if balance drops below X, inject liquidity"). This is by design: determinism ensures
        perfect reproducibility. The same config + same seed always produces byte-identical results.
      </Callout>

      <h3>Key Library Scenarios</h3>

      <h4>TARGET2 Crisis (25 days, 4 agents)</h4>
      <p>
        The flagship TARGET2 scenario. Tests all T2 features: dual priority system,
        bilateral/multilateral limits, algorithm sequencing, priority escalation. Features four
        distinct phases (Normal → Pressure → Crisis → Resolution) with one agent deliberately
        running a bad policy to create cascading gridlock. A "good policy" and "bad policy"
        variant let you compare system outcomes.
      </p>

      <h4>BIS Liquidity-Delay Tradeoff (1 day, 2 agents)</h4>
      <p>
        Direct replication of BIS Working Paper 1310 Box 3. Minimal configuration — 3 ticks,
        4 deterministic transactions, a liquidity pool with allocation fraction. Tests the
        fundamental tradeoff between liquidity cost and delay cost in a controlled setting.
      </p>

      <h4>Crisis Resolution (10 days, 4 agents)</h4>
      <p>
        Extends the advanced policy crisis scenario with a Day 4 "central bank intervention" —
        massive $500K DirectTransfer injections and $100K–$200K collateral boosts. Days 5–10
        show gradual recovery via stepped arrival rate restoration
        (0.5 → 0.7 → 0.8 → 0.85 → 0.9 → 1.0).
      </p>

      <h4>Suboptimal Policies (10/25 days, 4 agents)</h4>
      <p>
        A/B comparison of policy quality. Two "optimal" agents (well-tuned parameters) vs two
        "suboptimal" agents (conservative hoarder and reactive spender). Shows how subtle
        parameter differences compound over time, especially with high delay costs.
      </p>
    </DocPage>
  );
}

function Policies() {
  return (
    <DocPage title="Policy Decision Trees" subtitle="The DSL that controls bank behavior">
      <p>
        Every bank in SimCash is controlled by a <strong>policy</strong> — a JSON-based decision
        tree that determines how payments are handled, how budgets are set, and how collateral
        is managed. The policy DSL is expressive enough to encode strategies ranging from
        "release everything immediately" to sophisticated multi-factor adaptive approaches.
      </p>

      <h3>How Decision Trees Work</h3>
      <p>
        A policy tree is a binary decision tree. Each node is either a <strong>condition</strong>
        (which branches on true/false) or an <strong>action</strong> (a terminal decision).
        The tree is walked from root to leaf for each decision point, and the leaf action is executed.
      </p>
      <CodeBlock>{`{
  "type": "condition",
  "node_id": "check_urgency",
  "condition": {
    "op": "<=",
    "left": {"field": "ticks_to_deadline"},
    "right": {"param": "urgency_threshold"}
  },
  "on_true": {
    "type": "action",
    "node_id": "release_urgent",
    "action": "Release"
  },
  "on_false": {
    "type": "condition",
    "node_id": "check_balance",
    "condition": {
      "op": ">",
      "left": {"field": "balance"},
      "right": {"compute": {
        "op": "*",
        "left": {"field": "amount"},
        "right": {"value": 1.5}
      }}
    },
    "on_true": {"type": "action", "action": "Release"},
    "on_false": {"type": "action", "action": "Hold"}
  }
}`}</CodeBlock>

      <h3>The Four Tree Types</h3>
      <p>
        A complete policy definition (<code>DecisionTreeDef</code>) contains up to four
        independent trees, each evaluated at a different phase of the tick:
      </p>

      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-700">
            <th className="text-left py-2 text-slate-300">Tree</th>
            <th className="text-left py-2 text-slate-300">When Evaluated</th>
            <th className="text-left py-2 text-slate-300">Scope</th>
          </tr>
        </thead>
        <tbody className="text-slate-400">
          <tr className="border-b border-slate-800">
            <td className="py-1.5 pr-4 font-mono text-sky-400">bank_tree</td>
            <td>Once per tick, before payment processing</td>
            <td>Set budgets, write state registers</td>
          </tr>
          <tr className="border-b border-slate-800">
            <td className="py-1.5 pr-4 font-mono text-sky-400">payment_tree</td>
            <td>Per transaction in Queue 1</td>
            <td>Release / Hold / Split each payment</td>
          </tr>
          <tr className="border-b border-slate-800">
            <td className="py-1.5 pr-4 font-mono text-sky-400">strategic_collateral_tree</td>
            <td>Once per tick, after payment processing</td>
            <td>Proactive collateral posting</td>
          </tr>
          <tr>
            <td className="py-1.5 pr-4 font-mono text-sky-400">end_of_tick_collateral_tree</td>
            <td>Once per tick, at end of tick</td>
            <td>Reactive collateral cleanup</td>
          </tr>
        </tbody>
      </table>

      <Callout type="info">
        The <code>bank_tree</code> runs first and can set a release budget
        via <code>SetReleaseBudget</code>. The <code>payment_tree</code> may
        return <code>Release</code>, but the engine converts it to <code>Hold</code> if
        the budget is exhausted. This two-level control lets a policy set macro limits
        and then make micro decisions per payment.
      </Callout>

      <h3>Key Actions</h3>

      <h4>Payment Tree Actions</h4>
      <table className="w-full text-sm">
        <tbody className="text-slate-400">
          <tr className="border-b border-slate-800"><td className="py-1.5 pr-4 font-mono text-sky-400 w-40">Release</td><td>Submit payment to RTGS for settlement</td></tr>
          <tr className="border-b border-slate-800"><td className="py-1.5 pr-4 font-mono text-sky-400">Hold</td><td>Keep in queue for re-evaluation next tick</td></tr>
          <tr className="border-b border-slate-800"><td className="py-1.5 pr-4 font-mono text-sky-400">Split</td><td>Divide into N smaller payments and submit all</td></tr>
          <tr className="border-b border-slate-800"><td className="py-1.5 pr-4 font-mono text-sky-400">StaggerSplit</td><td>Split with staggered release timing</td></tr>
          <tr className="border-b border-slate-800"><td className="py-1.5 pr-4 font-mono text-sky-400">ReleaseWithCredit</td><td>Submit using intraday credit if needed</td></tr>
          <tr className="border-b border-slate-800"><td className="py-1.5 pr-4 font-mono text-sky-400">Reprioritize</td><td>Change payment priority without moving it</td></tr>
          <tr className="border-b border-slate-800"><td className="py-1.5 pr-4 font-mono text-sky-400">WithdrawFromRtgs</td><td>Pull payment back from Queue 2</td></tr>
          <tr><td className="py-1.5 pr-4 font-mono text-sky-400">ResubmitToRtgs</td><td>Change RTGS priority (Normal → Urgent → HighlyUrgent)</td></tr>
        </tbody>
      </table>

      <h4>Bank Tree Actions</h4>
      <table className="w-full text-sm">
        <tbody className="text-slate-400">
          <tr className="border-b border-slate-800"><td className="py-1.5 pr-4 font-mono text-sky-400 w-40">SetReleaseBudget</td><td>Set per-tick release limits (max value, per-counterparty caps)</td></tr>
          <tr className="border-b border-slate-800"><td className="py-1.5 pr-4 font-mono text-sky-400">SetState</td><td>Write a state register value (key must start with <code>bank_state_</code>)</td></tr>
          <tr className="border-b border-slate-800"><td className="py-1.5 pr-4 font-mono text-sky-400">AddState</td><td>Increment/decrement a state register</td></tr>
          <tr><td className="py-1.5 pr-4 font-mono text-sky-400">NoAction</td><td>Do nothing this tick</td></tr>
        </tbody>
      </table>

      <h4>Collateral Tree Actions</h4>
      <table className="w-full text-sm">
        <tbody className="text-slate-400">
          <tr className="border-b border-slate-800"><td className="py-1.5 pr-4 font-mono text-sky-400 w-40">PostCollateral</td><td>Post collateral to increase borrowing capacity</td></tr>
          <tr className="border-b border-slate-800"><td className="py-1.5 pr-4 font-mono text-sky-400">WithdrawCollateral</td><td>Withdraw collateral to reduce opportunity costs</td></tr>
          <tr><td className="py-1.5 pr-4 font-mono text-sky-400">HoldCollateral</td><td>Keep current collateral level unchanged</td></tr>
        </tbody>
      </table>

      <h3>Context Fields</h3>
      <p>
        Conditions can reference 80+ context fields. Here are the most important ones, organized by category:
      </p>

      <h4>Balance & Liquidity</h4>
      <p className="text-slate-400 text-sm font-mono">
        balance · effective_liquidity · credit_limit · available_liquidity · credit_used · liquidity_buffer · liquidity_pressure · credit_headroom
      </p>

      <h4>Transaction</h4>
      <p className="text-slate-400 text-sm font-mono">
        amount · remaining_amount · priority · ticks_to_deadline · arrival_tick · deadline_tick · is_past_deadline · is_overdue · overdue_duration · is_split · is_divisible
      </p>

      <h4>Queue State</h4>
      <p className="text-slate-400 text-sm font-mono">
        outgoing_queue_size · queue1_total_value · queue1_liquidity_gap · headroom · rtgs_queue_size · queue2_count_for_agent
      </p>

      <h4>Timing</h4>
      <p className="text-slate-400 text-sm font-mono">
        current_tick · system_tick_in_day · ticks_remaining_in_day · day_progress_fraction · is_eod_rush · system_current_day
      </p>

      <h4>Costs</h4>
      <p className="text-slate-400 text-sm font-mono">
        cost_delay_this_tx_one_tick · cost_overdraft_this_amount_one_tick · cost_overdraft_bps_per_tick · cost_delay_per_tick_per_cent · cost_deadline_penalty · cost_eod_penalty
      </p>

      <h4>Collateral</h4>
      <p className="text-slate-400 text-sm font-mono">
        posted_collateral · remaining_collateral_capacity · collateral_utilization · overdraft_headroom · excess_collateral
      </p>

      <h4>Counterparty & LSM</h4>
      <p className="text-slate-400 text-sm font-mono">
        tx_counterparty_id · tx_is_top_counterparty · my_bilateral_net_q2 · my_q2_out_value_to_counterparty · system_queue2_pressure_index
      </p>

      <h3>State Registers: Cross-Tick Memory</h3>
      <p>
        State registers let a policy maintain information across ticks within a day. They're
        <code>f64</code> values identified by keys prefixed with <code>bank_state_</code>.
      </p>
      <ul>
        <li>Set via <code>SetState</code> action, incremented via <code>AddState</code></li>
        <li>Read in any tree as a field: <code>{`{"field": "bank_state_cooldown"}`}</code></li>
        <li>Default to 0.0 if never set, max 10 per agent</li>
        <li><strong>Reset at end of each day</strong> — no multi-day memory</li>
      </ul>
      <p>Use cases: cooldown timers, release counters, running totals, mode flags.</p>

      <CodeBlock>{`// Bank tree: set a cooldown after releasing a lot
{
  "type": "condition",
  "condition": {
    "op": ">",
    "left": {"field": "bank_state_released_today"},
    "right": {"value": 500000}
  },
  "on_true": {
    "type": "action",
    "action": "SetState",
    "parameters": {
      "key": {"value": "bank_state_cooldown"},
      "value": {"value": 3},
      "reason": {"value": "high release volume, cooling off"}
    }
  },
  "on_false": {"type": "action", "action": "NoAction"}
}`}</CodeBlock>

      <h3>Policy Design Patterns</h3>

      <h4>The Cautious Banker</h4>
      <p>
        Conservative approach: maintain a large liquidity buffer, only release payments when
        the deadline is imminent or when the balance is well above the buffer threshold.
        Uses state registers to track how much has been released and enters a cooldown mode
        after heavy release ticks.
      </p>
      <ul>
        <li>Bank tree: <code>SetReleaseBudget</code> with a conservative cap</li>
        <li>Payment tree: Release if <code>ticks_to_deadline ≤ 3</code> OR <code>balance &gt; amount × 2.5</code></li>
        <li>Collateral tree: <code>PostCollateral</code> proactively at start of day, <code>WithdrawCollateral</code> at end</li>
        <li>Good for: avoiding overdraft, minimizing risk, stable cost profiles</li>
        <li>Weakness: high delay costs from holding too long</li>
      </ul>

      <h4>The Aggressive Market Maker</h4>
      <p>
        High-throughput strategy: release most payments immediately, use credit facilities
        aggressively, split large payments to maintain flow. Prioritizes settlement speed
        over liquidity conservation.
      </p>
      <ul>
        <li>Bank tree: <code>NoAction</code> (no budget constraints)</li>
        <li>Payment tree: Release everything except very large payments when balance is critically low</li>
        <li>Collateral tree: <code>PostCollateral</code> whenever overdraft utilization is high</li>
        <li>Good for: minimizing delay costs, high settlement rates</li>
        <li>Weakness: high liquidity and overdraft costs, vulnerable to rate spikes</li>
      </ul>

      <Callout type="insight">
        The optimal strategy typically falls between these extremes. The LLM optimization
        system can explore the space between "too cautious" and "too aggressive" by tuning
        parameters like <code>urgency_threshold</code> and <code>liquidity_buffer</code> and
        evolving the tree structure itself.
      </Callout>
    </DocPage>
  );
}

function LLMOptimization() {
  return (
    <DocPage title="LLM Optimization Deep Dive" subtitle="How AI agents learn, evaluate, and converge">
      <p>
        The LLM optimization system is the engine that drives policy improvement. It orchestrates
        a multi-day loop where each agent independently analyzes its performance, proposes improved
        policies, and statistically validates improvements before adoption.
      </p>

      <h3>The Optimization Loop</h3>
      <p>
        Each iteration follows five phases:
      </p>
      <ol>
        <li>
          <strong>Simulate</strong> — Run a full day with current policies. The Rust engine produces
          tick-by-tick events, cost breakdowns, and settlement outcomes.
        </li>
        <li>
          <strong>Evaluate</strong> — Compute each agent's costs. In bootstrap mode, this means
          running the policy on 50 resampled transaction sets to get statistical estimates.
        </li>
        <li>
          <strong>Propose</strong> — For each agent independently, build a 50,000+ token prompt
          with cost analysis, simulation traces, iteration history, and parameter trajectories.
          The LLM proposes a new policy JSON.
        </li>
        <li>
          <strong>Validate</strong> — The proposed policy is checked against scenario constraints:
          parameter ranges, allowed fields, valid actions. Invalid policies get up to 3 retries
          with error feedback appended to the prompt.
        </li>
        <li>
          <strong>Accept or Reject</strong> — Compare new vs old policy on the same samples
          (paired comparison). Accept only if the improvement is statistically significant.
        </li>
      </ol>

      <CodeBlock>{`Iteration 1: [Simulate] → [Evaluate] → [Propose A] → [Propose B] → [Accept/Reject]
Iteration 2: [Simulate] → [Evaluate] → [Propose A] → [Propose B] → [Accept/Reject]
...
Iteration N: [Simulate] → [Evaluate] → [Converged!]`}</CodeBlock>

      <h3>Bootstrap Evaluation</h3>
      <p>
        In stochastic scenarios, a single simulation run is unreliable — random payment arrivals
        mean the same policy can look great or terrible depending on the draw. Bootstrap evaluation
        solves this with <strong>paired comparison</strong>:
      </p>
      <ol>
        <li>Generate N bootstrap samples (default: 50) by resampling from observed transactions</li>
        <li>Run <em>both</em> the old and new policy on <em>each</em> sample</li>
        <li>Compute the cost difference (delta) per sample</li>
        <li>Accept if: mean delta &gt; 0, 95% CI doesn't cross zero, and CV ≤ 0.5</li>
      </ol>

      <Callout type="info">
        Using the <strong>same samples</strong> for both policies is crucial. It eliminates
        sample-to-sample variance — the only variation comes from the policy difference itself.
        This is far more sensitive than comparing means from independent samples.
      </Callout>

      <p>
        Each agent is evaluated in a <strong>3-agent sandbox</strong>: SOURCE → AGENT → SINK.
        The SOURCE generates transactions, the AGENT is the one being evaluated, and the SINK
        absorbs outgoing payments. This isolation ensures that an agent's evaluation isn't
        contaminated by other agents' changing policies.
      </p>

      <h3>Multi-Agent Isolation</h3>
      <p>
        Agent isolation is enforced at every level of the system:
      </p>
      <ul>
        <li><strong>Event filtering</strong> — Each agent's prompt contains only its own transactions, costs, and state changes. No counterparty balances or policies are revealed.</li>
        <li><strong>Separate history</strong> — Each agent has its own iteration history, best-cost tracking, and parameter trajectories.</li>
        <li><strong>Independent seeds</strong> — Each agent gets different RNG seeds per iteration via a SHA-256 seed matrix.</li>
        <li><strong>Isolated evaluation</strong> — Bootstrap samples and sandbox simulations are per-agent.</li>
      </ul>
      <p>
        This isolation is what enables Nash equilibrium finding. Each agent independently optimizes
        against the current state of the world (which includes other agents' fixed policies).
        If agents could see each other's strategies, they could game the optimization or coordinate
        in ways that don't reflect real RTGS incentives.
      </p>

      <h3>Nash Equilibrium and Convergence</h3>
      <p>
        In <strong>deterministic-temporal</strong> mode, convergence is detected when all agents'
        policies remain unchanged for a stability window (typically 5 iterations). Since deterministic
        evaluation gives identical costs for identical policies, stability means no agent can
        improve — which is precisely the definition of a Nash equilibrium.
      </p>
      <p>
        In <strong>bootstrap</strong> mode, convergence uses multiple signals:
      </p>
      <ul>
        <li><strong>Coefficient of variation (CV)</strong> — When cost variance drops below a threshold, the policy is stable</li>
        <li><strong>Trend analysis</strong> — Costs should be flat or declining, not oscillating</li>
        <li><strong>Regret</strong> — How far the current cost is from the best-ever cost</li>
      </ul>

      <Callout type="important">
        Convergence to a Nash equilibrium doesn't mean the outcome is <em>good</em>. In
        Experiment 3, agents reliably converge to stable profiles where one agent free-rides —
        a Nash equilibrium, but Pareto-dominated. Both agents would be better off at the
        symmetric equilibrium, but neither has an individual incentive to move there.
      </Callout>

      <h3>Optimization Interval</h3>
      <p>
        By default, agents optimize after every simulated day. But you can configure the
        <strong> optimization interval</strong> — how many days pass between optimization rounds.
        With an interval of 5, the agent plays 5 days with its current policy, accumulates more
        data, and then proposes a single improvement.
      </p>
      <ul>
        <li><strong>Interval = 1</strong> — Fastest learning, but each decision is based on a single day's data</li>
        <li><strong>Interval = 5–10</strong> — More data per decision, smoother convergence, less sensitive to single-day noise</li>
        <li><strong>Interval = N (large)</strong> — Almost batch optimization; useful when you want agents to commit to strategies</li>
      </ul>

      <h3>Three Evaluation Modes</h3>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-700">
            <th className="text-left py-2 text-slate-300">Mode</th>
            <th className="text-left py-2 text-slate-300">Acceptance Rule</th>
            <th className="text-left py-2 text-slate-300">Best For</th>
          </tr>
        </thead>
        <tbody className="text-slate-400">
          <tr className="border-b border-slate-800">
            <td className="py-1.5 pr-4 font-mono text-sky-400">bootstrap</td>
            <td>Statistical significance (95% CI) + variance check</td>
            <td>Stochastic scenarios — rigorous comparison</td>
          </tr>
          <tr className="border-b border-slate-800">
            <td className="py-1.5 pr-4 font-mono text-sky-400">deterministic-pairwise</td>
            <td>new_cost &lt; old_cost on same seed</td>
            <td>Single-agent deterministic optimization</td>
          </tr>
          <tr>
            <td className="py-1.5 pr-4 font-mono text-sky-400">deterministic-temporal</td>
            <td>Always accept; converge on policy stability</td>
            <td>Multi-agent Nash equilibrium finding</td>
          </tr>
        </tbody>
      </table>

      <h3>What the LLM Sees (and Doesn't)</h3>
      <p>
        The system prompt includes a <strong>filtered policy schema</strong> — only the actions,
        fields, and parameters that the scenario constraints allow. The LLM literally cannot
        see documentation for elements it isn't allowed to use, preventing hallucinated references
        to unavailable features.
      </p>
      <p>
        The user prompt includes cost breakdowns with priority flags (🔴 dominant cost, 🟡 significant,
        🟢 minor), automated trend detection (improving/worsening/oscillating), settlement rate
        alerts, and full iteration history with acceptance status markers (⭐ BEST / ✅ KEPT / ❌ REJECTED).
      </p>
    </DocPage>
  );
}

/* ─── Blog Posts ─── */

function BlogConvergence() {
  return (
    <DocPage title="Teaching AI to Play the Liquidity Game" subtitle="How LLM agents learn to optimize cash allocation — and discover Nash equilibria along the way" isBlog date="2026-02-17">
      <h3>The Game</h3>
      <p>
        Every morning, banks face a deceptively simple question: <em>how much cash should we set aside
        for today's payments?</em>
      </p>
      <p>
        In a Real-Time Gross Settlement (RTGS) system, payments settle individually and immediately —
        no netting, no batching, no safety net. A bank must commit liquidity at the start of the day
        to fund its outgoing obligations. Commit too much and you're paying opportunity costs on idle
        capital all day. Commit too little and payments queue up, deadlines are missed, and penalty
        costs pile up fast.
      </p>
      <p>
        What makes this truly interesting is that it's not a solo optimization problem — it's a
        <strong>coordination game</strong>. If Bank B commits generous liquidity, its payments to
        Bank A settle quickly, giving A incoming cash to fund its own outgoing payments. Bank A
        can then get away with committing less. Each bank's optimal strategy depends on what the
        other bank does, but neither bank can observe the other's decision.
      </p>
      <p>
        This is exactly the kind of problem that has clean theoretical solutions on paper but is
        fiendishly hard in practice. So we asked: can AI agents figure it out?
      </p>

      <h3>The Experiment</h3>
      <p>
        We set up two AI agents — BANK_A and BANK_B — each powered by a large language model (currently Gemini 2.5 Flash) with high
        reasoning effort. Each agent controls a single parameter: <code>initial_liquidity_fraction</code>,
        the fraction of its available liquidity pool to commit at the start of each simulated trading day.
        The value ranges from 0% (commit nothing, extremely risky) to 100% (commit everything,
        extremely expensive).
      </p>
      <p>
        The loop works like a real cash manager doing end-of-day review:
      </p>
      <ol>
        <li>The day starts. Each bank commits liquidity according to its current policy.</li>
        <li>Our Rust simulation engine runs a full 12-tick trading day with stochastic payment arrivals
        (Poisson-distributed, ~2 payments per tick, log-normally distributed amounts).</li>
        <li>The day ends. Costs are tallied — liquidity costs, delay penalties, deadline failures.</li>
        <li>Each agent independently reviews its own performance: what went wrong, what went right,
        how much each cost component contributed.</li>
        <li>Each agent proposes a new <code>initial_liquidity_fraction</code> for tomorrow.</li>
        <li>The new policy is statistically validated via bootstrap paired comparison (50 resampled
        scenarios, 95% confidence interval). Only accepted if the improvement is real, not noise.</li>
      </ol>
      <p>
        Critically, the agents are <strong>information-isolated</strong>. Each agent sees only its own
        costs, its own settlement history, its own iteration trajectory. No counterparty balances, no
        opponent policies, no shared state. The only signal about the other bank comes indirectly
        through the timing of incoming payments — just like in a real RTGS system.
      </p>

      <h3>What Happens: The Convergence Pattern</h3>
      <p>
        We ran this experiment multiple times (3 independent passes of up to 25 iterations each), and
        a consistent pattern emerged:
      </p>
      <p>
        <strong>Day 0 — The expensive default.</strong> Both agents start at 100% allocation. Every cent
        of available liquidity is committed. Payments settle instantly (great!), but the liquidity cost
        is enormous. Total costs are at their peak.
      </p>
      <p>
        <strong>Days 1–3 — The big drop.</strong> Agents rapidly discover that they're massively
        over-allocating. The LLM sees the cost breakdown, notices that liquidity cost dominates
        everything else, and proposes dramatic cuts. Fractions drop from 100% to somewhere in the
        20–40% range. Costs fall by 60–80%. This is the "obvious wins" phase — the agent doesn't
        need sophisticated reasoning to see that 100% is wasteful.
      </p>
      <p>
        <strong>Days 4–7 — Fine-tuning.</strong> Now it gets interesting. The agents are in the right
        ballpark, but each adjustment is smaller and more nuanced. Cut too aggressively and delay
        costs spike. The LLM starts reasoning about the tradeoff explicitly: "reducing from 15% to
        12% saved X in liquidity costs but caused Y in additional delays." Adjustments shrink to
        1–3 percentage points per iteration.
      </p>
      <p>
        <strong>Days 8–10+ — Near-equilibrium.</strong> Policies stabilize. Proposed changes are tiny
        (fractions of a percent) and many are rejected by the bootstrap validator — the improvement
        isn't statistically significant. The agents have found their groove.
      </p>

      <Callout type="insight">
        The final converged values from our Experiment 2 replication: <strong>BANK_A ≈ 8.8%,
        BANK_B ≈ 5.2%</strong>. The BIS paper's analytical result for the same scenario:
        A = 8.5%, B = 6.3%. Different runs produce slightly different numbers (A ranges 5.7–8.8%,
        B ranges 5.2–6.3% across passes), but they consistently land in the same neighborhood.
        The agents are finding the right answer.
      </Callout>

      <h3>The Cool Part: Emergent Coordination</h3>
      <p>
        Here's what makes this more than a parameter search: it's a <strong>multi-agent game</strong>.
        BANK_A's optimal liquidity fraction depends on what BANK_B does, and vice versa. If B
        commits more, A can commit less (because B's payments to A provide incoming liquidity).
        The "right answer" isn't a fixed number — it's a <em>pair</em> of strategies that are
        mutually best responses.
      </p>
      <p>
        That's a Nash equilibrium. And our agents find it.
      </p>
      <p>
        Neither agent knows the other exists as an optimizer. Neither agent can see the other's
        policy or cost function. They're independently hill-climbing in a shared environment,
        and the environment shifts under them as the other agent adapts. Despite this, they
        converge to a stable pair of strategies where neither has an incentive to deviate — the
        textbook definition of Nash equilibrium.
      </p>
      <p>
        The convergence isn't always smooth. In some runs, we see brief oscillations where one
        agent cuts liquidity, causing the other to experience more delays, prompting <em>that</em>
        agent to increase its commitment, which then lets the first agent cut further. But these
        oscillations dampen, and the system settles.
      </p>

      <h3>What It Means</h3>
      <p>
        This result has implications beyond payment systems:
      </p>
      <ul>
        <li>
          <strong>LLMs can discover game-theoretic equilibria through repeated play.</strong> Without
          any explicit game theory in their training objective or prompts, these agents converge to
          Nash equilibria by independently optimizing against observed outcomes. The equilibrium
          emerges from the interaction, not from computation.
        </li>
        <li>
          <strong>Statistical evaluation matters.</strong> Our bootstrap paired comparison (50 samples,
          95% CI) prevents agents from chasing noise. Without it, agents in stochastic environments
          oscillate endlessly, accepting "improvements" that are just lucky draws. The statistical
          rigor is what makes convergence possible.
        </li>
        <li>
          <strong>The gap between stability and optimality is real.</strong> In our symmetric
          Experiment 3 (different from the stochastic Experiment 2 discussed here), agents converge
          to <em>stable but suboptimal</em> outcomes — one free-rides while the other overcommits.
          It's a Nash equilibrium, but both would be better off at the symmetric solution. Convergence
          doesn't mean the outcome is good.
        </li>
        <li>
          <strong>Implications for policy testing.</strong> If LLM agents can discover equilibria
          in simulated payment systems, regulators could use this approach to stress-test policy
          changes before deployment. What happens to bank behavior if you change the cost structure?
          The delay penalty? The deadline rules? Let the agents play it out and see where they land.
        </li>
      </ul>

      <h3>Try It Yourself</h3>
      <p>
        SimCash is built for exploration. You can run the convergence experiment yourself right here
        on this platform — configure a scenario, set the number of iterations, and watch the agents
        learn in real time. Start with the Experiment 2 preset (12-tick stochastic, bootstrap
        evaluation) and see how quickly the agents find the equilibrium.
      </p>
      <p>
        Or try breaking it: crank up the delay costs, make the payment distributions wildly
        asymmetric, or give one agent a much larger liquidity pool. The equilibrium shifts, and
        watching the agents adapt is half the fun.
      </p>
      <p>
        The code is open source on{' '}
        <a href="https://github.com/aerugo/SimCash" target="_blank" rel="noopener">GitHub</a>.
        We'd love to see what you discover.
      </p>
    </DocPage>
  );
}

function BlogCoordination() {
  return (
    <DocPage title="Designing Financial Stress Tests with SimCash" subtitle="How to model crisis scenarios, liquidity shocks, and central bank interventions in a simulated RTGS system" isBlog date="2026-02-17">
      <h3>Why Stress Testing Matters</h3>
      <p>
        In 2008, the payment systems that underpin global finance didn't break — but they came
        terrifyingly close. Lehman Brothers' default sent shockwaves through every major RTGS system.
        Banks that had comfortably recycled incoming payments to fund outgoing ones suddenly found
        themselves staring at empty queues. The liquidity that everyone counted on — other banks'
        payments flowing in — simply stopped.
      </p>
      <p>
        The lesson was clear: you can't test a payment system's resilience only on sunny days.
        Real-Time Gross Settlement systems process trillions of euros daily, and their stability
        depends on every participant maintaining adequate liquidity. When one major bank fails to
        deliver, the cascading effects can freeze the entire network. Stress testing isn't a
        regulatory checkbox — it's the only way to understand how your system behaves when the
        assumptions underlying normal operations stop being true.
      </p>
      <p>
        But traditional stress testing is expensive and slow. You need custom models, carefully
        calibrated parameters, weeks of engineering time. SimCash was built to change that.
      </p>

      <h3>How SimCash Models Crises</h3>
      <p>
        At its core, SimCash's scenario system lets you define <strong>what happens</strong> and
        <strong>when it happens</strong> — then hands the rest to the simulation engine. Scenarios
        are multi-phase narratives with configurable events at each stage:
      </p>
      <ul>
        <li><strong>Liquidity shocks:</strong> Suddenly reduce one or more banks' available liquidity
        at a specific tick — modeling an unexpected outflow, a collateral call, or a credit line revocation.</li>
        <li><strong>Payment surges:</strong> Inject a burst of high-value payments into the system,
        simulating end-of-day settlement rushes or margin calls during volatile markets.</li>
        <li><strong>Participant failures:</strong> Remove a bank from the system entirely, modeling
        a Lehman-style default where all expected incoming payments vanish.</li>
        <li><strong>Central bank interventions:</strong> Inject emergency liquidity at a specific
        tick — the lender-of-last-resort stepping in to prevent systemic collapse.</li>
      </ul>
      <p>
        Each scenario phase has a name, a duration (in ticks), and a set of events. You can chain
        phases to create complex narratives: "normal operations for 4 ticks, then a liquidity shock,
        then observe the cascade for 6 ticks, then the central bank intervenes." The engine handles
        the rest — payment processing, queue management, cost accounting, deadline tracking — all
        running at the same fidelity as a normal simulation.
      </p>

      <h3>Walking Through: The TARGET2 Crisis Scenario</h3>
      <p>
        SimCash ships with a built-in scenario called <strong>TARGET2 Crisis</strong>, modeled on
        the dynamics of the European Central Bank's RTGS system during a sovereign debt crisis.
        Here's what happens when you run it:
      </p>
      <p>
        <strong>Phase 1 — Normal Operations (Ticks 1-3):</strong> Three banks operate normally.
        Payments arrive via Poisson process, amounts are log-normally distributed. Banks settle
        payments as they come in, recycling incoming liquidity to fund outgoing obligations.
        Everything works smoothly. Costs are low.
      </p>
      <p>
        <strong>Phase 2 — The Shock (Tick 4):</strong> Bank C suffers a sudden liquidity drain —
        its available balance drops by 60%. This models a large unexpected outflow: a margin call,
        a deposit flight, a collateral haircut. Bank C's outgoing payments immediately start queuing.
      </p>
      <p>
        <strong>Phase 3 — The Cascade (Ticks 5-8):</strong> Here's where it gets interesting.
        Banks A and B were counting on incoming payments from Bank C to fund their own obligations.
        Those payments are now stuck in C's queue. A and B's own queues start growing. The delay
        costs compound: each tick a payment sits in queue, it accrues penalties. If deadlines pass,
        the failure costs are even steeper.
      </p>
      <p>
        <strong>Phase 4 — Intervention (Tick 9):</strong> The central bank injects emergency
        liquidity into Bank C. The queued payments start flowing again. But the damage is done —
        the cascade has already pushed costs far above normal levels across all participants.
      </p>
      <p>
        What should you watch for? The <strong>delay cost curve</strong> tells the story. In normal
        operations, delay costs are near zero. After the shock, they spike — first for Bank C,
        then for A and B with a 1-2 tick lag. The total system cost often triples or quadruples
        relative to the no-shock baseline. The spread between banks reveals who was most dependent
        on C's incoming payments.
      </p>

      <h3>AI Agents vs. Static Policies Under Stress</h3>
      <p>
        Here's what makes SimCash's stress testing genuinely novel: you can pit <strong>adaptive
        AI agents</strong> against <strong>static rule-based policies</strong> and watch how they
        respond to the same crisis.
      </p>
      <p>
        A static FIFO policy doesn't know a crisis is happening. It processes payments in order,
        commits the same liquidity fraction it always does, and watches helplessly as costs spike.
        A more sophisticated decision-tree policy might have crisis-response rules — "if queue
        depth exceeds X, delay low-priority payments" — but those rules were written before the
        crisis happened. They can't adapt to the specific shape of this particular shock.
      </p>
      <p>
        An LLM-powered agent, by contrast, gets a full performance report after each tick. It
        sees the queue building, the delay costs spiking, the pattern of which payments are failing.
        And it adjusts. In our experiments, AI agents facing the TARGET2 Crisis scenario typically
        respond within 2-3 rounds: they increase their liquidity commitment, shift to more
        aggressive release of queued payments, and accept higher liquidity costs to avoid the
        compounding delay penalties. The total crisis cost for AI-managed banks is consistently
        15-30% lower than for static-policy banks facing the same shock.
      </p>
      <p>
        This isn't magic — it's exactly what a skilled human cash manager would do. But the AI does
        it faster, more consistently, and without the panicked phone calls.
      </p>

      <h3>Building Your Own Stress Tests</h3>
      <p>
        The scenario editor in SimCash's web interface lets you design custom stress tests without
        writing code. You define phases visually — drag to set durations, click to add events,
        configure parameters with sliders:
      </p>
      <ul>
        <li><strong>Choose your topology:</strong> How many banks? What's the initial liquidity distribution?</li>
        <li><strong>Define the baseline:</strong> Set payment arrival rates, amount distributions,
        and the normal operating period.</li>
        <li><strong>Add the shock:</strong> Pick which bank gets hit, the severity (10% drain to 90%),
        and the timing.</li>
        <li><strong>Configure the response:</strong> Add a central bank intervention phase, or don't —
        and see what happens without a backstop.</li>
        <li><strong>Assign policies:</strong> Give each bank a different strategy — one AI-managed,
        one FIFO, one custom decision tree — and compare their crisis responses head-to-head.</li>
      </ul>
      <p>
        You can save scenarios, share them, and run them repeatedly with different random seeds to
        build statistical confidence. The bootstrap evaluation system applies here too: run 50
        seeds of the same crisis and you'll know whether one policy's crisis performance is genuinely
        better or just got lucky with payment timing.
      </p>

      <h3>What Researchers Can Learn</h3>
      <p>
        Stress testing in SimCash isn't just about finding the breaking point. It's about
        understanding the <strong>transmission mechanism</strong> — how a shock at one node propagates
        through the network, which relationships amplify it, and which policies contain it.
      </p>
      <p>
        Central bank researchers can use this to evaluate intervention timing: is it better to
        inject liquidity immediately, or wait to see if the market self-corrects? Banking
        supervisors can study concentration risk: what happens when the most-connected bank fails?
        And policy designers can test resilience requirements: how much committed liquidity does
        each bank need to survive a worst-case shock without central bank help?
      </p>
      <p>
        The answers aren't theoretical. They come from running thousands of simulated crises with
        realistic payment flows, realistic cost structures, and agents that behave like real
        decision-makers. That's the value of a sandbox: you can break things safely, learn from
        the wreckage, and build better systems before the next crisis arrives.
      </p>
    </DocPage>
  );
}

function BlogBootstrap() {
  return (
    <DocPage title="From FIFO to Nash: The Evolution of Payment Strategies" subtitle="How payment processing strategies evolved from simple queues to AI-discovered equilibria" isBlog date="2026-02-17">
      <h3>FIFO: The Reliable Baseline</h3>
      <p>
        First In, First Out. It's the simplest possible payment processing strategy: payments
        arrive, they go into a queue, and they're processed in order. No prioritization, no
        strategic timing, no adaptation. FIFO is what happens when you don't make a decision —
        and in many real RTGS systems, it's essentially what banks do by default.
      </p>
      <p>
        FIFO has real virtues. It's predictable — every participant knows exactly how the queue
        behaves. It's fair — no payment gets special treatment. It's easy to implement, easy to
        audit, and easy to reason about. For decades, this was good enough.
      </p>
      <p>
        But "good enough" isn't optimal. FIFO treats a €10 million time-critical CLS settlement
        the same as a €500 internal transfer. It doesn't account for incoming payments that might
        arrive in the next tick and provide the liquidity needed to clear the queue naturally. It
        can't distinguish between a temporary liquidity shortage (where delaying briefly would be
        costless) and a genuine funding gap (where delay compounds into failure). FIFO is a strategy
        that ignores all available information — and in a system where information is abundant,
        that's leaving money on the table.
      </p>

      <h3>The Strategy Space</h3>
      <p>
        SimCash's policy engine reveals just how much room there is beyond FIFO. At every decision
        point — each time a payment could be processed or a bank-level action could be taken — an
        agent chooses from <strong>16 distinct actions</strong>:
      </p>
      <ul>
        <li><strong>Payment actions:</strong> Release (process immediately), Delay (hold for later),
        Queue (add to back of queue), Prioritize (move to front), Split (partial release), and
        several conditional variants that depend on current state.</li>
        <li><strong>Bank actions:</strong> NoAction (do nothing), RequestLiquidity (ask the central
        bank for more), ReturnLiquidity (give back excess), AdjustReserves (rebalance), and others
        that manage the bank's overall position.</li>
      </ul>
      <p>
        Each decision is informed by over <strong>140 context fields</strong> — the complete state
        of the world as the agent sees it. Current balance, queue depth, queue value, time of day,
        payments pending, incoming payment history, liquidity ratio, cost accumulation rates,
        deadline proximity for each queued payment, counterparty reliability scores, and dozens more.
        This isn't a toy state space — it mirrors the information a real cash manager has on their
        screens.
      </p>
      <p>
        Strategies are expressed as <strong>decision trees</strong>: nested if-then-else structures
        that examine context fields and select actions. A tree might say: "If the queue value
        exceeds 50% of available balance AND the highest-priority payment's deadline is within 2
        ticks, then Release. Otherwise, if incoming payment velocity is above average, Delay.
        Otherwise, Queue." These trees can be shallow (3-4 decisions) or deep (dozens of branches),
        creating an enormous space of possible strategies.
      </p>

      <h3>When Does Sophistication Pay Off?</h3>
      <p>
        This is the question that surprised us most. You'd expect more complex policies to always
        outperform simpler ones — more information, more conditions, better decisions. But that's
        not what happens.
      </p>
      <p>
        In our experiments, the relationship between policy complexity and performance follows a
        curve. Very simple policies (FIFO, or a tree with 2-3 nodes) leave significant value on
        the table. They can't respond to the state of the system at all. But very complex policies
        (deep trees with 20+ branches) often <em>overfit</em> to specific payment patterns. They
        perform brilliantly on the scenarios they were designed for and terribly on everything else.
      </p>
      <p>
        The sweet spot turns out to be <strong>moderate complexity</strong>: trees with 5-10
        decision nodes that focus on the most informative context fields. Queue depth, liquidity
        ratio, time-of-day, and deadline proximity carry most of the signal. Adding branches for
        obscure context fields (third-derivative of incoming payment velocity, say) adds noise
        faster than it adds value.
      </p>
      <p>
        This mirrors a well-known result in machine learning — the bias-variance tradeoff — but
        seeing it play out in a financial simulation is striking. The best payment strategies
        aren't the cleverest. They're the ones that focus on the right signals and ignore the rest.
      </p>

      <h3>The Policy Library</h3>
      <p>
        SimCash ships with a curated library of pre-built strategies spanning the full spectrum
        from conservative to aggressive:
      </p>
      <ul>
        <li><strong>FIFO Baseline:</strong> Pure queue-order processing. The control group.</li>
        <li><strong>Cautious:</strong> Holds extra liquidity reserves, delays non-urgent payments,
        prioritizes avoiding deadline failures above all else. Low variance, moderate cost.</li>
        <li><strong>Balanced:</strong> Adapts liquidity commitment based on queue pressure. Releases
        payments when funded, delays when tight. The "sensible middle ground."</li>
        <li><strong>Aggressive:</strong> Commits minimal liquidity upfront, relies heavily on
        incoming payments for funding. High reward when it works, high penalty when it doesn't.</li>
        <li><strong>Deadline-Driven:</strong> Ignores queue order entirely, processes payments
        by deadline proximity. Minimizes failure costs at the expense of potentially higher delays.</li>
        <li><strong>Adaptive:</strong> Changes behavior based on the current phase of the day —
        conservative early (when incoming flows are uncertain), aggressive late (when remaining
        obligations are known).</li>
      </ul>
      <p>
        Each policy in the library has been tested across hundreds of random seeds and multiple
        scenarios. The documentation includes expected cost ranges, failure rates, and performance
        profiles so you know what you're getting before you deploy one in an experiment.
      </p>

      <h3>Building Custom Policies</h3>
      <p>
        The policy editor lets you construct decision trees visually. You start with a root node,
        add conditions (pick a context field, choose a comparator, set a threshold), and assign
        actions to the leaves. The editor validates your tree in real-time — it'll warn you about
        unreachable branches, missing edge cases, or conditions that are always true.
      </p>
      <p>
        You can also start from a library policy and modify it. Take the Balanced strategy, add a
        crisis-response branch ("if liquidity ratio drops below 20%, switch to aggressive release"),
        and you've got a custom policy that handles normal operations sensibly and responds to
        shocks without freezing up. Save it, name it, run it against the originals.
      </p>
      <p>
        For power users, policies can also be written directly in JSON — the same format the LLM
        agents produce. This means any strategy an AI discovers can be extracted, inspected, edited,
        and redeployed as a static policy. The boundary between human-designed and AI-discovered
        strategies is deliberately blurry.
      </p>

      <h3>How AI Discovers Better Strategies</h3>
      <p>
        When an LLM agent optimizes a policy, it doesn't search the tree space randomly. It starts
        with a simple policy (often FIFO or a basic tree), runs simulations, reads the performance
        reports, and makes targeted modifications. The reasoning looks remarkably like what a human
        expert would do:
      </p>
      <p>
        <em>"Delay costs are 3x liquidity costs. I'm over-committing liquidity. Let me reduce
        initial_liquidity_fraction from 0.65 to 0.50 and add a condition: if queue depth exceeds 5,
        release the highest-value payment regardless of order."</em>
      </p>
      <p>
        Each proposed change is validated by bootstrap paired comparison — the new policy must
        outperform the old one across 50 resampled scenarios with 95% confidence. This prevents
        the agent from chasing noise. Over 15-20 rounds, the policy evolves from simple to
        moderately complex, accumulating the decision branches that actually improve performance
        and discarding the ones that don't survive statistical validation.
      </p>
      <p>
        The result is a policy that no human designed but that any human can read. Decision trees
        are inherently interpretable — you can trace every branch, understand every condition, and
        debate whether the logic makes sense. This is a crucial advantage over black-box approaches.
      </p>

      <h3>The Nash Equilibrium Question</h3>
      <p>
        The deepest question in multi-agent payment strategy isn't "what's the best policy?" —
        it's "what happens when everyone optimizes simultaneously?"
      </p>
      <p>
        In game theory, a <strong>Nash equilibrium</strong> is a set of strategies where no player
        can improve their outcome by changing their own strategy alone. In SimCash, this means a
        configuration where every bank's policy is the best response to every other bank's policy.
        Nobody wants to deviate.
      </p>
      <p>
        Our multi-agent experiments show that LLM agents do converge — but not always to the same
        equilibrium. In symmetric games (identical banks, identical payment flows), the agents
        typically find an equilibrium within 10-15 rounds. But the equilibrium they find depends
        on the path they take to get there. Early aggressive moves by one agent can push the system
        toward an asymmetric equilibrium where one bank free-rides on the other's liquidity
        provision.
      </p>
      <p>
        This is the Prisoner's Dilemma playing out in real-time payment systems. The cooperative
        outcome (both banks commit moderate liquidity, both benefit from smooth settlement) is
        Pareto-optimal but unstable. The Nash equilibrium (one bank commits high liquidity, the
        other free-rides) is stable but inefficient. Both agents know this. Neither can fix it
        unilaterally.
      </p>
      <p>
        Understanding when agents converge, what they converge to, and whether the equilibrium is
        socially efficient — these are the questions that connect SimCash to decades of game theory
        research. And now, instead of solving them on a whiteboard, you can watch them unfold in a
        simulated payment system with realistic costs, realistic constraints, and agents that reason
        about their decisions in plain English.
      </p>
      <p>
        The journey from FIFO to Nash isn't just about better payment processing. It's about
        understanding the fundamental tension in any shared financial infrastructure: individual
        optimization vs. collective welfare. SimCash makes that tension visible, measurable, and
        explorable.
      </p>
    </DocPage>
  );
}

/* ─── Reference ─── */

function References() {
  return (
    <DocPage title="References & Reading" subtitle="Papers, documentation, and further resources">
      <h3>Primary References</h3>
      <ul className="space-y-3">
        <li>
          <strong>Castro et al. (2025)</strong>.{' '}
          <em>"AI agents for cash management in payment systems."</em>{' '}
          BIS Working Paper No. 1310.{' '}
          <a href="https://www.bis.org/publ/work1310.pdf" target="_blank" rel="noopener" className="text-sky-400 hover:underline">
            PDF ↗
          </a>
          <p className="text-sm text-slate-500 mt-1">
            The foundational paper. Tests whether gen AI can perform intraday liquidity management
            in a wholesale payment system. SimCash replicates and extends their experiments.
          </p>
        </li>
        <li>
          <strong>Korinek, A. (2025)</strong>.{' '}
          <em>"AI Agents for Economic Research."</em>{' '}
          August 2025 update to <em>"Generative AI for Economic Research"</em> (JEL, 2023).{' '}
          <a href="https://www.aeaweb.org/content/file?id=23290" target="_blank" rel="noopener" className="text-sky-400 hover:underline">
            PDF ↗
          </a>
          <p className="text-sm text-slate-500 mt-1">
            Demystifies AI agents for economists — covering autonomous LLM systems with planning, tool use,
            and multi-step task execution. Shows how to build research agents using "vibe coding" and
            frameworks like LangGraph. Directly relevant to SimCash's approach of using LLM agents as
            autonomous policy optimizers.
          </p>
        </li>
      </ul>

      <h3>Background Reading</h3>
      <ul className="space-y-3">
        <li>
          <strong>ECB TARGET Services</strong>.{' '}
          <em>T2 (formerly TARGET2) RTGS System.</em>
          <p className="text-sm text-slate-500 mt-1">
            The real-world system that SimCash's settlement mechanics are modeled on.
            T2 is the Eurosystem's RTGS system for large-value euro payments.
            SimCash implements T2-compliant liquidity-saving mechanisms.
          </p>
        </li>
        <li>
          <strong>Liquidity-Saving Mechanisms (LSM)</strong>.
          <p className="text-sm text-slate-500 mt-1">
            Bilateral offsetting and multilateral cycle detection — the algorithms that let
            banks settle with less liquidity by netting mutual obligations.
          </p>
        </li>
      </ul>

      <h3>SimCash Documentation</h3>
      <ul className="space-y-2">
        <li>
          <a href="https://github.com/aerugo/SimCash" target="_blank" rel="noopener" className="text-sky-400 hover:underline">
            GitHub Repository ↗
          </a>{' '}
          — Source code, README, and development guidelines
        </li>
        <li>
          <a href="https://github.com/aerugo/SimCash/tree/main/docs/reference" target="_blank" rel="noopener" className="text-sky-400 hover:underline">
            Reference Documentation ↗
          </a>{' '}
          — 80+ pages covering CLI, experiments, AI cash management, policy DSL
        </li>
        <li>
          <a href="https://github.com/aerugo/SimCash/blob/main/docs/game_concept_doc.md" target="_blank" rel="noopener" className="text-sky-400 hover:underline">
            Game Concept Document ↗
          </a>{' '}
          — The "why" behind the simulation
        </li>
      </ul>

      <h3>Key Concepts Glossary</h3>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-700">
            <th className="text-left py-2 text-slate-300">Term</th>
            <th className="text-left py-2 text-slate-300">Definition</th>
          </tr>
        </thead>
        <tbody className="text-slate-400">
          <tr className="border-b border-slate-800"><td className="py-2 pr-4 font-mono text-sky-400">RTGS</td><td>Real-Time Gross Settlement — each payment settles individually in real time</td></tr>
          <tr className="border-b border-slate-800"><td className="py-2 pr-4 font-mono text-sky-400">LSM</td><td>Liquidity-Saving Mechanism — bilateral/multilateral netting to reduce liquidity needs</td></tr>
          <tr className="border-b border-slate-800"><td className="py-2 pr-4 font-mono text-sky-400">initial_liquidity_fraction</td><td>The key parameter: what fraction of the pool to commit (0.0–1.0)</td></tr>
          <tr className="border-b border-slate-800"><td className="py-2 pr-4 font-mono text-sky-400">Bootstrap</td><td>Statistical resampling to compare policies across multiple samples</td></tr>
          <tr className="border-b border-slate-800"><td className="py-2 pr-4 font-mono text-sky-400">Paired comparison</td><td>Evaluating both policies on identical samples to cancel noise</td></tr>
          <tr className="border-b border-slate-800"><td className="py-2 pr-4 font-mono text-sky-400">Nash equilibrium</td><td>Strategy profile where no player gains from unilateral deviation</td></tr>
          <tr className="border-b border-slate-800"><td className="py-2 pr-4 font-mono text-sky-400">Pareto efficiency</td><td>No player can be made better off without making another worse off</td></tr>
          <tr><td className="py-2 pr-4 font-mono text-sky-400">Free-riding</td><td>Exploiting others' liquidity commitment while minimizing your own</td></tr>
        </tbody>
      </table>
    </DocPage>
  );
}

/* ─── Shared Components ─── */

function DocPage({ title, subtitle, isBlog, date, children }: {
  title: string;
  subtitle: string;
  isBlog?: boolean;
  date?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      {isBlog && (
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs bg-violet-500/20 text-violet-400 px-2 py-0.5 rounded-full">Blog</span>
          {date && <span className="text-xs text-slate-500">{date}</span>}
        </div>
      )}
      <h1 className="text-2xl font-bold text-slate-100 mb-1">{title}</h1>
      <p className="text-slate-400 mb-6">{subtitle}</p>
      <div className="space-y-4 text-slate-300 leading-relaxed [&_h3]:text-lg [&_h3]:font-semibold [&_h3]:text-slate-200 [&_h3]:mt-8 [&_h3]:mb-3 [&_h4]:text-base [&_h4]:font-medium [&_h4]:text-slate-300 [&_h4]:mt-6 [&_h4]:mb-2 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:space-y-1 [&_ol]:list-decimal [&_ol]:pl-5 [&_ol]:space-y-1 [&_li]:text-slate-300 [&_a]:text-sky-400 [&_a]:hover:underline [&_code]:text-sky-400 [&_code]:bg-slate-800 [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded [&_code]:text-xs [&_table]:border-collapse [&_table]:w-full [&_td]:py-1.5 [&_td]:pr-4 [&_td]:text-sm">
        {children}
      </div>
    </div>
  );
}

function Callout({ type, children }: { type: 'info' | 'important' | 'insight'; children: React.ReactNode }) {
  const styles = {
    info: 'border-sky-500/30 bg-sky-500/5',
    important: 'border-amber-500/30 bg-amber-500/5',
    insight: 'border-violet-500/30 bg-violet-500/5',
  };
  const icons = { info: 'ℹ️', important: '⚠️', insight: '💡' };

  return (
    <div className={`border-l-4 rounded-r-lg p-4 my-4 text-sm ${styles[type]}`}>
      <span className="mr-2">{icons[type]}</span>
      {children}
    </div>
  );
}

function CodeBlock({ children }: { children: string }) {
  return (
    <pre className="bg-slate-900 border border-slate-700 rounded-lg p-4 text-xs font-mono text-slate-300 overflow-x-auto my-4 whitespace-pre">
      {children}
    </pre>
  );
}
