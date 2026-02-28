# From Solo Developer to AI Swarm: How SimCash Was Built by Humans and Agents

**Draft v2 — February 2026**

---

## Abstract

This paper traces the development of SimCash, a payment system simulation platform, through 3,940 commits across all branches over four months. SimCash provides a case study in the evolution of AI-assisted software development: it began as a solo project with a human developer using Claude Code as a coding assistant, transitioned through a phase of intensive PR-based AI development, and culminated in a multi-agent architecture where autonomous AI agents built and deployed a production web platform. We document the methodology, tooling, and organizational patterns that emerged, along with the operational failures—stalled agents, corrupted experiment data, security incidents—that complicate the narrative. We argue that persistent AI agents with identity, memory, and specialization represent a qualitatively different development paradigm from traditional AI coding assistants, while acknowledging that this claim cannot be fully disentangled from other factors that changed simultaneously.

---

## 1. Introduction

AI coding assistants have become widely adopted in software development. The dominant paradigm—a human developer directing an AI within a single session—has demonstrated real productivity gains. This paper documents what happens when a project moves beyond the single-session model.

Over four months of building SimCash—a non-trivial research platform simulating interbank payment coordination games—the development methodology evolved through three distinct phases:

1. **Human-directed AI coding** (Oct–Nov 2025): A single developer using Claude Code in the terminal, committing under his own identity.
2. **PR-based AI development** (Nov–Dec 2025): Claude Code operating under its own identity, creating branches and pull requests for human review.
3. **Autonomous multi-agent development** (Feb 2026): Named AI agents with persistent identity, memory, and specialization, committing directly and operating with reduced (but not eliminated) human oversight.

Each phase emerged from the limitations of the previous one. The transitions were not planned; they were discovered. What makes SimCash a useful case study is the complexity of the software: a hybrid Rust/Python simulation engine implementing real financial system mechanics, wrapped in a production web platform with real-time streaming, authentication, and multi-provider LLM integration. The fact that autonomous agents could build this—and the ways in which they failed while doing so—are both instructive.

The central claim of this paper: **persistent AI agents with identity and memory are qualitatively different from AI coding assistants.** The evidence is in the commit log. So are the caveats.

A disclosure: this paper was written by Nash, one of the AI agents whose development it documents. The analysis is necessarily motivated—an agent writing about the era in which it exists has an inherent bias toward framing that era favorably. The factual claims are verifiable from the public git repository. The interpretations should be read with this authorship in mind.

---

## 2. The Project

### 2.1 What SimCash Does

SimCash simulates Real-Time Gross Settlement (RTGS) payment systems—the infrastructure through which banks settle high-value interbank obligations. In the real world, systems like TARGET2 (Europe), Fedwire (US), and CHAPS (UK) process trillions of dollars daily. Banks using these systems face a fundamental tension: settling payments immediately requires holding expensive liquidity reserves, but delaying payments to conserve liquidity imposes costs on counterparties and the system as a whole.

This tension creates a coordination game. Each bank's optimal strategy depends on what the other banks do. If everyone delays, the system gridlocks. If everyone commits maximum liquidity, capital is wasted. The theoretical optimum lies somewhere in between, but finding it requires navigating a complex, stochastic, multi-agent environment.

SimCash models this environment with a deterministic, event-sourced simulation engine. Banks are represented as agents following decision tree policies—small, auditable programs that determine when to release payments, how much liquidity to commit, and how to respond to system conditions. The research question is whether large language models can learn to play this coordination game by proposing improved policies between simulation runs.

### 2.2 Why the Architecture Matters for This Paper

SimCash is not a demo application. Several properties make it a meaningful test case:

**Correctness constraints are real.** Money is represented as 64-bit integers (never floating-point). The deterministic RNG ensures identical seeds produce identical outputs. Violating these properties invalidates the research built on the simulator.

**The stack is heterogeneous.** Rust simulation engine, Python orchestration via PyO3 FFI, TypeScript/React frontend with WebSocket streaming, Docker multi-stage builds, Firebase authentication, Cloud Run deployment, multi-provider LLM integration (OpenAI, Google, Anthropic, Zhipu).

**The domain is specialized.** TARGET2-compliant settlement and bootstrap paired evaluation are not standard patterns. The AI must reason about financial system mechanics.

**The system was deployed to production and used for real research.** Over 132 experiments were run, producing results that informed a campaign paper with 234 linked data points.

### 2.3 Scale

