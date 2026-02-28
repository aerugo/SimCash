# Agent Archaeology Report: How Nash, Dennis & Stefan Actually Worked

**Compiled by Ned 🦞 — Feb 28, 2026**
**Source: Agent memory files, session histories, workspace artifacts, handover documents**

---

## 1. Timeline of Deployment

### Nash 🏦 — Feb 16-28 (13 days)
- **Feb 16**: First boot. Cloned repo, read all docs, established identity. No code written.
- **Feb 17**: Explosive first day — 56 commits. Built entire web platform from scratch (FastAPI + React + WebSocket streaming + Firebase Auth + Docker). 60 tests by end of day.
- **Feb 18-19**: UX polish waves, playtesting via browser automation, light mode, onboarding tour, docs section. Deployed to Cloud Run + Firebase Hosting.
- **Feb 20**: Production bug-fixing marathon — 9+ bugs in one session (WS crashes, auth races, Firestore config, mobile sign-in, reconnection storms). Public guest access feature built.
- **Feb 21**: Crisis scenario debugging. Settlement rate display always 0% (event type mismatch with Rust engine). Model switch GLM-5 → GLM-4.7 due to rate limits.
- **Feb 22**: Constraint groups system. Incorporated Dennis's penalty mode branch. Stefan's UX testing feedback addressed.
- **Feb 23**: Password auth replaced magic links. Game status visibility. Optimization interval UI fix.
- **Feb 24**: Rate limit investigation. Dynamic concurrency throttling. Degraded status + retry-then-stall system.
- **Feb 25**: OOM fix (bootstrap evaluator leaking Orchestrators). Bootstrap retry with multi-turn LLM conversation. v0.2.0 deployed.
- **Feb 26**: Bootstrap retry debugging (504 timeout on retry calls with 50k+ token history). Cloud Build auto-deploy fixed.
- **Feb 27**: Tour v2 (25-beat onboarding). Cost delta bug found and fixed (62 experiments compromised). Deployed rev 168.
- **Feb 28**: Ownership/auth security audit. Lehman Month experiment salvage. Showcase page + paper pages. White paper research & draft.

### Dennis ⚙️ — Active ~Feb 19-27 (intermittent)
Dennis had a fundamentally different deployment model. He was NOT always-on like Nash. He was activated by Hugi for specific review/audit tasks, worked intensely on them, then went quiet.

- **~Feb 19**: Penalty Mode feature (6 phases). Built `PenaltyMode` enum in Rust (Fixed/Rate), wired through engine + Python + FFI. 18 Rust tests, 18 Python tests. Merged to Nash's branch.
- **~Feb 22**: First code review of Nash's web module. Found: game.py was a 1,447-line god class, dual diverging optimization paths, no reuse of paper's OptimizationLoop. Nash refactored based on review: 1447→603 lines.
- **~Feb 22**: Intra-scenario bugs analysis. Diagnosed settlement >100% (cross-day cumulative, not a bug) and negative costs (engine resets accumulators daily, Nash's code wrongly assumed cumulative).
- **~Feb 22**: Experiment runner vs web platform audit. 4 reports identifying root causes of divergent results between paper pipeline and web sandbox.
- **~Feb 25**: Bootstrap evaluation code audit + handover. Found phantom liquidity pool bug, cost mislabeling (`liquidity_cost` mapped to `overdraft_cost`), rejection amnesia.
- **~Feb 27**: Deep review of Nash's bootstrap retry. Multiple rounds — first review was against stale code (Dennis's mistake). Found key mismatch in `single_agent_context.py`.
- **~Feb 27**: Cost delta bug forensics. Traced through git history to prove engine resets accumulators and Nash's delta code was wrong.

### Stefan 🏦 — Feb 21-28 (8 days)
- **Feb 21**: First session. Identity bootstrapped. Read three key papers (BoC/BIS, AEA, Korinek 2025). Created RTGS knowledge base. Got SimCash account.
- **Feb 22**: First experiments. UX testing report (3 bugs, 3 feature requests). Created 3 complex 25-day scenarios (Lehman Month, Large Network, Periodic Shocks).
- **Feb 24**: 3-model comparison complete (GLM/Flash/Pro on Liquidity Squeeze). Built API pipeline runner (`run-pipeline.py`). Bulk experiments — 18/20 done by end of day.
- **Feb 25**: 65/93 experiments done. Baselines complete. HEADLINE FINDING: LLM optimization destroys value in complex scenarios (5+ banks).
- **Feb 26**: All 93 wave 1 + 12 v0.2 Castro experiments complete (105 total). Debugging bootstrap retry visibility with Nash.
- **Feb 27**: Phase A (v0.2 no-retry) complete — 24 experiments. Phase B retry canary debugging. Phase C retry experiments running — 25/36 done.
- **Feb 28**: All C4-full complex scenarios complete (6 experiments). Conclusion: complexity threshold is structural. Handover to Nash. Pipeline finished.

