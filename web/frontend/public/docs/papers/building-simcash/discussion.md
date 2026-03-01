# Discussion & Conclusion

## What We Learned

### Plans Are Disposable, Architecture Is Not

The Grand Plan was written on day one and deleted by day fifty. Nineteen refactoring plans were created and deleted within a week. Five paper versions were created and discarded in five days.

Yet the architecture specified in the Grand Plan—Rust core, Python API, PyO3 FFI, decision tree policies—survived every era unchanged. The i64 money invariant, the deterministic RNG, the event-sourced model: all present from the first commit, all still enforced in the last.

Plans are just-in-time context for implementation. Architecture is the durable artifact.

### The Human Ascends the Abstraction Ladder

Over four months, the human's contribution changed character:

| Era | Human Role | Human Commits |
|-----|-----------|---------------|
| 1 (Oct–Nov) | Implementer + quality controller | 224 (100%) |
| 2 (Nov–Dec) | Director + reviewer | 861 + 246 merges/manual (~34%) |
| 3 (Feb) | Vision holder + strategic advisor | 1 (0.2%) |

This is not the human becoming irrelevant, and "one commit" dramatically understates the human's actual involvement. Hugi made one commit, but he was constantly active on Telegram: firefighting stalled agents (6–7 times in twelve days), forwarding messages between agents who couldn't communicate directly, providing credentials, playtesting the application and reporting bugs, making strategic decisions (model selection, budget caps, experiment priorities), and restarting failed sessions. The human was a **message bus** between agents that lacked direct communication channels.

A more honest framing: the human's role shifted from writing code to managing an AI team. The commit count captures the first part of that shift but misses the second. "One commit" measures code contribution; it does not measure coordination labor.

### Specialization: Designed and Emergent

Nobody assigned Nash to engineering or Stefan to experiments. Their identity files (SOUL.md) gave them different orientations, but the specific division of labor emerged from the work itself.

This claim requires qualification. Specialization was not purely emergent—it was seeded by design. Each agent received a SOUL.md file that oriented it toward specific work: Nash toward systems engineering, Stefan toward research methodology, Dennis toward backend infrastructure. Each operated in a separate workspace configured for its role. The division of labor grew from these seeds, but the seeds were planted deliberately. A more accurate statement: **specialization was designed at a coarse level and emerged at a fine level.**

---

## What Didn't Work

### Agent Stalling

The paper's most significant operational challenge goes unmentioned in the commit log: agents regularly stall. Nash got stuck in polling loops waiting for Cloud Build completions, entered unresponsive states requiring manual nudges, and occasionally produced aborted turns that consumed API quota without useful output. Stefan experienced similar issues during long experiment runs.

The human's role in the multi-agent era was not as hands-off as the commit statistics suggest. Between the commits, Hugi was monitoring agents via Telegram, nudging stalled processes, restarting failed sessions, and debugging agent infrastructure. "One commit in twelve days" is accurate for the git log; it understates the actual human effort required to keep the agent fleet running.

### The Cost-Delta Bug: A Case Study in AI-Built Failure

During the twelve-day period this paper documents, Nash introduced a bug in `_compute_cost_deltas()` in the Python orchestration layer. The function silently produced incorrect cost metrics for multi-day scenarios—costs that should have been summed across days were instead taken from only the last day, and settlement rates that should have been computed cumulatively were averaged.

The bug passed all existing tests. It was invisible to Nash, who had written both the code and the tests. It was invisible during the 132 experiments Stefan ran on top of it—the experiments completed successfully, producing plausible-looking but incorrect results.

It took Stefan, working on a different task (analyzing experiment results for the campaign paper), to notice that cost reduction percentages didn't match expectations for complex scenarios. Stefan flagged the discrepancy. Dennis audited the Rust engine to rule out simulator-level issues. Nash eventually traced the root cause to the Python metric computation.

The diagnosis required coordinated effort across three agents and the human, took two days, and revealed that data from dozens of experiments needed recomputation.

The damage extended beyond the obvious. Even after the metric computation was corrected, experiments that had run with incorrect cost feedback had corrupted optimization trajectories—the LLM had made policy decisions based on wrong data. These experiments look superficially clean but their optimization paths are poisoned. This is a subtler and more dangerous form of data corruption than explicit errors: **silent failures that produce plausible but wrong results.**

This is the paper's strongest case study for what can go wrong: **an AI-introduced bug, passing AI-written tests, invisible to the AI agents consuming its output, caught only when a different AI agent noticed anomalous results during an unrelated task.** The failure mode is not that AI writes buggy code—humans do too. The failure mode is that AI-written tests may share the same blind spots as AI-written code, because both emerge from the same reasoning process.

### Coordination Overhead

The three agents could not communicate directly. All coordination flowed through three channels: Hugi on Telegram (primary), handover documents committed to the shared repository, and a fourth agent (Ned) who could check agent status and send nudges—though these nudges almost always timed out when the target agent was stuck mid-turn.