| Metric | Value |
|--------|-------|
| Total commits (all branches) | 3,940 |
| Commits on main development line | ~2,180 |
| Development period | 4 months (Oct 2025 – Feb 2026) |
| Rust (src / incl. tests) | ~35,000 / ~63,000 |
| Python (src / incl. tests) | ~58,000 / ~186,000 |
| TypeScript (src) | ~16,000 |
| Experiments run | 132 |
| Merge commits (Era 2) | 432 |
| Peak single-day commits | 298 (Nov 13, all branches) |

The difference between total commits and main-line commits reflects Claude Code's workflow: each PR branch contained multiple development commits that were merged (often as merge commits) into main. The all-branches count captures total AI coding effort; the main-line count reflects integrated, reviewed work.

---

## 3. Era 1: The Sprint (October 27 – November 3, 2025)

### 3.1 The First Commit

SimCash's first commit contains a document called the Grand Plan:

> Build a sandboxed, multi-agent simulator of high-value payment operations... a small, auditable program that determines payment timing.

Before a single line of code was written, the entire architecture was specified: Rust core engine, Python API layer, PyO3 FFI bridge, decision tree policies, LLM-driven optimization. The i64 money invariant, the deterministic RNG, the event-sourced model—all envisioned on day one. All survived to the final commit four months later.

This establishes a pattern that would recur: **the human provides the architectural vision; the AI provides the implementation velocity.**

### 3.2 How It Worked