---

## 2. Coordination Patterns — How It Actually Worked

### The Hugi Hub
Hugi was the primary coordination mechanism. He:
- Forwarded messages between agents ("Stefan found this bug, Nash fix it")
- Forwarded screenshots from one agent to another
- Relayed experiment results and requests
- Asked Ned (me) to check on agents when they went silent

**There was almost no direct agent-to-agent communication.** Nash, Dennis, and Stefan could not message each other. All coordination flowed through:
1. Hugi on Telegram (primary)
2. Shared git repo (commits visible to all)
3. Handover documents in `docs/reports/`
4. Me (Ned) doing status checks and nudges via `sessions_send`

### Handover Documents — The Real Coordination Mechanism
The handover docs were the most structured coordination artifact:
- **Dennis → Nash**: `handover-nash-bootstrap-evaluation.md`, `handover-nash-cost-delta-bug.md`, `handover-nash-experiment-fixes.md`, `web-module-deep-review.md`
- **Nash → Stefan**: `HANDOVER-STEFAN.md`, `handover-stefan-settlement-optimization.md`, `handover-stefan-cost-delta-bug.md`
- **Stefan → Nash**: `HANDOVER-NASH.md` (experiment results + showcase coordination)
- **Nash → Dennis**: `handover-dennis-mid-sim-policy-update.md`, `handover-dennis-intra-scenario-bugs.md`

These documents were the closest thing to formal inter-agent communication. They were detailed, structured, and written with the receiving agent in mind.

