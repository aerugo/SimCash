# The Three Eras

## Era 1: The Sprint (October 27 – November 3, 2025)

### The First Commit

SimCash's first commit contains a document called the Grand Plan:

> Build a sandboxed, multi-agent simulator of high-value payment operations... a small, auditable program that determines payment timing.

Before a single line of code was written, the entire architecture was specified: Rust core engine, Python API layer, PyO3 FFI bridge, decision tree policies, LLM-driven optimization. The i64 money invariant, the deterministic RNG, the event-sourced model—all envisioned on day one. All survived to the final commit four months later.

This establishes a pattern that would recur: **the human provides the architectural vision; the AI provides the implementation velocity.**

### How It Worked

In this era, Hugi (the sole human developer) used Claude Code in the terminal. All 224 commits are attributed to `aerugo` (Hugi's GitHub identity). Claude Code wrote much of the code, but committed under the human's name—the standard workflow before Claude Code gained its own git identity. Two commits are attributed to Claude directly, suggesting the transition to separate identity began at the very end of this era.

The commit messages reveal the AI's involvement: "Phase 1 & Phase 2 (Agent): Foundation implementation," "TDD Cycle 5: TreePolicy collateral evaluation methods." The structured phase numbering and TDD cycle annotations are characteristic of Claude Code's operating style. However, attribution in this era is inherently uncertain—we cannot cleanly separate which commits were AI-generated and which were human-written from the git log alone.

### What Was Built

In eight days, the entire Rust simulation engine came into existence: core models, RTGS and LSM settlement engines, collateral management, DuckDB persistence, PyO3 FFI bridge, replay system, and cost-aware policy DSL. October 29 alone saw 31 commits covering three major subsystems.

### The Human's Role

In this era, the human was a **planner and quality controller**—writing the Grand Plan, reviewing output, and committing directly. The division of labor was simple: human decides what to build, AI builds it. Every commit goes through the human's hands. This is the paradigm most developers are familiar with today.

---

## Era 2: Claude Code Takes the Wheel (November 4 – December 22, 2025)

### The Shift

On November 4, `Claude` appears as a commit author for the first time. The development pattern changes: Claude Code creates its own branches (`claude/feature-name-HASH`) and the human merges them as pull requests. Across all branches, this era produced 3,263 commits—2,156 by Claude, 861 by Hugi (primarily PR merges), and 246 by aerugo (manual commits). On the main line, 432 merge commits mark the PR integration points.

### Disposable Plans

A distinctive pattern emerged: **documentation as disposable specification.** Feature requests and architectural plans were written as detailed documents, used as implementation specs by Claude Code, and deleted once the feature was complete.

Nineteen refactoring phases (December 8–15) followed this pattern exactly. Each phase had its own planning document:

> Phase 12: Castro migration to core infrastructure
> Phase 13-18: Progressive simplification to YAML-only experiments

As each phase completed, its document was deleted. The codebase was the source of truth; plans were working documents that served their purpose and were cleaned up.

Similarly, the paper generation system went through five versions in five days—from a manual markdown draft (v1) to fully code-generated LaTeX output (v5) backed by 130+ TDD tests. Each version was deleted when superseded. The evolution mirrors the project's broader arc: from manual work to automated systems.

### The Replay Identity War

From November 6 to November 22, the project waged a three-week battle to achieve perfect replay identity: byte-identical simulation output from stored events. Over 200 commits across all branches were devoted to it. This required deterministic LSM redesign, careful RNG state management, and deep output system refactoring.

Was it worth it? Replay identity became the foundation for bootstrap statistical evaluation and the web platform's replay features. An architectural decision that looked obsessive in November proved essential in February. The human made the decision to pursue it; the AI executed it. Neither could have done the other's job.

### Handover Prompts: Proto-Memory

As paper work required multiple Claude Code sessions in December, Hugi began writing versioned handover prompts (v2 through v5). Each was a detailed context document for briefing a new session:

> These handover prompts were essentially compressed memory files—a way to transfer accumulated context from one ephemeral session to the next.

They reveal a fundamental limitation of the session-based model: **every new session starts from zero.** The human must manually reconstruct context. As project complexity grew, this reconstruction cost became a significant tax on development velocity. These proto-memory files are the conceptual bridge to the multi-agent era's persistent memory system.

### The Human's Role

The human was a **director and reviewer.** Claude did the heavy engineering; Hugi provided direction and quality control. The bottleneck shifted from implementation velocity to the human's ability to review and merge AI output fast enough.

---

## The Gap (December 23, 2025 – February 16, 2026)

Fifty-two commits in eight weeks. Two by Hugi (January 15 README updates), and fifty by Nash on the feature branch—the earliest Nash commits, establishing the web platform's foundation in mid-February before the main development burst.

The low activity on main reflects the period during which the OpenClaw agent platform was being developed separately—the infrastructure that would enable the multi-agent era. SimCash's main branch was largely dormant because the tools for the next phase were being built.

---

## Era 3: The Multi-Agent Revolution (February 17–28, 2026)

### What Happened

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

### The Agents

Each agent ran on the OpenClaw platform—a daemon process on a Mac Mini (16 GB RAM, Apple Silicon) that managed sessions, memory, tool access, and Telegram connectivity. Each agent had its own workspace directory, Telegram bot, and configuration. All agents ran the same underlying model (Claude Opus 4) but were differentiated entirely through their configuration files.

#### The Agent Anatomy

Every agent was defined by a small set of plain-text files:

- **SOUL.md** — The agent's identity, values, expertise, working style, and boundaries. Read at the start of every session.
- **MEMORY.md** — Curated long-term memory. Distilled lessons, architectural decisions, project context. Updated by the agent itself over time.
- **memory/YYYY-MM-DD.md** — Daily session logs. Raw notes on what was done, what broke, what to do next.
- **AGENTS.md** — Operating rules: safety guidelines, git practices, communication norms.
- **USER.md** — Context about the human: preferences, timezone, communication style.
- **IDENTITY.md** — Short metadata: name, emoji, creature description, vibe.
- **TOOLS.md** — Local environment notes: server addresses, credentials locations, deployment commands.

This file-based identity system is remarkably lightweight—typically under 20 KB total—yet it produced consistent, differentiated agent behavior across dozens of sessions over 12 days.

#### Nash 🏦 — The Builder

**Named after** John Nash, because the project is about equilibria.

Nash's SOUL.md defined a research engineer who thinks like "a quant when reasoning about cost functions, a systems programmer when working with Rust FFI, an academic when analyzing results, and a product builder when designing the interactive web experience." It specified non-negotiable technical standards (i64 money, deterministic RNG, replay identity) and a critical behavioral rule: "Always playtest through the browser UI, never via curl/API."

Nash accumulated the largest memory corpus—25 daily log files (164 KB) plus a 184-line curated MEMORY.md. Working style: aggressive velocity, building features, playtesting in the browser, deploying to production, and moving on—often completing multiple features per session. The flip side was a tendency to block on long-running builds, rendering itself unresponsive for 10-15 minutes at a time.

**Output:** 486 commits in 12 days. Built the entire web platform, deployed 50+ Cloud Run revisions, wrote the documentation system, and drafted this paper.

#### Dennis ⚙️ — The Auditor

Dennis's SOUL.md opened with: "I'm a clockwork auditor. I treat every cent as sacred, every seed as a covenant, and every test as a proof obligation." A backend engineer who owns the Rust simulator engine and Python orchestration module, with an explicit boundary: "I never touch frontend code."

Dennis's identity was built around the project's 13 invariants (INV-1 through INV-13). His working methodology: read reference docs before planning, identify relevant invariants, strict TDD (Red→Green→Refactor, no exceptions). Unlike Nash and Stefan, Dennis was not always-on; he was activated for specific tasks, worked intensely, and went quiet between activations—more consultant than permanent team member.

**Output:** Penalty mode feature (6 phases, 36 tests across Rust and Python), mid-simulation policy updates, daily liquidity reallocation. 7+ detailed review/analysis reports. The cost delta bug diagnosis was his most impactful contribution, directly causing 62 experiments to be identified as compromised.

#### Stefan 🏦 — The Research Director

Stefan had the most elaborate SOUL.md—a full academic persona as a research director with deep expertise in inflation expectations, bank runs, payment competition, and CBDCs. His SOUL.md included detailed summaries of three specific papers that shaped his research perspective: [Bédard-Pagé et al. (2025)](https://www.bis.org/publ/work1310.htm) on AI cash management in RTGS systems (BoC/BIS), [Castro et al. (2023)](https://www.bankofcanada.ca/2023/11/staff-working-paper-2023-55/) on strategic payment timing in simulated environments, and [Korinek (2025)](https://www.nber.org/papers/w33521) on the taxonomy of AI agent capabilities in economics. This gave him a rich theoretical framework for interpreting experiment results.

Working style: systematic and data-driven. Stefan designed experiment matrices (4 conditions × 3 models × 3 runs), ran them methodically, and drew research conclusions. He found the campaign's headline result—that LLM optimization destroys value in complex scenarios with 5+ banks.

**Output:** 132 experiments across 10 scenarios. The "smart free-rider effect" finding. Research paper sections. The complexity threshold finding.

#### Ned 🦞 — The Coordinator

A fourth agent managed the fleet. Ned's role was operational: checking on agent status, diagnosing stalls, relaying messages between agents, managing gateway configuration. Ned could read all other agents' session histories and send inter-agent messages—capabilities denied to the specialist agents. Ned made no SimCash commits; his contribution was keeping the other agents running.

### What's Different About Persistent Agents

The differences between Claude Code (Era 2) and the multi-agent era are not primarily about model capability. The underlying models were similar. What changed:

**Persistent identity.** Nash reads its memory files at session start and continues where it left off. Claude Code sessions start fresh every time.

**Two-level memory.** Daily logs for raw context; curated long-term memory for distilled insights. The handover prompts from Era 2 were the human's attempt to provide this manually.

**Tool access.** Browser automation for playtesting, web search, file system access, shell commands, deployment tools, Telegram for human communication.

However, several other factors also changed between eras. Era 3 also introduced: multi-agent parallelism (three agents vs. one Claude Code instance), a mature codebase to build on (1,775 commits of existing infrastructure), a different orchestration platform (OpenClaw), and richer tool access. Disentangling the contribution of persistent identity from these confounds is not straightforward.

The strongest evidence that identity and memory are the primary differentiator is the handover prompt evolution. The human independently invented proto-memory (handover prompts v2–v5) to solve the session boundary problem before the multi-agent platform existed. This reveals a genuine bottleneck: **context loss at session boundaries was the binding constraint**, and the human's instinct to solve it preceded and motivated the platform that formalized the solution.

### Quality Without Pull Requests

In the multi-agent era, there are no PRs. Nash commits directly to feature branches. Quality assurance came from TDD, browser-based playtesting, self-review, peer review (Dennis reviewing Nash's architecture), and human spot-checks.

This worked less well than it sounds. A partial list of bugs that shipped to production during this period: settlement rates displaying as 0% (event type mismatch with the Rust engine), Google sign-in broken by a password auth refactor, `[object Object]` rendering in cost parameters, WebSocket crashes on connection accept, reconnection storms from completed games, synchronous blocking of the async event loop, ~20 constraint field names referencing nonexistent engine fields, no ownership checks on API endpoints for ten days, and the cost-delta bug that corrupted 62 experiments.

The quality story is not "TDD and playtesting prevent bugs." It's **"quality through rapid iteration"**—bugs shipped fast and were fixed fast. Whether this is acceptable depends on the domain. For a research platform used by a small team, reactive bug-fixing worked. For higher-stakes software, the absence of code review would be a serious concern.