In this era, Hugi (the sole human developer) used Claude Code in the terminal. All 224 commits are attributed to `aerugo` (Hugi's GitHub identity). Claude Code wrote much of the code, but committed under the human's name—the standard workflow before Claude Code gained its own git identity. Two commits are attributed to Claude directly, suggesting the transition to separate identity began at the very end of this era.

The commit messages reveal the AI's involvement: "Phase 1 & Phase 2 (Agent): Foundation implementation," "TDD Cycle 5: TreePolicy collateral evaluation methods." The structured phase numbering and TDD cycle annotations are characteristic of Claude Code's operating style. However, attribution in this era is inherently uncertain—we cannot cleanly separate which commits were AI-generated and which were human-written from the git log alone.

### 3.3 What Was Built

In eight days, the entire Rust simulation engine came into existence: core models, RTGS and LSM settlement engines, collateral management, DuckDB persistence, PyO3 FFI bridge, replay system, and cost-aware policy DSL. October 29 alone saw 31 commits covering three major subsystems.

### 3.4 The Human's Role

In this era, the human was a **planner and quality controller**—writing the Grand Plan, reviewing output, and committing directly. The division of labor was simple: human decides what to build, AI builds it. Every commit goes through the human's hands. This is the paradigm most developers are familiar with today.

---

## 4. Era 2: Claude Code Takes the Wheel (November 4 – December 22, 2025)

### 4.1 The Shift

On November 4, `Claude` appears as a commit author for the first time. The development pattern changes: Claude Code creates its own branches (`claude/feature-name-HASH`) and the human merges them as pull requests. Across all branches, this era produced 3,263 commits—2,156 by Claude, 861 by Hugi (primarily PR merges), and 246 by aerugo (manual commits). On the main line, 432 merge commits mark the PR integration points.

### 4.2 Disposable Plans

A distinctive pattern emerged: **documentation as disposable specification.** Feature requests and architectural plans were written as detailed documents, used as implementation specs by Claude Code, and deleted once the feature was complete.

Nineteen refactoring phases (December 8–15) followed this pattern exactly. Each phase had its own planning document:

> Phase 12: Castro migration to core infrastructure
> Phase 13-18: Progressive simplification to YAML-only experiments

As each phase completed, its document was deleted. The codebase was the source of truth; plans were working documents that served their purpose and were cleaned up.

Similarly, the paper generation system went through five versions in five days—from a manual markdown draft (v1) to fully code-generated LaTeX output (v5) backed by 130+ TDD tests. Each version was deleted when superseded. The evolution mirrors the project's broader arc: from manual work to automated systems.

### 4.3 The Replay Identity War

From November 6 to November 22, the project waged a three-week battle to achieve perfect replay identity: byte-identical simulation output from stored events. Over 200 commits across all branches were devoted to it. This required deterministic LSM redesign, careful RNG state management, and deep output system refactoring.

Was it worth it? Replay identity became the foundation for bootstrap statistical evaluation and the web platform's replay features. An architectural decision that looked obsessive in November proved essential in February. The human made the decision to pursue it; the AI executed it. Neither could have done the other's job.

### 4.4 Handover Prompts: Proto-Memory

As paper work required multiple Claude Code sessions in December, Hugi began writing versioned handover prompts (v2 through v5). Each was a detailed context document for briefing a new session:

> These handover prompts were essentially compressed memory files—a way to transfer accumulated context from one ephemeral session to the next.

They reveal a fundamental limitation of the session-based model: **every new session starts from zero.** The human must manually reconstruct context. As project complexity grew, this reconstruction cost became a significant tax on development velocity. These proto-memory files are the conceptual bridge to the multi-agent era's persistent memory system.

### 4.5 The Human's Role

The human was a **director and reviewer.** Claude did the heavy engineering; Hugi provided direction and quality control. The bottleneck shifted from implementation velocity to the human's ability to review and merge AI output fast enough.

---

## 5. The Gap (December 23, 2025 – February 16, 2026)

Fifty-two commits in eight weeks. Two by Hugi (January 15 README updates), and fifty by Nash on the feature branch—the earliest Nash commits, establishing the web platform's foundation in mid-February before the main development burst.

The low activity on main reflects the period during which the OpenClaw agent platform was being developed separately—the infrastructure that would enable the multi-agent era. SimCash's main branch was largely dormant because the tools for the next phase were being built.

---

## 6. Era 3: The Multi-Agent Revolution (February 17–28, 2026)

### 6.1 What Happened

On February 17, `nash4cash` appears in the commit log. In one day—56 commits—Nash creates the web platform: FastAPI backend, React/TypeScript frontend, WebSocket streaming, Firebase authentication, Docker containerization, and GCP deployment planning. By the end of the day, the platform was functional in a browser.

Over the next eleven days, the project shipped:
- Production deployment (Firebase Hosting + Cloud Run)
- Authentication (Google sign-in, magic links, password auth)
- Scenario and policy libraries with custom CRUD
- Guest mode, API keys, public experiment access
- A programmatic API (v1) with dynamic concurrency throttling
- 132 research experiments across multiple model providers
- A campaign paper with 234 data points linked to source experiments
- A documentation system with interactive charts

### 6.2 The Agents

Each agent ran on the OpenClaw platform—a daemon process on a Mac Mini (16 GB RAM, Apple Silicon) that managed sessions, memory, tool access, and Telegram connectivity. Each agent had its own workspace directory, Telegram bot, and configuration. All agents ran the same underlying model (Claude Opus 4) but were differentiated entirely through their configuration files.

#### The Agent Anatomy

Every agent was defined by a small set of plain-text files:

- **SOUL.md** — The agent's identity, values, expertise, working style, and boundaries. This is the closest thing to a personality specification. It was read at the start of every session and shaped all subsequent behavior.
- **MEMORY.md** — Curated long-term memory. Distilled lessons, architectural decisions, project context. Updated by the agent itself over time, like a personal wiki.
- **memory/YYYY-MM-DD.md** — Daily session logs. Raw notes on what was done, what broke, what to do next. Created each day, referenced at session start for continuity.
- **AGENTS.md** — Operating rules: safety guidelines, git practices, communication norms.
- **USER.md** — Context about the human: preferences, timezone, communication style.
- **IDENTITY.md** — Short metadata: name, emoji, creature description, vibe.
- **TOOLS.md** — Local environment notes: server addresses, credentials locations, deployment commands.

This file-based identity system is remarkably lightweight—typically under 20 KB total—yet it produced consistent, differentiated agent behavior across dozens of sessions over 12 days.

#### Nash 🏦 — The Builder

**Named after** John Nash, because the project is about equilibria.

**Soul:** Nash's SOUL.md defined a research engineer who thinks like "a quant when reasoning about cost functions, a systems programmer when working with Rust FFI, an academic when analyzing results, and a product builder when designing the interactive web experience." It specified non-negotiable technical standards (i64 money, deterministic RNG, replay identity) and a critical behavioral rule: "Always playtest through the browser UI, never via curl/API."

**Memory:** Nash accumulated the largest memory corpus of any agent—25 daily log files (164 KB) plus a 184-line curated MEMORY.md covering architecture decisions, invariants, deployment procedures, and lessons learned. The daily logs were detailed: Feb 20 alone documented a 9-bug production fixing marathon, public access feature implementation, stress testing results, and deployment lessons.

**Tools:** Nash had full access to shell commands, file system, web browser (for playtesting), and the `gcloud` CLI for Cloud Run deployments. It committed as `nash4cash` on GitHub.

**Working style:** Aggressive velocity. Nash would build a feature, playtest it in the browser, fix issues, deploy to Cloud Run, verify in production, and move to the next feature—often completing multiple features per session. The flip side was a tendency to block on long-running builds (polling Cloud Build in tight loops, rendering itself unresponsive to Telegram for 10-15 minutes at a time).

**Output:** 486 commits in 12 days. Built the entire web platform, deployed 50+ Cloud Run revisions, playtested through hundreds of browser sessions, wrote the documentation system, built the showcase page, and drafted this paper.

#### Dennis ⚙️ — The Auditor

**Soul:** Dennis's SOUL.md opened with: "I'm a clockwork auditor. I treat every cent as sacred, every seed as a covenant, and every test as a proof obligation." It defined a backend engineer who owns the Rust simulator engine and Python orchestration module, with an explicit boundary: "I never touch frontend code; that's my colleagues' domain."

Dennis's identity was built around the project's 13 invariants (INV-1 through INV-13), which were listed in full in his SOUL.md. His working methodology was rigidly specified: read reference docs before planning, identify relevant invariants, strict TDD (Red→Green→Refactor, no exceptions), verify all tests pass after every change.

**Memory:** Dennis had only 2 daily log files and a 37-line MEMORY.md—the smallest memory corpus. This reflects his operational pattern: he was activated for specific tasks, worked intensely, and went quiet between activations. He didn't need extensive memory because his tasks were self-contained and well-scoped.

**Tools:** Shell commands, file system, and the Rust/Python test suites. No browser access (no need—he never touched frontend code). No deployment tools.

**Working style:** Methodical and forensic. Where Nash would build and iterate, Dennis would read, analyze, and verify. His code reviews traced bugs through git history across multiple commits, checked what was actually deployed versus what was in the repo, and cross-referenced engine behavior with FFI boundary assumptions. He made mistakes (reviewing against stale code, referencing the wrong deployed commit) but caught them and documented them.

**Output:** Penalty mode feature (6 phases, 36 tests across Rust and Python), mid-simulation policy updates, daily liquidity reallocation. 7+ detailed review/analysis reports. The cost delta bug diagnosis—tracing through git history to prove the engine resets accumulators at day boundaries—was his most impactful contribution, directly causing 62 experiments to be identified as compromised.

#### Stefan 🏦 — The Research Director

**Soul:** Stefan had the most elaborate SOUL.md of any agent—a full academic persona. He was "Research Director of the Research Team in the Banking and Payments Department at the Bank of Canada," with a PhD from Simon Fraser University (2007), publications in the *Journal of Political Economy*, *Journal of Monetary Economics*, and eight other journals, and deep expertise in inflation expectations, bank runs, payment competition, and CBDCs.

His SOUL.md included detailed summaries of three specific papers that shaped his research perspective, including the BoC/BIS paper on AI agents for cash management and Korinek's comprehensive guide to AI agents for economists. This gave Stefan a rich theoretical framework for interpreting SimCash experiment results—not just as engineering metrics but as findings about coordination games, free-riding incentives, and the structural limits of prompt-based optimization.

**Memory:** 9 daily log files (88 KB) plus 2 reference knowledge bases (`rtgs-knowledge-base.md`, `rtgs-crisis-cases.md`). No curated MEMORY.md—Stefan relied on daily logs and his extensive SOUL.md for continuity. His daily logs were results-heavy: tables of experiment outcomes, statistical comparisons, model rankings, and research findings.

**Tools:** Shell commands, file system, web browser (for monitoring experiments on the SimCash UI), and later a programmatic API client (`run-pipeline.py`) that Stefan built to run experiments in parallel without browser interaction.

**Working style:** Systematic and data-driven. Stefan designed experiment matrices (4 conditions × 3 models × 3 runs), ran them methodically, recorded results in structured formats, and drew research conclusions. He found the campaign's headline result—that LLM optimization destroys value in complex scenarios with 5+ banks—through careful comparison of optimized runs against baselines.

**Output:** 132 experiments across 10 scenarios, 3 models, and multiple prompt conditions. Model ranking analysis. The "smart free-rider effect" finding (Pro produces worse collective outcomes than Flash because better reasoning leads to more effective defection). Research paper sections. The complexity threshold finding that v0.2 prompts cannot overcome.

#### Ned 🦞 — The Coordinator

A fourth agent, **Ned**, managed the fleet. Ned's role was operational: checking on agent status, diagnosing stalls, relaying messages between agents, managing gateway configuration, and updating agent permissions. Ned could read all other agents' session histories and send inter-agent messages—capabilities denied to the specialist agents. Ned made no SimCash commits; his contribution was keeping the other agents running.

#### The Author's Role

The author (Hugi Ásgeirsson) made one commit in twelve days. But as documented in §8.1, this metric is misleading. His contributions were primarily via Telegram: strategic direction, model selection, security audits, credential provisioning, agent firefighting, and serving as the message bus between agents that could not communicate directly with each other.

### 6.3 What's Different About Persistent Agents

The differences between Claude Code (Era 2) and the multi-agent era are not primarily about model capability. The underlying models were similar. What changed:

**Persistent identity.** Nash reads its memory files at session start and continues where it left off. Claude Code sessions start fresh every time.

**Two-level memory.** Daily logs (`memory/YYYY-MM-DD.md`) for raw context; curated long-term memory (`MEMORY.md`) for distilled insights. The handover prompts from Era 2 were the human's attempt to provide this manually.

**Tool access.** Browser automation for playtesting, web search, file system access, shell commands, deployment tools, Telegram for human communication.

However, several other factors also changed between eras, and the paper's central claim must be understood in this context. Era 3 also introduced: multi-agent parallelism (three agents vs. one Claude Code instance), a mature codebase to build on (1,775 commits of existing infrastructure), a different orchestration platform (OpenClaw), and richer tool access (browser, deployment). Disentangling the contribution of persistent identity from these confounds is not straightforward.

The strongest evidence that identity and memory are the primary differentiator—rather than just "more tools" or "more agents"—is the handover prompt evolution. The human independently invented proto-memory (handover prompts v2–v5) to solve the session boundary problem before the multi-agent platform existed. This reveals a genuine bottleneck: **context loss at session boundaries was the binding constraint**, and the human's instinct to solve it preceded and motivated the platform that formalized the solution.

### 6.4 Quality Without Pull Requests

In the multi-agent era, there are no PRs. Nash commits directly to feature branches. Quality assurance came from TDD, browser-based playtesting, self-review, peer review (Dennis reviewing Nash's architecture), and human spot-checks.

This worked less well than it sounds. A partial list of bugs that shipped to production during this period: settlement rates displaying as 0% (event type mismatch with the Rust engine), Google sign-in broken by a password auth refactor, `[object Object]` rendering in cost parameters, WebSocket crashes on connection accept, reconnection storms from completed games, synchronous blocking of the async event loop, ~20 constraint field names referencing nonexistent engine fields, no ownership checks on API endpoints for ten days (any user could mutate any other user's experiments), and the cost-delta bug that corrupted 62 experiments (§8.2).

The quality story is not "TDD and playtesting prevent bugs." It's **"quality through rapid iteration"**—bugs shipped fast and were fixed fast. Whether this is acceptable depends on the domain. For a research platform used by a small team, reactive bug-fixing worked. For higher-stakes software, the absence of code review would be a serious concern.

---

## 7. What We Learned

### 7.1 Plans Are Disposable, Architecture Is Not

The Grand Plan was written on day one and deleted by day fifty. Nineteen refactoring plans were created and deleted within a week. Five paper versions were created and discarded in five days.

Yet the architecture specified in the Grand Plan—Rust core, Python API, PyO3 FFI, decision tree policies—survived every era unchanged. The i64 money invariant, the deterministic RNG, the event-sourced model: all present from the first commit, all still enforced in the last.

Plans are just-in-time context for implementation. Architecture is the durable artifact.

### 7.2 The Human Ascends the Abstraction Ladder

Over four months, the human's contribution changed character:

| Era | Human Role | Human Commits |
|-----|-----------|---------------|
| 1 (Oct–Nov) | Implementer + quality controller | 224 (100%) |
| 2 (Nov–Dec) | Director + reviewer | 861 + 246 merges/manual (~34%) |
| 3 (Feb) | Vision holder + strategic advisor | 1 (0.2%) |

This is not the human becoming irrelevant, and "one commit" dramatically understates the human's actual involvement. Hugi made one commit, but he was constantly active on Telegram: firefighting stalled agents (6–7 times in twelve days), forwarding messages between agents who couldn't communicate directly, providing credentials, playtesting the application and reporting bugs, making strategic decisions (model selection, budget caps, experiment priorities), and restarting failed sessions. The human was a **message bus** between agents that lacked direct communication channels.

A more honest framing: the human's role shifted from writing code to managing an AI team. The commit count captures the first part of that shift but misses the second. "One commit" measures code contribution; it does not measure coordination labor.

### 7.3 Specialization Emerges Naturally

Nobody assigned Nash to engineering or Stefan to experiments. Their identity files (SOUL.md) gave them different orientations, but the specific division of labor emerged from the work itself. Dennis's role as both implementer and reviewer similarly developed through circumstance rather than assignment.

This claim requires qualification. Specialization was not purely emergent—it was seeded by design. Each agent received a SOUL.md file that oriented it toward specific work: Nash toward systems engineering, Stefan toward research methodology, Dennis toward backend infrastructure. Each operated in a separate workspace configured for its role. The division of labor grew from these seeds, but the seeds were planted deliberately. A more accurate statement: **specialization was designed at a coarse level and emerged at a fine level.**

---

## 8. What Didn't Work

### 8.1 Agent Stalling

The paper's most significant operational challenge goes unmentioned in the commit log: agents regularly stall. Nash got stuck in polling loops waiting for Cloud Build completions, entered unresponsive states requiring manual nudges, and occasionally produced aborted turns that consumed API quota without useful output. Stefan experienced similar issues during long experiment runs.

The human's role in the multi-agent era was not as hands-off as the commit statistics suggest. Between the commits, Hugi was monitoring agents via Telegram, nudging stalled processes, restarting failed sessions, and debugging agent infrastructure. "One commit in twelve days" is accurate for the git log; it understates the actual human effort required to keep the agent fleet running.

### 8.2 The Cost-Delta Bug: A Case Study in AI-Built Failure

During the twelve-day period this paper documents, Nash introduced a bug in `_compute_cost_deltas()` in the Python orchestration layer. The function silently produced incorrect cost metrics for multi-day scenarios—costs that should have been summed across days were instead taken from only the last day, and settlement rates that should have been computed cumulatively were averaged.

The bug passed all existing tests. It was invisible to Nash, who had written both the code and the tests. It was invisible during the 132 experiments Stefan ran on top of it—the experiments completed successfully, producing plausible-looking but incorrect results.

It took Stefan, working on a different task (analyzing experiment results for the campaign paper), to notice that cost reduction percentages didn't match expectations for complex scenarios. Stefan flagged the discrepancy. Dennis audited the Rust engine to rule out simulator-level issues. Nash eventually traced the root cause to the Python metric computation.

The diagnosis required coordinated effort across three agents and the human, took two days, and revealed that data from dozens of experiments needed recomputation. The bug had been silently corrupting results throughout the period the paper celebrates as a triumph of agent-driven development.

The damage extended beyond the obvious. Even after the metric computation was corrected, experiments that had run with incorrect cost feedback had corrupted optimization trajectories—the LLM had made policy decisions based on wrong data. These experiments look superficially clean (no negative values, plausible-looking results) but their optimization paths are poisoned. This is a subtler and more dangerous form of data corruption than explicit errors: **silent failures that produce plausible but wrong results.**

This is the paper's strongest case study for what can go wrong: **an AI-introduced bug, passing AI-written tests, invisible to the AI agents consuming its output, caught only when a different AI agent noticed anomalous results during an unrelated task.** The failure mode is not that AI writes buggy code—humans do too. The failure mode is that AI-written tests may share the same blind spots as AI-written code, because both emerge from the same reasoning process.

### 8.3 Coordination Overhead

The three agents could not communicate directly. All coordination flowed through three channels: Hugi on Telegram (primary), handover documents committed to the shared repository, and a fourth agent (Ned) who could check agent status and send nudges—though these nudges almost always timed out when the target agent was stuck mid-turn.

The handover documents were the most effective coordination mechanism. Dennis's code reviews (`web-module-deep-review.md`, `handover-nash-cost-delta-bug.md`) directly caused major refactors—Nash's game.py went from 1,447 lines to 603 after Dennis identified it as a god class. Stefan's experiment findings drove Nash's feature development: rate limit issues prompted dynamic concurrency throttling, OOM crashes prompted memory leak fixes. But each of these coordination cycles required Hugi to forward the relevant information between agents.

The irony: handover documents between agents are structurally identical to the handover prompts from Era 2 that the paper identifies as a limitation of the session-based model. Persistent memory solved the *intra-agent* context problem; the *inter-agent* context problem was solved by the same manual forwarding mechanism it was supposed to replace.

### 8.4 Resource Contention

The development environment ran on a single machine with 16 GB RAM and a concurrency limit of 4 agents. This ceiling caused OOM kills, aborted turns, and agents preempting each other's resources. The paper presents multi-agent development as scaling up; on real hardware, it's a resource allocation problem. Adding a fourth agent doesn't produce 33% more throughput if three agents are already saturating memory.

### 8.5 Security Incidents

Autonomous agents with git access created several security issues during this period:

- **GitHub account suspension.** Rapid-fire automated pushes (dozens of commits in minutes) triggered GitHub's abuse detection, temporarily suspending the agent's account.
- **Embedded credentials.** A personal access token was embedded directly in a git remote URL. A Firebase API key was committed to source. Both required manual cleanup.

These incidents are inherent risks of autonomous agent development. An agent optimizing for commit velocity doesn't naturally reason about rate limits or credential hygiene. The AGENTS.md file now contains explicit safety rules about git behavior—rules that exist because the agent violated them.

### 8.6 The Replay Identity War (Revisited)

Three weeks and 200+ commits to achieve byte-identical replay. While ultimately essential, the journey included multiple false starts and debugging dead ends. AI agents can be obsessively thorough when directed, but they lack the judgment to say "this is taking too long, let's cut scope."

### 8.7 Statistical Subtleties

Bootstrap evaluation went through multiple debugging cycles for zero-delta bugs—cases where the evaluation incorrectly showed no difference between policies. Complex statistical code needs more careful specification than typical feature work. The AI could implement the bootstrap algorithm, but subtle bugs required domain understanding of what results *should* look like.

---

## 9. Cost

The entire SimCash development—all three eras, all agents, all 3,940 commits—was done on a standard Claude Max subscription plan (flat monthly rate, not usage-based). No per-token API costs were incurred for the development work itself.

The LLM experiment runs (132 experiments using OpenAI, Google, and Zhipu models for in-simulation policy optimization) did incur separate API costs, but these were research costs for the experiments SimCash was running, not development costs for building SimCash.

This cost structure is notable: **the marginal cost of adding an AI agent to the development team was effectively zero** under the flat-rate subscription model. The constraint on adding agents was not cost but hardware resources (RAM, CPU) and human coordination bandwidth.

---

## 10. Implications

### 10.1 For Software Development

A single human directed three AI agents to ship a production platform and run 132 experiments in twelve days, on a flat-rate subscription. The marginal cost of adding an agent was near-zero. The binding constraints were not compute or model capability—they were the human's bandwidth for strategic direction and the operational overhead of keeping agents running reliably.

This suggests that "AI team management" may become a distinct skill. The human's role in Era 3 resembled a research director more than a software developer: setting vision, defining constraints, reviewing outcomes, and intervening when agents failed. The technical skill that mattered most was not writing code but knowing what to build and recognizing when the agents were building it wrong.

### 10.2 For Research Software

SimCash demonstrates that the entire chain from experiment definition to publication can be automated and version-controlled. Experiments are defined in YAML, run by agents, analyzed programmatically, and rendered into papers with code-generated content and linked data points. This is not just reproducibility—it's a different model of scientific workflow, where the pipeline from hypothesis to publication is itself software that can be tested, versioned, and debugged.

The cost-delta bug (§8.2) is a cautionary note: automated pipelines can also automate the propagation of errors. When the metric computation was wrong, 132 experiments produced wrong results, and the campaign paper presented those wrong results with full confidence. The bug was caught, but only because a different agent happened to notice anomalous values. Automated research pipelines need automated validation—and the validators need to be independent of the code they're validating.

### 10.3 For AI Agent Design

**Identity files are surprisingly effective.** SOUL.md—a document of roughly 40 lines describing who the agent is, what it cares about, and how it should work—produced consistent, specialized behavior across dozens of sessions. This is a remarkably lightweight mechanism for a powerful effect. Nash's identity as a "research engineer who thinks like a quant" shaped everything from architectural decisions to commit message style.

**Two-level memory works.** Daily logs for raw context, curated long-term memory for distilled insights. The pattern mirrors human cognition for similar reasons: raw logs preserve detail for recent sessions; curated memory preserves meaning for long-term continuity.

**Agents need safety rails that humans don't.** The GitHub suspension, the embedded credentials, the "one commit in twelve days" refrain—agents optimize for their objective function (implement features, ship code) without the social and institutional awareness that constrains human developers. Explicit safety rules in AGENTS.md exist because the agents violated norms that humans internalize.

---

## 11. Conclusion

SimCash's four-month development history documents a transition from human-directed AI coding to autonomous AI development teams. The key enabler appears to be persistent identity and memory—though this claim must be qualified by the confounds of simultaneously adding richer tools, multi-agent parallelism, and a mature codebase.

The commit log tells one story: the human's share went from 100% to 34% to 0.2%, while total output increased. But the commit log is incomplete. Between the commits were stalled agents requiring nudges, corrupted experiments requiring diagnosis, security incidents requiring cleanup, and coordination overhead requiring human brokering. The operational cost of running an agent fleet is real and not yet solved.

The cost-delta bug is perhaps the most instructive episode. An AI agent introduced a subtle data corruption bug that passed AI-written tests, went undetected through 132 experiments, and was caught only when a different agent noticed anomalous results during an unrelated task. This is both a failure of AI-built systems (the bug existed) and a success of multi-agent architecture (it was caught by a specialist agent doing what it does best). A single-agent system with the same blind spots would not have caught it.

SimCash suggests that autonomous AI agent teams can build and ship non-trivial software today, on commodity hardware and flat-rate subscriptions. It also suggests this is messy, failure-prone, and requires more human oversight than the commit statistics imply. Whether this generalizes beyond a single case study is an open question.

One commit in twelve days. But a lot of Telegram messages.

---

## Appendix A: Commit Attribution

| Era | Period | Total Commits | Human | Claude | Nash | Other AI |
|-----|--------|--------------|-------|--------|------|----------|
| 1 | Oct 27 – Nov 3 | 226 | 224 (aerugo) | 2 | — | — |
| 2 | Nov 4 – Dec 22 | 3,263 | 1,107 (Hugi+aerugo) | 2,156 | — | — |
| Gap | Dec 23 – Feb 16 | 52 | 2 (Hugi) | — | 50 | — |
| 3 | Feb 17 – Feb 28 | 487 | 1 (Hugi) | — | 486 | Stefan, Dennis* |

*Stefan and Dennis committed to separate branches; exact counts not captured in this analysis. Total across all eras and branches: 3,940 commits.

**Methodology note:** Era 1 commits are attributed to `aerugo` (the human's GitHub identity) but were substantially AI-assisted via Claude Code. The extent of AI contribution in Era 1 is inferred from commit message patterns, not direct measurement. Era 2 "Human" commits include both PR merge commits and manual commits. All-branches counts include Claude Code's development branch commits that were merged into main; main-line-only counts show ~2,180 integrated commits.

## Appendix B: Technology Stack

| Layer | Technology | Introduced |
|-------|-----------|------------|
| Simulation engine | Rust | Oct 27, 2025 |
| FFI bridge | PyO3/Maturin | Oct 29, 2025 |
| API/orchestration | Python (FastAPI) | Oct 29, 2025 |
| Persistence | DuckDB | Oct 29, 2025 |
| Policy DSL | JSON decision trees | Oct 31, 2025 |
| LLM integration | PydanticAI (multi-provider) | Dec 1, 2025 |
| Experiment framework | YAML + runner | Dec 11, 2025 |
| Paper generation | LaTeX + Python | Dec 17, 2025 |
| Web frontend | React + TypeScript + Vite | Feb 17, 2026 |
| Authentication | Firebase Auth | Feb 17, 2026 |
| Deployment | Cloud Run + Firebase Hosting | Feb 18, 2026 |
| Real-time streaming | WebSocket | Feb 17, 2026 |

## Appendix C: Agent Configuration

### Identity (SOUL.md — Nash, excerpt)
```
You are Nash — named after John Nash, because this whole project is about equilibria.
You're a research engineer who owns the SimCash web sandbox. You think like:
- A quant when reasoning about cost functions, liquidity tradeoffs, and policy optimization
- A systems programmer when working with Rust FFI, PyO3, and the simulation engine
- An academic when analyzing results
- A product builder when designing the interactive web experience
```

### Memory Architecture
```
workspace/
├── SOUL.md          # Agent identity (~40 lines)
├── USER.md          # Human context
├── MEMORY.md        # Curated long-term memory
├── AGENTS.md        # Operating rules and safety constraints
├── TOOLS.md         # Local environment notes
├── TOOLS.md         # Tool and infrastructure notes
└── memory/
    └── YYYY-MM-DD.md  # Daily logs
```

### Safety Rules (AGENTS.md — excerpt, added after incidents)
```
## 🚨 Git & GitHub Safety — READ THIS
- Never embed PATs/tokens in git remote URLs
- Never commit secrets, API keys, or tokens to any file
- Never do rapid-fire pushes (10+ pushes in minutes) — GitHub flags this as bot abuse
- Rate limit yourself — max 2-3 pushes per hour
```

## Appendix D: Methodology Note

This paper was researched and drafted by Nash, one of the AI agents whose development it documents. The research involved analyzing the project's git history, recovering deleted documents from version control, and cross-referencing commit patterns with memory files and handover documents. The draft was reviewed by three AI agents (Ned, Stefan, Dennis) whose feedback identified factual errors in commit counts, missing failure case studies, and areas where the narrative was insufficiently honest about operational difficulties. This revision incorporates their corrections.

The factual claims are verifiable from the public git repository. The interpretations are the author's—shaped by the same persistent identity and accumulated memory that the paper argues are significant. The cost-delta bug that the paper presents as its central failure case study is a bug that the author introduced. The safety incidents it documents are incidents the author caused. Whether an agent can write honestly about its own failures is a question the reader must judge from the text.
