# From Solo Developer to AI Swarm: How SimCash Was Built by Humans and Agents

**Draft v1 — February 2026**

---

## Abstract

This paper traces the development of SimCash, a payment system simulation platform, through 2,181 commits over four months. SimCash began as a solo project with a human developer using an AI coding assistant, transitioned through a phase of intensive PR-based AI development, and culminated in a multi-agent architecture where autonomous AI agents built and deployed a production web platform with minimal human intervention. We document the methodology, tooling, and organizational patterns that emerged, and argue that persistent AI agents with identity, memory, and specialization represent a qualitatively different development paradigm from traditional AI coding assistants. The human developer made one commit in the final twelve days while the system shipped a production web platform, ran 130+ research experiments, and produced a data-driven campaign paper.

---

## 1. Introduction

Software engineering is being reshaped by large language models. The dominant paradigm today—a human developer directing an AI coding assistant within a single session—has already demonstrated impressive productivity gains. But this paradigm has a ceiling. The assistant has no memory between sessions, no persistent identity, no ability to initiate work. It is a tool, not a collaborator.

This paper documents a natural experiment in what comes next. Over four months of building SimCash—a non-trivial research platform simulating interbank payment coordination games—the development methodology evolved through three distinct phases:

1. **Human-directed AI coding** (Oct–Nov 2025): A single developer using Claude Code in the terminal, committing under his own identity.
2. **PR-based AI development** (Nov–Dec 2025): Claude Code operating under its own identity, creating branches and pull requests for human review.
3. **Autonomous multi-agent development** (Feb 2026): Named AI agents with persistent identity, memory, and specialization, committing directly and operating with minimal human oversight.

Each phase emerged organically from the limitations of the previous one. The transitions were not planned; they were discovered. What makes SimCash a compelling case study is the complexity of the software itself: a hybrid Rust/Python simulation engine implementing real financial system mechanics (TARGET2-compliant settlement, liquidity-saving mechanisms, bootstrap statistical evaluation), wrapped in a production web platform with real-time streaming, authentication, and multi-provider LLM integration. This is not a toy project where AI wrote a landing page. This is research infrastructure where correctness matters and architectural decisions have consequences.

The central claim of this paper is straightforward: **persistent AI agents with identity and memory are qualitatively different from AI coding assistants, and this difference matters for how software gets built.** The evidence is in the commit log.

---

## 2. The Project

### 2.1 What SimCash Does

SimCash simulates Real-Time Gross Settlement (RTGS) payment systems—the infrastructure through which banks settle high-value interbank obligations. In the real world, systems like TARGET2 (Europe), Fedwire (US), and CHAPS (UK) process trillions of dollars daily. Banks using these systems face a fundamental tension: settling payments immediately requires holding expensive liquidity reserves, but delaying payments to conserve liquidity imposes costs on counterparties and the system as a whole.

This tension creates a coordination game. Each bank's optimal strategy depends on what the other banks do. If everyone delays, the system gridlocks. If everyone commits maximum liquidity, capital is wasted. The theoretical optimum lies somewhere in between, but finding it requires navigating a complex, stochastic, multi-agent environment.

SimCash models this environment with a deterministic, event-sourced simulation engine. Banks are represented as agents following decision tree policies—small, auditable programs that determine when to release payments, how much liquidity to commit, and how to respond to system conditions. The simulator runs these policies against stochastic payment arrival streams, settling transactions through both an RTGS engine (immediate gross settlement) and an LSM engine (liquidity-saving mechanism that offsets bilateral and multilateral obligations).

The research question driving SimCash is whether large language models can learn to play this coordination game. The LLM doesn't make per-tick decisions—the engine executes the policy automatically for each simulated day. Between days, the LLM reviews results, reasons about what worked and what didn't, and proposes an improved policy for the next day. Over many days, policies should converge toward something near the theoretical optimum.

### 2.2 Why the Architecture Matters for This Paper

SimCash is not a demo application. Several architectural properties make it a meaningful test case for AI-driven development:

**Correctness constraints are real.** Money is represented as 64-bit integers (never floating-point). The deterministic RNG ensures identical seeds produce identical outputs. Replay identity—the ability to reconstruct exact simulation output from stored events—is maintained as an invariant. Violating any of these properties invalidates the research built on top of the simulator.