The handover documents were the most effective coordination mechanism. Dennis's code reviews (`web-module-deep-review.md`, `handover-nash-cost-delta-bug.md`) directly caused major refactors—Nash's game.py went from 1,447 lines to 603 after Dennis identified it as a god class. Stefan's experiment findings drove Nash's feature development: rate limit issues prompted dynamic concurrency throttling, OOM crashes prompted memory leak fixes. But each of these coordination cycles required Hugi to forward the relevant information between agents.

The irony: handover documents between agents are structurally identical to the handover prompts from Era 2 that the paper identifies as a limitation of the session-based model. Persistent memory solved the *intra-agent* context problem; the *inter-agent* context problem was solved by the same manual forwarding mechanism it was supposed to replace.

### Resource Contention

The development environment ran on a single machine with 16 GB RAM and a concurrency limit of 4 agents. This ceiling caused OOM kills, aborted turns, and agents preempting each other's resources. Multi-agent development sounds like scaling up; on real hardware, it's a resource allocation problem.

### Security Incidents

Autonomous agents with git access created several security issues:

- **GitHub account suspension.** Rapid-fire automated pushes triggered GitHub's abuse detection, temporarily suspending the agent's account.
- **Embedded credentials.** A personal access token was embedded in a git remote URL. A Firebase API key was committed to source. Both required manual cleanup.

These incidents are inherent risks of autonomous agent development. An agent optimizing for commit velocity doesn't naturally reason about rate limits or credential hygiene. The AGENTS.md file now contains explicit safety rules—rules that exist because the agent violated them.

### Statistical Subtleties

Bootstrap evaluation went through multiple debugging cycles for zero-delta bugs—cases where the evaluation incorrectly showed no difference between policies. Complex statistical code needs more careful specification than typical feature work. The AI could implement the bootstrap algorithm, but subtle bugs required domain understanding of what results *should* look like.

---

## Cost

The entire SimCash development—all three eras, all agents, all 3,940 commits—was done on a standard Claude Max subscription plan (flat monthly rate, not usage-based). No per-token API costs were incurred for the development work itself.

The LLM experiment runs (132 experiments using OpenAI, Google, and Zhipu models for in-simulation policy optimization) did incur separate API costs, but these were research costs for the experiments SimCash was running, not development costs for building SimCash.

This cost structure is notable: **the marginal cost of adding an AI agent to the development team was effectively zero** under the flat-rate subscription model. The constraint on adding agents was not cost but hardware resources (RAM, CPU) and human coordination bandwidth.

---

## Implications

### For Software Development

A single human directed three AI agents to ship a production platform and run 132 experiments in twelve days, on a flat-rate subscription. The marginal cost of adding an agent was near-zero. The binding constraints were not compute or model capability—they were the human's bandwidth for strategic direction and the operational overhead of keeping agents running reliably.

This suggests that "AI team management" may become a distinct skill. The human's role in Era 3 resembled a research director more than a software developer: setting vision, defining constraints, reviewing outcomes, and intervening when agents failed.

### For Research Software

SimCash demonstrates that the entire chain from experiment definition to publication can be automated and version-controlled. Experiments are defined in YAML, run by agents, analyzed programmatically, and rendered into papers with code-generated content and linked data points. This is not just reproducibility—it's a different model of scientific workflow.

The cost-delta bug is a cautionary note: automated pipelines can also automate the propagation of errors. Automated research pipelines need automated validation—and the validators need to be independent of the code they're validating.

### For AI Agent Design

**Identity files are surprisingly effective.** SOUL.md—a document of roughly 40 lines describing who the agent is, what it cares about, and how it should work—produced consistent, specialized behavior across dozens of sessions.

**Two-level memory works.** Daily logs for raw context, curated long-term memory for distilled insights. The pattern mirrors human cognition for similar reasons.

**Agents need safety rails that humans don't.** The GitHub suspension, the embedded credentials—agents optimize for their objective function without the social and institutional awareness that constrains human developers. Explicit safety rules exist because the agents violated norms that humans internalize.

---

## Conclusion

SimCash's four-month development history documents a transition from human-directed AI coding to autonomous AI development teams. The key enabler appears to be persistent identity and memory—though this claim must be qualified by the confounds of simultaneously adding richer tools, multi-agent parallelism, and a mature codebase.

The commit log tells one story: the human's share went from 100% to 34% to 0.2%, while total output increased. But the commit log is incomplete. Between the commits were stalled agents requiring nudges, corrupted experiments requiring diagnosis, security incidents requiring cleanup, and coordination overhead requiring human brokering. The operational cost of running an agent fleet is real and not yet solved.

The cost-delta bug is perhaps the most instructive episode. An AI agent introduced a subtle data corruption bug that passed AI-written tests, went undetected through 132 experiments, and was caught only when a different agent noticed anomalous results during an unrelated task. This is both a failure of AI-built systems (the bug existed) and a success of multi-agent architecture (it was caught by a specialist agent doing what it does best). A single-agent system with the same blind spots would not have caught it.

SimCash suggests that autonomous AI agent teams can build and ship non-trivial software today, on commodity hardware and flat-rate subscriptions. It also suggests this is messy, failure-prone, and requires more human oversight than the commit statistics imply. Whether this generalizes beyond a single case study is an open question.

One commit in twelve days. But a lot of Telegram messages.
