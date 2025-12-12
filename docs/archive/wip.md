Keep implementing the plans in docs/plans/new-optimizer/. Start by reading docs/plans/new-optimizer/new-optimizer-plan.md carefully and the notes in docs/plans/new-optimizer/work_notes.md to understand what has been done so far.

Every time you start a new phase, create a new fleshed out plan for that phase in docs/plans/new-optimizer/phases/phase_X.md adhering to strict TDD principles,
then work through the sub-phases of that plan until done, then return to plans/refactor/development-plan.md for the next phase, create a fleshed out docs/plans/new-optimizer/phases/phase_X+1.md adhering to strict TDD principles, and so on
Always follow Python and Rust conventions as set out in CLAUDE.md files and .claude/agents/ guides.

Make sure to understand and respect all project invariants. Before starting any work, make sure you understand constraints and invariants of the project at large.
Make sure these are captured in tests, along with the intended logic and functionality of the new features, as you adhere to TDD principles.

As you reach major milestones, run relevant tests in Cargo (for the Rust module) and Pytest (for the api and experiments/castro modules).
Whenever starting new work, look at docs/plans/new-optimizer/work_notes.md to understand what what done last before resuming.


-----------------------

Now we need to iterate to make the policy optimization better.
experiments/castro/experiments/exp1.yaml is an experiment that attempts to recreate an experiment from the paper experiments/castro/papers/castro_et_al.md - the "Inital Liquidit Game" - a one-shot **initial liquidity game** with two agents. We know the optimal policy for this game from the paper. Our goal is to make the policy optimization find this optimal policy, using GPT-5.2 with reasoning set to "high". In order to do so we may need to tweak the scenario and game config to make it more similar to the setup in the paper, and we should espcially pay attention to using the right exclusion for policy and cost schema features to avoid confusing the LLM with features that should not be used in this simple game. We may also find that we need to improve the prompt or other parts of the optimization loop.