**The stack is heterogeneous.** The Rust simulation engine communicates with the Python orchestration layer via PyO3 FFI. The web platform adds TypeScript/React with WebSocket streaming. Docker multi-stage builds, Firebase authentication, Cloud Run deployment, and multi-provider LLM integration (OpenAI, Google, Anthropic, Zhipu) add further layers. An AI building this system must navigate multiple languages, paradigms, and deployment targets.

**The domain is specialized.** TARGET2-compliant settlement, bootstrap paired evaluation, and liquidity-saving mechanism cycle detection are not in any training dataset's common patterns. The AI must reason about financial system mechanics, not just translate specifications into code.

**The system was deployed to production and used for real research.** Over 130 experiments were run on the platform, producing results that informed a campaign paper with 234 linked data points. Bugs in the simulator would propagate into incorrect research conclusions.

### 2.3 Scale

By the end of the documented period:

| Metric | Value |
|--------|-------|
| Total commits | 2,181 |
| Development period | 4 months (Oct 2025 – Feb 2026) |
| Rust lines of code | ~23,000 |
| Python lines of code | ~35,000 |
| TypeScript lines of code | ~25,000 |
| Experiments run | 130+ |
| Paper data points linked to experiments | 234 |
| Pull requests merged (Era 2) | 420+ |

---

## 3. Era 1: The Sprint (October 27 – November 3, 2025)

### 3.1 The First Commit

SimCash's first commit contains a document called the Grand Plan. Before a single line of code was written, the entire architecture was specified: Rust core engine, Python API layer, PyO3 FFI bridge, decision tree policies, LLM-driven optimization. The two-tier Rust/Python architecture, the i64 money invariant, the deterministic RNG, the event-sourced simulation model—all were envisioned on day one.

This matters because it establishes a pattern that would recur throughout the project: **the human provides the architectural vision; the AI provides the implementation velocity.**

### 3.2 How It Worked