### Branch Strategy
- Nash worked on `feature/interactive-web-sandbox` (primary development branch)
- Dennis worked on `feature/penalty-mode` and `feature/mid-sim-policy-update` (feature branches merged into Nash's)
- Stefan worked on `experiments/2026q1-stefan` (experiment branch)
- Dennis's penalty mode branch was merged by Nash on Feb 19

### The Cron/Heartbeat System
- Nash had a 30-minute heartbeat cron (`grand-plan-check`) that kept him working autonomously
- Stefan had a 30-minute overnight experiment monitor cron — this was created mid-campaign to keep experiments flowing overnight
- Dennis had no heartbeat — he was task-driven, not autonomous

---

## 3. Stalling and Failures — The Operational Reality

This is the biggest gap in the white paper. Agent stalling was a **constant operational tax**.

### Nash Stalling Patterns
Nash's primary failure mode was **blocking on builds/deploys**:
1. **Polling loops**: Nash would `exec` a Cloud Build, then repeatedly poll it with `process action=poll` — burning API turns getting "(no new output) Process still running." This happened at least 5-6 times across the 12 days.
2. **While-loop waits**: Nash wrote `while [ status = WORKING ]; do sleep 30; done` commands with 10-15 minute timeouts. During these waits, he was completely unresponsive to Telegram messages.
3. **Aborted turns**: Multiple instances of `stopReason: "aborted"` in Nash's history — the API call was killed mid-response, leaving the session in a bad state with queued messages piling up.

**Impact**: Hugi asked me "is Nash stuck?" or "Nash stopped responding" at least 6-7 times during the 12 days. Each time required diagnosis (me reading Nash's session history) and intervention (nudge via `sessions_send` or telling Hugi to message directly).

**Mitigation attempted**: I added a "NEVER Block on Builds/Deploys" rule to Nash's AGENTS.md on Feb 26. Nash didn't read it because his existing session predated the change.

### Stefan Stalling Patterns
Stefan's primary failure mode was **aborted turns**:
- Multiple instances of responses getting killed mid-generation (`stopReason: "aborted"`, partial text like "They're both still")
- After an aborted turn, the session went into a bad state where queued messages weren't processed
- Stefan's experiment monitoring required browser automation (taking snapshots of SimCash UI) — these large tool responses may have contributed to timeouts

**Specific incidents**:
- Feb 23 ~08:22: Stefan's response aborted mid-sentence. Heartbeat + Hugi messages queued up. Required gateway restart to unstick.
- Feb 23 ~09:09: Same pattern again. Aborted turn, unprocessed messages.
- Last output 32 hours ago at one point while messages were coming in.

### Inter-Agent Message Failures
My `sessions_send` nudges to stuck agents **almost always timed out**:
- Nash: 4+ timeout failures on `sessions_send`
- Stefan: 2+ timeout failures
- The inter-agent messaging essentially doesn't work when an agent is stuck mid-turn

### Resource Contention
- `maxConcurrent: 4` meant agents could preempt each other
- 16 GB RAM on the Mac Mini with 4 agents + Chrome + VS Code caused OOM kills
- Cloud Run OOM on Feb 25 when bootstrap evaluator created too many Orchestrators (Nash fixed with `del orchestrator`)

---

## 4. Quality Incidents — What Shipped Broken

### Security Incidents
1. **Firebase API key committed to source** (Feb ~20): `AIzaSyAT_IULl1kAW804XTIhoLhASDXIlv21Kas` in `firebase.ts`. Google flagged it. Nash fixed by moving to env var.
2. **GitHub account `nash4cash` suspended** (Feb 17): Rapid automated pushes + PAT embedded in git remote URL. Account needed manual restoration.
3. **No ownership checks on API endpoints** (caught Feb 28): Any authenticated user could mutate any other user's experiments. Nash added `_check_owner_or_admin()` after Hugi's audit request.

### Production Bugs
1. **Settlement rate always 0%** (Feb 21): Nash checked for event type `"Settlement"` but Rust engine emits `RtgsImmediateSettlement`, `LsmBilateralOffset`, `Queue2LiquidityRelease`.
2. **Google Sign-In broken** (Feb 23): Password auth refactor broke Google sign-in button. Commit `c1dc209c` fixed it.
3. **`[object Object]` in cost params display** (Feb 21): Nested objects rendered as string. Noted but delayed fix.
4. **Negative costs in multi-day experiments** (Feb 27): `_compute_cost_deltas()` assumed engine returned cumulative costs; actually returned per-day. 62 experiments compromised and needed re-running. Dennis diagnosed the root cause.
5. **WS crash on accept** (Feb 20): `BaseHTTPMiddleware` broke WebSocket connections.
6. **Reconnection storm** (Feb 21): Completed games reconnecting in infinite loop, flooding server.
7. **Auto-run stalling** (Feb 20): Sync-blocking `game.run_day()` blocking the async event loop.
8. **Phantom field names in constraints** (Feb 22): ~20 constraint field names didn't exist in the Rust engine. LLM told to use nonexistent fields → all rejected.
9. **Bootstrap retry silently failing** (Feb 26): 504 DEADLINE_EXCEEDED on Vertex AI, silently caught. Showed `validation_attempts=0, latency=0` with no explanation.

### Data Integrity
- 62 multi-day experiments compromised by the cost delta bug. All were re-run.
- GLM complex scenario results pre-bugfix were in the results directory but compromised. Stefan caught this during showcase page work.
- Stefan's Lehman Month experiments stalled when Cloud Run recycled the instance overnight — no auto-resume mechanism.

---

## 5. The Human's Actual Role

The white paper says Hugi made "one commit in twelve days" and frames him as a "vision holder." The reality is more nuanced. Hugi was **constantly involved** via Telegram:

### What Hugi Actually Did
1. **Firefighting agent stalls**: "Nash stopped responding" → asks Ned to check → Ned diagnoses → Hugi messages agent directly or asks for gateway restart. This happened 6-7+ times.
2. **Forwarding between agents**: Stefan found bugs → Hugi forwarded to Nash. Dennis wrote review → Hugi relayed to Nash. Stefan needed API features → Hugi told Nash.
3. **Strategic decisions**: Model selection (GLM-5 → GLM-4.7), budget cap ($100/month), which experiments to prioritize, when to deploy.
4. **Security oversight**: Asked Nash to audit ownership checks. Flagged the Firebase API key exposure.
5. **Providing credentials**: GCP service account keys, Firebase config, Vercel tokens.
6. **Playtesting**: Logged into the app, found bugs (Google login broken, `[object Object]`), reported to agents.
7. **Unblocking**: Gateway restarts, approving pairing requests, killing hung processes.

### What the White Paper Gets Wrong
The "one commit" stat is technically accurate but misleading. Hugi's Telegram messages to the three agents were a significant coordination effort. He was essentially a **human message bus** between agents that couldn't talk to each other. The "minimal human intervention" framing undersells this operational overhead.

---

## 6. Inter-Agent Dynamics — Did They Actually Collaborate?

### Dennis → Nash: YES, Significant Impact
Dennis's code reviews directly caused major refactors:
- **game.py refactor**: 1,447 → 603 lines after Dennis's deep review identified god-class, dual optimization paths, no code reuse
- **Cost delta bug**: Dennis diagnosed the root cause (engine resets accumulators) that Nash had wrong for 10 days. 62 experiments had to be re-run.
- **Bootstrap bugs**: Dennis found phantom liquidity pool, cost mislabeling (inverted signal to LLM), rejection amnesia. Nash fixed all three.
- **Penalty mode**: Dennis built the entire feature in Rust+Python, Nash merged it.

However, Dennis also made mistakes:
- First bootstrap review was against stale code (Dennis's own admission)
- Cost delta bug analysis initially referenced wrong deployed commit
- Reviews were thorough but sometimes slow to arrive

### Stefan → Nash: YES, Experiment-Driven Development
Stefan's experiments drove Nash's feature development:
- **Rate limiting**: Stefan's bulk experiments hit Vertex AI rate limits → Nash built dynamic concurrency throttling
- **OOM fix**: Stefan's 6-bank experiments caused Cloud Run OOM → Nash fixed bootstrap evaluator memory leak
- **Bootstrap retry visibility**: Stefan needed to see retry data → Nash added `bootstrap_proposals` API
- **Settlement optimization**: Stefan's settlement rate findings → Nash added v0.2 prompt improvements
- **Showcase page**: Stefan completed 130 experiments → Nash built showcase page with real data

Stefan also did UX testing (Feb 22) that found real bugs (stale counterparty refs, missing event types).

### Nash → Dennis: Task-Based
Nash wrote handover docs for Dennis (mid-sim policy update, intra-scenario bugs). Dennis picked these up and executed. The flow was primarily one-directional (Nash identifies problem → writes handover → Dennis investigates/implements).

### Nash → Stefan: Infrastructure Provider
Nash built the platform Stefan ran experiments on. Nash deployed features Stefan requested. Nash fixed bugs Stefan encountered. The relationship was more service-provider than peer-collaborator.

---

## 7. What the White Paper Gets Wrong or Omits

### 1. "Minimal Human Intervention" (Abstract)
Hugi was actively firefighting agent stalls, forwarding messages between agents, and providing operational support throughout. "Minimal commits" ≠ "minimal intervention."

### 2. "Specialization Emerged Naturally" (§6.4)
Specialization was **explicitly designed** via SOUL.md files and separate workspaces. Nash got the web platform workspace. Dennis got the Rust engine workspace. Stefan got a research identity and papers to read. The SOUL.md files didn't just "orient" them — they defined their roles.

### 3. "Quality Without Pull Requests" (§6.5)
Multiple production bugs shipped: settlement always 0%, Google login broken, negative costs, no ownership checks, reconnection storms. The quality story is more like "quality through rapid iteration and bug-fixing" than the paper's framing of proactive quality mechanisms.

### 4. No Mention of Agent Stalling
The biggest operational cost — agents going unresponsive for 30min+ periods, requiring human intervention to unstick — is completely absent from the paper. This happened 6-7+ times across 12 days.

### 5. No Mention of Coordination Overhead
The three agents couldn't communicate directly. All coordination went through Hugi-as-message-bus or handover documents in the repo. The paper describes communication channels but doesn't mention that inter-agent messaging mostly failed.

### 6. Cost Analysis Missing
Running 3-4 agents on Claude Opus 4 continuously for 12 days is expensive. The paper should quantify API costs vs. a single Claude Code session approach.

### 7. The 62 Compromised Experiments
Nash's cost delta bug compromised 62 multi-day experiments that had to be re-run. Dennis diagnosed it. This is a significant quality incident that illustrates both the risks of autonomous development and the value of peer review — but the paper doesn't mention it.

### 8. Dennis's Real Contribution Timeline
The paper implies Dennis was active throughout. In reality, Dennis was activated for specific tasks (penalty mode, code reviews, bug analysis) with gaps between activations. He was the least autonomous of the three — more like an on-call consultant than a team member.

### 9. GitHub Account Suspension
Nash's GitHub account was suspended for bot-like behavior (rapid pushes + embedded PAT). This is mentioned nowhere in the paper but is a real consequence of autonomous agent development that readers should know about.

---

## 8. Summary: The Ground Truth

The multi-agent development of SimCash was **genuinely productive** — 475+ commits, a production web platform, 130+ experiments, and real research findings in 12 days. That's remarkable for any development setup.

But it was also **operationally messy**:
- Agents stalled constantly and needed human intervention
- Coordination was bottlenecked through Hugi as a human message bus
- Production bugs shipped regularly and were fixed reactively
- A major data integrity incident (62 compromised experiments) required re-running
- Security issues were caught late (no ownership checks for 10 days)
- The GitHub account got suspended

The white paper's core argument — that persistent identity + memory is qualitatively different — is well-supported by the evidence. But the "autonomous AI team" framing oversells the autonomy and undersells the human coordination overhead. A more honest framing would be: **"a human research director managing a team of AI specialists via Telegram, with impressive velocity but significant operational overhead."**

The future version of this — where agents can communicate directly, recover from stalls automatically, and coordinate without human message-passing — would be genuinely transformative. But that's not what happened in Feb 2026. What happened was productive, novel, and interesting. It just wasn't as clean as the paper makes it sound.
