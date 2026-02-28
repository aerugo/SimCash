# Development Methodology Evolution

## Phase 1: Human-Directed Solo Development (Oct 27 – Nov 3, 2025)

### The "aerugo" Era
All 125 commits in the first week are authored by `aerugo` (Hugi's GitHub username). There are no PR branches, no Claude author attribution. Yet the commit messages reveal unmistakable AI-assisted patterns:

- **Phase-based organization:** "Phase 1 & Phase 2 (Agent): Foundation implementation"
- **TDD cycle numbering:** "TDD Cycle 5: TreePolicy collateral evaluation methods"
- **Structured commit messages:** Every commit follows a pattern of `type(scope): description`
- **Rapid, comprehensive implementation:** 31 commits in a single day (Oct 29), covering collateral management, persistence, and FFI

### How Claude Code Was Used
In this era, Hugi was using Claude Code in the terminal, directing it to implement phases from the Grand Plan. Claude Code would write code and commit directly under Hugi's git identity (`aerugo`). Evidence:

1. The Grand Plan existed from commit #1 — a detailed architectural document that reads like an AI-generated specification
2. Commit messages use conventions that became standard Claude Code patterns
3. The speed of implementation (entire RTGS+LSM engine in one day) suggests AI code generation
4. TDD methodology is applied consistently — a signature of Claude Code's preferred workflow

### Development Rhythm
- Hugi writes/updates the Grand Plan
- Claude Code implements the next phase
- Commits go directly to main
- No code review process

---

## Phase 2: Claude Code PR Branches (Nov 4 – Dec 22, 2025)

### The Shift
On November 4, `Claude` appears as a commit author for the first time. The development pattern fundamentally changes:

**Before (Era 1):**
```
aerugo → main (direct commit)
```

**After (Era 2):**
```
Claude → claude/feature-name-hash (branch)
Hugi → main (merge PR)
```

### The PR Branch Pattern
Claude Code creates branches with a distinctive naming convention:
```
claude/feature-name-RANDOM_HASH
```

Examples:
- `claude/review-liquidity-modeling-011CUoQPa5zX2CYsGy6RdkAu`
- `claude/fix-replay-simulation-output-011CUqie3oMs2NweUVEtxe2p`
- `claude/policy-scenario-testing-architecture-011CV5QrWYjXCXWe5kKezXyv`

Hugi merges these as GitHub PRs (numbered #1 through #420+). This is the "standard" Claude Code workflow:
1. Hugi describes what to build
2. Claude Code creates a branch, implements it with TDD
3. Hugi reviews and merges the PR

### The Human Role
Hugi's commits in this era are:
- **PR merges** (the majority)
- **Manual adjustments:** "lazy checkpoint", "moved plans around", "Deleted redundant files"
- **Direction changes:** updating experiment configs, tweaking parameters
- **Housekeeping:** "Cleaned up old docs", "removed 'castro mode'"

Claude does the heavy engineering. Hugi provides direction and quality control.

### Documentation as Specification
A distinctive pattern emerges: **feature requests as development specs.**

Hugi (or Claude) writes a detailed feature request or plan document in `docs/plans/` or `docs/requests/`. Claude Code implements it via PR. The plan is deleted after completion. This "disposable spec" pattern is the precursor to the formal CLAUDE.md system.

### The Handover Prompt Innovation
Starting Dec 13, "handover prompts" appear — detailed context documents (v2-v5) for briefing new Claude Code sessions on the paper work. These are the earliest form of agent context management.

### Intensity
At its peak, this methodology produced:
- 88 commits in one day (Nov 13)
- 93 commits in one day (Dec 11)
- 420+ PRs merged over 7 weeks
- ~1,700 commits total

---

## Phase 3: The Multi-Agent Revolution (Feb 17 – Feb 28, 2026)

### The Gap
Between Dec 22 and Feb 17, only 2 commits. ~8 weeks of silence.

### What Changed
When development resumes on Feb 17, everything is different:

1. **New author:** `nash4cash` (456 commits in 12 days)
2. **No more PR branches:** Direct commits to feature branches
3. **No more `Claude` author:** The AI is now `nash4cash` — a named agent with identity
4. **Commit messages are more diverse:** Mix of formal and casual styles
5. **A second agent appears:** `Stefan` on Feb 28

### Nash: The Research Engineer Agent
Nash (running on OpenClaw) operates fundamentally differently from Claude Code:

**Claude Code (Era 2):**
- Receives a task from human
- Creates a PR branch
- Implements with TDD
- Waits for human to merge
- No persistent identity or memory

**Nash (Era 3):**
- Has a persistent identity (SOUL.md, MEMORY.md, AGENTS.md)
- Works from a dedicated workspace
- Can initiate work proactively (heartbeats)
- Maintains context across sessions via memory files
- Commits directly (no PR workflow needed)
- Has its own GitHub identity (`nash4cash`)
- Can spawn subagents for subtasks
- Has tools (browser, web search, file system, shell)

### Stefan: The Experiment Runner Agent
Stefan appears on Feb 28, specifically focused on running and analyzing experiments:
- "stefan: wave3 bugfix reruns"
- "Add Stefan experiment handover — all experiments complete"
- "Paper content: introduction & discussion — Stefan"

Stefan's role is narrower than Nash's — a specialized agent for experiment execution and data analysis.

### Dennis: The Reviewer
Dennis appears in commit messages as a code reviewer (not a committing agent):
- "Add game module refactor plan (based on Dennis deep review)"
- "docs: handover for Dennis — intra-scenario settlement & cost bugs"
- "docs: incorporate Dennis feedback on prompt anatomy report"

Dennis reviews Nash's work and provides technical feedback, suggesting a human-in-the-loop review pattern even in the multi-agent era.

### The Development Rhythm in Multi-Agent Era

```
Hugi → defines what to build (docs, handovers, conversations)
Nash → implements features, deploys, playtests (456 commits)
Stefan → runs experiments, analyzes results (experiment-focused)
Dennis → reviews architecture, provides feedback (advisory)
Hugi → reviews, adjusts direction (1 commit in this era!)
```

The human's role shifted from **merging PRs** to **defining direction.** Hugi made only 1 commit in the entire Feb 17-28 period, yet the project shipped a complete web platform, 130+ experiments, and a campaign paper.

---

## Tooling Evolution

### Era 1-2: Claude Code (Terminal)
- Claude Code running in terminal
- Standard Claude Code workflow (branch → PR → merge)
- No persistent agent identity
- Session-based context only

### Era 3: OpenClaw Platform
- **OpenClaw** provides the agent runtime
- **Heartbeats** for proactive behavior
- **Subagents** for parallelized work
- **Memory files** for cross-session continuity
- **CLAUDE.md / AGENTS.md** for agent configuration
- **Browser tool** for playtesting
- **Channel integration** (Telegram) for human communication

### Key Infrastructure:
- `SOUL.md` — agent identity and personality
- `USER.md` — human context
- `MEMORY.md` — long-term memory
- `memory/YYYY-MM-DD.md` — daily logs
- `HEARTBEAT.md` — proactive task list
- `TOOLS.md` — tool configuration

---

## What This Reveals

### 1. The Human Role Transformed
```
Era 1: Human writes plan, AI codes under human's identity
Era 2: Human directs, AI codes under AI's identity, human merges
Era 3: Human defines vision, AI agents execute autonomously
```

### 2. AI Contribution Grew Monotonically
```
Era 1: ~125 commits, AI-assisted but human-attributed
Era 2: ~1,700 commits, ~60% Claude-attributed
Era 3: ~475 commits, ~99% agent-attributed
```

### 3. The "Handover Prompt" Was the Bridge
The handover prompts (v2-v5) in Dec 2025 were the conceptual bridge between Claude Code's session-based work and Nash's persistent agent model. They evolved into:
- CLAUDE.md files (agent instructions)
- SOUL.md (agent identity)
- memory/ files (persistent context)

### 4. Specialization Emerged Naturally
Rather than one general-purpose AI, the multi-agent era produced:
- **Nash:** Full-stack engineer, deployer, playtester
- **Stefan:** Experiment runner, data analyst
- **Dennis:** Architectural reviewer
- Each with distinct commit patterns and communication styles

### 5. The Pace Paradox
The multi-agent era produced similar daily commit counts to the Claude Code era (50-65/day), but the commits were more cohesive — Nash would build, test, deploy, playtest, and fix in a continuous flow rather than the branch-merge-new-branch cycle of Claude Code.