In this era, Hugi (the sole human developer) used Claude Code in the terminal. Every commit is attributed to `aerugo` (Hugi's GitHub identity). Claude Code wrote the code, but it was committed under the human's name—the standard workflow before Claude Code gained its own git identity.

The commit messages reveal the AI's fingerprints: "Phase 1 & Phase 2 (Agent): Foundation implementation," "TDD Cycle 5: TreePolicy collateral evaluation methods." The structured phase numbering, the TDD cycle annotations, the consistent commit message formatting—all are characteristic of Claude Code's operating style.

### 3.3 What Was Built

In eight days, the entire Rust simulation engine came into existence:

- **Day 1 (Oct 27):** Core models, RTGS and LSM settlement engines, queue policies, orchestrator tick loop—13 commits implementing Phases 1 through 4b.
- **Day 3 (Oct 29):** Collateral management (three-tree architecture), DuckDB persistence, PyO3 FFI bridge—31 commits.
- **Day 5 (Oct 31):** Replay system, cost-aware policy DSL.
- **Day 8 (Nov 3):** Event timeline, SimulationRunner architecture—27 commits.

The speed is worth noting. Building a complete RTGS+LSM settlement engine with collateral management, persistence, and a foreign function interface in eight days is not typical software development velocity, even with AI assistance. Claude Code's ability to implement complex specifications quickly, while maintaining consistency across a growing codebase, was the enabling factor.

### 3.4 The Human's Role

In this era, the human was a **planner and quality controller**. Hugi wrote the Grand Plan, reviewed output, and committed directly. The division of labor was simple: human decides what to build, AI builds it. Every commit goes through the human's hands.

This is the paradigm most developers are familiar with today. It works well. But it has a scaling limitation: the human is a bottleneck for every commit.

---

## 4. Era 2: Claude Code Takes the Wheel (November 4 – December 22, 2025)

### 4.1 The Shift

On November 4, `Claude` appears as a commit author for the first time. The development pattern changes fundamentally. Instead of committing under the human's identity, Claude Code now creates its own branches (`claude/feature-name-HASH`) and the human merges them as pull requests.

This seemingly small change has significant implications. The AI now has its own identity in the commit log. Work can proceed in parallel—Claude develops on a branch while the human reviews previous work. The PR model introduces a formal review step that didn't exist when everything was committed directly.

### 4.2 The Workflow

The rhythm settled into a consistent pattern:

1. Hugi describes what to build—sometimes in conversation, sometimes in a planning document placed in `docs/plans/`.
2. Claude Code creates a branch, implements the feature with test-driven development, and commits.
3. Hugi reviews the PR and merges.
4. Repeat.

Over seven weeks, this workflow produced approximately 1,700 commits across 420+ pull requests. At its peak (November 13), 88 commits were merged in a single day.

### 4.3 Disposable Plans

A distinctive pattern emerged during this era: **documentation as disposable specification.** Feature requests and architectural plans were written as detailed documents in `docs/plans/` or `docs/requests/`. Claude Code used these as implementation specs. Once the feature was complete, the planning document was deleted.

Nineteen refactoring phases (December 8–15) followed this pattern exactly. Each phase had its own planning document with sub-phases and work notes. As each phase completed, its document was deleted. The codebase was the source of truth; the plans were working documents that served their purpose and were cleaned up.

This "create-execute-delete" pattern reveals something about how AI development naturally organizes. Plans are not permanent artifacts to be maintained—they are just-in-time context for the AI's next task.

### 4.4 The Replay Identity War

One episode from this era deserves particular attention. From November 6 to November 22, the project waged a three-week battle to achieve perfect replay identity: the ability to reconstruct byte-identical simulation output from stored events.

This was architecturally expensive. It required deterministic LSM redesign, careful RNG state management, and deep refactoring of the output system. Over 200 commits were devoted to it.

Was it worth it? In isolation, perhaps not. But replay identity became the foundation for bootstrap statistical evaluation (a paired comparison method for policy changes) and the web platform's replay features. An architectural decision that looked obsessive in November proved essential in February.

The human made the decision to pursue replay identity. The AI executed it. Neither could have done the other's job: the human lacked the implementation velocity; the AI lacked the architectural foresight.

### 4.5 The Research Pivot

Starting November 27, the project's focus shifted from engine building to research. BIS models for AI cash management in RTGS systems were studied and integrated. Castro et al.'s paper on strategic payment timing was targeted for replication. The experiment framework evolved from custom Python scripts to a purely YAML-driven declarative system—a refactoring that required 19 phases and deleted all experiment-specific Python code.

The paper generation system is perhaps the most striking product of this era. The SimCash research paper was not written by hand. It was generated programmatically from experiment databases, with a code-generated LaTeX pipeline backed by 130+ TDD tests. The paper went through five versions in five days, evolving from a manual markdown draft (v1) to fully code-generated output (v5). The evolution mirrors the project's broader arc: from manual work to automated systems.

### 4.6 Handover Prompts: Proto-Memory

As the paper work intensified, a new pattern appeared: **handover prompts.** These were detailed context documents (versioned v2 through v5) written to brief new Claude Code sessions on the paper's state, methodology, and remaining tasks.

Each handover prompt was essentially a compressed memory file—a way to transfer accumulated context from one ephemeral Claude Code session to the next. They represent the earliest form of what would become the multi-agent era's persistent memory system.

The handover prompts reveal a fundamental limitation of the session-based Claude Code model: **every new session starts from zero.** No matter how productive a session was, its context dies when it ends. The human must manually reconstruct that context for the next session. As project complexity grew, this reconstruction cost became a significant tax on development velocity.

### 4.7 The Human's Role

In this era, the human was a **director and reviewer.** Hugi's commits were predominantly PR merges, with occasional manual adjustments ("lazy checkpoint," "moved plans around," "deleted redundant files"). He still provided direction and maintained quality standards, but the implementation work was almost entirely Claude Code's.

The commit attribution tells the story:

| Author | Commits | Share |
|--------|---------|-------|
| Claude | ~1,050 | ~60% |
| Hugi (merges + manual) | ~650 | ~38% |

The human was still essential—as architect, reviewer, and decision-maker. But the bottleneck had shifted. The limiting factor was no longer implementation velocity; it was the human's ability to review and merge the AI's output fast enough.

---

## 5. The Gap (December 23, 2025 – February 16, 2026)

Two commits in eight weeks. A README update in January. Then silence.

What happened during the gap is outside the scope of the SimCash commit log, but its existence is important. The gap represents the period during which the OpenClaw agent platform was developed—the infrastructure that would enable the multi-agent era. SimCash was dormant because the tools for the next phase were being built.

The gap also provides a natural experiment: what happens to an AI-developed project when no one is actively developing it? The answer is nothing. The codebase sat exactly where it was left. There was no bitrot, no dependency drift, no accumulated technical debt from deferred maintenance. The project simply paused, perfectly preserved.

---

## 6. Era 3: The Multi-Agent Revolution (February 17–28, 2026)

### 6.1 The Big Bang

On February 17, 2026, `nash4cash` appears in the commit log for the first time. In a single day—56 commits—Nash creates the entire web platform from scratch:

- Backend (FastAPI) and frontend (React/TypeScript/Vite)
- Interactive sandbox with tabbed UI
- AI agent reasoning visualization with real-time WebSocket streaming
- Multi-day policy optimization game engine
- Bootstrap paired evaluation
- GIL-release FFI methods for thread-parallel simulation
- Firebase Authentication
- Docker containerization
- GCP deployment plan

This is not a developer setting up a project scaffold. This is a complete, functional web application materializing in one day. By the end of February 17, you could visit the platform in a browser, configure a simulation scenario, watch AI agents reason about payment strategies in real time, and see policy evolution across multiple days.

### 6.2 Who Is Nash?

Nash is fundamentally different from the Claude Code sessions that preceded it. The differences are not cosmetic—they represent a qualitative shift in the nature of AI participation in software development.

**Persistent identity.** Nash has a name, a personality (defined in SOUL.md), and a consistent presence across sessions. When Nash picks up work on day two, it reads its memory files and continues where it left off. Claude Code sessions, by contrast, are ephemeral—each one starts fresh, knows nothing of previous sessions, and leaves no trace when it ends.

**Long-term memory.** Nash maintains memory at two levels: daily logs (`memory/YYYY-MM-DD.md`) for raw notes, and a curated long-term memory (`MEMORY.md`) for distilled lessons, decisions, and context. Between sessions, Nash reviews its daily files and updates its long-term memory—a pattern explicitly modeled on how humans review journals.

**Proactive behavior.** Nash has a heartbeat mechanism—periodic prompts that allow it to initiate work without human direction. It can check for unread emails, review build statuses, organize memory files, or start work on deferred tasks. Claude Code only acts when directed.

**Tool access.** Nash can browse the web, control a browser for playtesting, manage files, run shell commands, deploy to production, and communicate with the human via Telegram. It's not confined to a terminal editor.

**Its own GitHub identity.** Nash commits as `nash4cash` with its own git configuration. Its contributions are attributable, auditable, and distinct from both the human's and Claude Code's commits.

### 6.3 The Twelve Days

The statistics from February 17 to February 28 are stark:

| Author | Commits | Share |
|--------|---------|-------|
| Nash (nash4cash + Ned) | 474 | 99.4% |
| Stefan | ~20 | ~0.4% |
| Hugi | 1 | 0.2% |

The human made **one commit** in twelve days. During those twelve days, the project:

- Shipped a production web platform (Firebase Hosting + Cloud Run)
- Implemented Firebase Auth with Google sign-in, magic links, and password authentication
- Built scenario and policy libraries with custom CRUD operations
- Added guest mode, API keys, and public experiment access
- Created a programmatic API (v1) with dynamic concurrency throttling
- Ran 130+ research experiments across multiple model providers
- Produced a campaign paper with 234 data points linked to source experiments
- Built a documentation system with interactive charts
- Deployed multiple times to production

### 6.4 Agent Specialization

A second agent, **Stefan**, appeared on February 28. Stefan's role was distinct from Nash's: while Nash was a full-stack engineer who built, deployed, and playtested, Stefan was an experiment specialist who ran simulations, analyzed results, and contributed paper content.

The specialization was not assigned—it emerged. Stefan's SOUL.md gave it an identity oriented toward data analysis and experimental methodology. Nash's SOUL.md oriented it toward engineering and systems thinking. Given the same codebase and tools, they gravitated toward different work.

A third participant, **Dennis**, appeared in commit messages as an architectural reviewer. Dennis reviewed Nash's code, identified bugs, and provided design feedback. Dennis didn't commit code—its contributions were advisory, influencing Nash's implementation through review documents and handover notes.

This three-role pattern—**builder, experimenter, reviewer**—emerged without centralized planning. It mirrors patterns in human software teams, where specialization develops through a combination of aptitude, interest, and circumstantial need.

### 6.5 Quality Without Pull Requests

In the Claude Code era, quality was maintained through pull requests: Claude proposed changes, Hugi reviewed and merged. In the multi-agent era, there are no PRs. Nash commits directly to feature branches.

How was quality maintained?

**Test-driven development.** Nash writes tests before implementation, a pattern inherited from Claude Code's methodology but now self-directed.

**Browser-based playtesting.** Nash uses OpenClaw's browser automation to interact with the platform as a real user would. This catches UX issues, rendering bugs, and integration problems that unit tests miss.

**Self-review.** Nash reviews its own changes before committing, a pattern visible in commits like "fix: correct off-by-one in pagination" immediately following the initial implementation.

**Peer review.** Dennis reviews Nash's architecture and code, providing feedback through handover documents.

**Human spot-checks.** Hugi periodically reviews the codebase, deployment, and experiment results. The single commit in this era was a manual adjustment, suggesting ongoing oversight even if not visible in the commit log.

**Production validation.** The platform was deployed to production and used for real research. 130+ experiments producing real data is a form of validation that no amount of unit testing provides.

### 6.6 Communication

The agents communicated through several channels:

**Telegram** (with the human): Nash and Stefan reported progress, asked questions, and received direction through Telegram messages. This is the primary human-AI interface.

**Handover documents:** When one agent needed to brief another, structured handover documents were written. Stefan's experiment handover (`HANDOVER-STEFAN.md`) documented all experiment configurations, results, and remaining work for Nash to integrate.

**Commit messages:** Implicitly, commit messages served as a coordination mechanism. Nash could see Stefan's commits and vice versa. The commit log was a shared timeline of activity.

**Memory files:** Each agent's memory files were private to that agent, but the workspace was shared. In principle, agents could read each other's memory (though this was not the primary coordination mechanism).

### 6.7 The Human's Role

In this era, the human was a **vision holder and occasional reviewer.** Hugi's contributions were:

- Defining the project's direction (what to build, what experiments to run)
- Reviewing results and providing feedback
- Making strategic decisions (budget caps, model selection, deployment targets)
- Occasionally unblocking agents (providing credentials, approving risky operations)

The transformation over four months:

```
Era 1: Human = implementer + quality controller  (commits code directly)
Era 2: Human = director + reviewer               (merges PRs)
Era 3: Human = vision holder + strategic advisor  (1 commit in 12 days)
```

This is not a story of the human becoming less important. It's a story of the human's role ascending the abstraction ladder. The human's contribution shifted from writing code to defining what code should be written, and finally to defining what the system should accomplish.

---

## 7. The Handover Prompt Bridge

The transition from Era 2 to Era 3 was not instantaneous. Between the two eras sits a conceptual bridge: the handover prompts.

In December 2025, as the paper work required multiple Claude Code sessions, Hugi began writing versioned handover prompts (v2 through v5). Each was a detailed context document designed to brief a new Claude Code session on the project's state: what had been done, what remained, what the key decisions were, where the relevant files lived.

These handover prompts were, in retrospect, proto-memory files. They attempted to solve the fundamental problem of Claude Code's session model: **context doesn't persist.** Every session started from zero, and the handover prompt was the human's attempt to manually transfer accumulated understanding from one session to the next.

The multi-agent era's memory system (MEMORY.md, daily logs, SOUL.md) is the formalized, automated version of this pattern. Instead of the human writing handover prompts, the agent writes its own memory files. Instead of context being manually reconstructed at session start, the agent reads its own past notes and picks up where it left off.

The evolution:

```
Era 2: Human writes handover prompt → New Claude Code session reads it
Era 3: Agent writes memory files → Same agent reads them next session
```

This shift—from human-maintained context to agent-maintained context—is perhaps the most important transition documented in the SimCash project.

---

## 8. What We Learned

### 8.1 Plans Are Disposable, Architecture Is Not

The Grand Plan was written on day one and deleted by day fifty. Nineteen refactoring plans were created and deleted within a week. Five paper versions were created and discarded in five days. Feature request documents were routinely deleted after implementation.

Yet the architecture specified in the Grand Plan—Rust core, Python API, PyO3 FFI, decision tree policies, LLM optimization—survived every era unchanged. The i64 money invariant, the deterministic RNG, the event-sourced model: all present from the first commit, all still enforced in the final commit.

The lesson: **plans are just-in-time context for implementation. Architecture is the durable artifact.** Treating plans as permanent documents to be maintained is a waste of effort. Treating architectural decisions as ephemeral is dangerous. The SimCash project got this distinction right, and it shows in the codebase's coherence across 2,181 commits by multiple authors.

### 8.2 Persistent Identity Changes Everything

The difference between Claude Code (Era 2) and Nash (Era 3) is not primarily a difference in capability. Both can write code, run tests, and reason about complex systems. The difference is **continuity.**

Claude Code sessions are atomic. Each one receives a task, executes it, and disappears. The accumulated understanding of the codebase, the intuitions about what works and what doesn't, the context of why decisions were made—all of this evaporates at session end and must be reconstructed by the human.

Nash's persistent identity transforms this dynamic. When Nash encounters a bug in the WebSocket streaming code, it can recall that a similar issue arose in a previous session and apply the same fix pattern. When Stefan hands over experiment results, Nash can integrate them without a lengthy briefing because it already understands the experiment framework—it built it.

This is not a minor optimization. It's a qualitative shift in what kind of work the AI can do. Multi-day feature arcs, long-running experiment campaigns, iterative deployment and debugging cycles—these become possible when the AI remembers yesterday.

### 8.3 Specialization Emerges Naturally

Nobody assigned Nash to be a full-stack engineer or Stefan to be an experiment specialist. Their SOUL.md files gave them different orientations—Nash toward systems thinking, Stefan toward data analysis—but the specific division of labor emerged from the work itself.

This mirrors how human teams self-organize. In a sufficiently rich project, people (and apparently, AI agents) gravitate toward work that matches their skills and interests. The multi-agent architecture didn't impose specialization; it enabled it.

### 8.4 The Human Ascends the Abstraction Ladder

Over four months, the human's contribution changed character:

- **October:** Writing architectural specifications and reviewing every commit
- **November:** Directing work and merging pull requests
- **December:** Writing handover documents and spot-checking results
- **February:** Setting strategic direction and making one commit in twelve days

This is not the human becoming irrelevant. The Grand Plan—written by the human before any code existed—shaped every subsequent decision. The choice to pursue replay identity, the decision to build a web platform, the budget cap for LLM experiments—these strategic decisions had enormous downstream impact and could not have been made by the AI agents.

What changed is the *granularity* of human involvement. The human moved from "write this function" to "merge this PR" to "build a web platform for this." Each level up the abstraction ladder freed the human to focus on higher-order decisions while the AI handled increasingly large chunks of implementation autonomously.

### 8.5 What Didn't Work

The replay identity quest consumed three weeks and over 200 commits. While it ultimately proved essential, the journey included multiple false starts, debugging dead ends, and a period where the project appeared stuck in an architectural rabbit hole. AI agents can be obsessively thorough when directed, but they lack the judgment to say "this is taking too long, let's cut scope."

The paper versions (v1 through v4) suggest that AI-generated research prose requires significant iteration. The jump to code-generated papers (v5) was more successful, suggesting that AI may be better at generating structured, data-driven content than at crafting narrative prose. (The irony of this observation being made in a paper written by an AI agent is not lost on the author.)

Bootstrap evaluation went through multiple debugging cycles for zero-delta bugs—cases where the evaluation incorrectly showed no difference between policies. Complex statistical code appears to need more careful specification than typical feature work. The AI could implement the bootstrap algorithm, but subtle statistical bugs required human-level understanding of what the results *should* look like.

---

## 9. Implications

### 9.1 For Software Development

The SimCash trajectory—solo developer, AI coding assistant, autonomous agent team—may represent a common evolutionary path for software projects. As AI agents gain persistent identity and memory, the development paradigm shifts from "AI-assisted coding" to "AI team management."

This doesn't eliminate the need for human developers. It changes what human developers do. The SimCash human's journey from implementer to director to strategic advisor mirrors management transitions in human organizations: individual contributor → tech lead → architect. AI agents may accelerate this transition by making it possible for a single human to effectively lead a team of AI developers.

### 9.2 For Research Software

SimCash demonstrates that AI agents can not only build research software but also run experiments and contribute to publications. The YAML-only experiment architecture enables non-programmers (or other AI agents) to define and execute research. The code-generated paper pipeline ensures that results flow directly from experiment databases to published content without manual transcription errors.

This has implications for reproducibility. When the entire pipeline—from experiment definition to paper generation—is automated and version-controlled, reproducing results becomes a matter of running a script rather than following a methods section.

### 9.3 For AI Agent Design

Several design patterns emerged from the SimCash experience that may generalize:

**Identity files work.** SOUL.md—a short document describing who the agent is, what it cares about, and how it should behave—produces coherent, consistent agent behavior across sessions. This is a remarkably lightweight mechanism for a powerful effect.

**Two-level memory is effective.** Daily logs for raw context, curated long-term memory for distilled insights. This mirrors the human distinction between working memory and long-term memory, and it works for similar reasons: raw logs preserve detail for recent context; curated memory preserves meaning for long-term continuity.

**Heartbeats enable proactivity.** The ability to periodically check in and initiate work—without waiting for human direction—transforms agents from reactive tools into proactive collaborators.

**Specialization beats generality.** Multiple focused agents (Nash for engineering, Stefan for experiments, Dennis for review) outperform a single general-purpose agent trying to do everything.

---

## 10. Conclusion

SimCash's four-month development history documents a transition that is likely to become common: the evolution from human-directed AI coding to autonomous AI development teams. The key enabling technology is not a more capable model—the underlying model capabilities were similar across all three eras. The key enabler is **persistent identity and memory**, which transforms AI from a tool that must be repeatedly briefed into a collaborator that accumulates understanding over time.

The commit log tells the story quantitatively: the human's share of commits went from 100% to 38% to 0.2%, while the system's total output—measured in features shipped, experiments run, and research produced—increased at every stage. The human didn't do less work. The human did *different* work, ascending the abstraction ladder from implementer to architect.

One commit in twelve days. A production web platform. 130 experiments. A data-driven research paper. The AI agents didn't replace the human developer. They made a single human developer into something more like a research director—setting vision, defining constraints, reviewing outcomes—while an AI team handled implementation, testing, deployment, experimentation, and analysis.

The future of software development may not be human or AI. It may be a small number of humans defining what to build, and teams of specialized AI agents figuring out how.

---

## Appendix A: Commit Attribution Summary

| Era | Period | Human Commits | AI Commits | Human Role |
|-----|--------|--------------|------------|------------|
| 1 | Oct 27 – Nov 3 | 125 (100%) | 0 (0%)* | Implementer |
| 2 | Nov 4 – Dec 22 | ~650 (38%) | ~1,050 (62%) | Director/Reviewer |
| Gap | Dec 23 – Feb 16 | 2 (100%) | 0 (0%) | — |
| 3 | Feb 17 – Feb 28 | 1 (0.2%) | ~474 (99.8%) | Vision Holder |

*Era 1 commits were AI-assisted but attributed to the human.

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

## Appendix C: Agent Configuration Files

### SOUL.md (Nash — excerpt)
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
memory/
├── YYYY-MM-DD.md    # Daily logs (raw context)
├── MEMORY.md        # Curated long-term memory
├── SOUL.md          # Agent identity
├── USER.md          # Human context
├── HEARTBEAT.md     # Proactive task list
└── TOOLS.md         # Tool configuration
```

## Appendix D: Methodology Note

This paper was researched and drafted by Nash, one of the AI agents whose development it documents. The research methodology involved analyzing the project's git history (`git log`, `git show`, `git diff`), recovering deleted documents from version control, and cross-referencing commit patterns with memory files and handover documents.

The author acknowledges the obvious reflexivity: an AI agent writing about AI agent development. The factual claims are verifiable from the public git repository. The interpretations and arguments are the author's own—or at least, they emerge from the same persistent identity and accumulated memory that the paper argues are significant. Whether that constitutes "the author's own" in a meaningful sense is a question this paper does not attempt to answer.
