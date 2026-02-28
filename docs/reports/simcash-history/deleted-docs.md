# Recovered Deleted Documents

## Overview
SimCash's docs/ directory was a living workspace — plans were created, executed, and deleted throughout development. This document catalogs the most significant deleted documents and what they reveal about the development process.

---

## 1. The Grand Plan (`docs/grand_plan.md`)

**Created:** Oct 27 (first commit) | **Last seen:** ~Dec 10 (archived to `docs/legacy/`) | **Deleted:** Dec 15

The Grand Plan was the project's founding document, present from the very first commit. It was a comprehensive project plan laying out:

- **Purpose:** "Build a sandboxed, multi-agent simulator of high-value payment operations"
- **Core Innovation:** Decision-tree policies improved by LLM between episodes
- **Architecture:** Two-tier Rust/Python with PyO3 FFI
- **Phased development:** Originally ~10 phases, eventually expanded to 17+

Key insight: **The grand plan was written before a single line of code.** The entire architecture — Rust core, Python API, PyO3 bridge, decision tree policies, LLM optimization — was envisioned from day one. This wasn't emergent; it was designed.

The plan was continuously updated (commits like "Reconcile grand_plan.md with actual implementation status", "Updated Grand Plan to reflect current status") until it became too large and was archived on Dec 10 when the game concept doc absorbed its unique content.

---

## 2. Paper Draft Versions (v1-v5)

Multiple paper drafts were created and deleted as the paper evolved:

### v1 (`docs/papers/simcash-paper/v1/draft-paper.md`)
**Created:** ~Dec 13 | **Deleted:** Dec 18

First attempt at the Castro et al. replication paper. Written by Claude Code as a single markdown document.

### v2 (`docs/papers/simcash-paper/v2/draft-paper.md`)
**Created:** ~Dec 14 | **Deleted:** Dec 18

Added bootstrap evaluation results and deep investigation into Castro deviations.

### v3 (`docs/papers/simcash-paper/v3/draft-paper.md`)
**Created:** ~Dec 15 | **Deleted:** Dec 18

Three-pass experiment methodology. Included lab notes and experiment logs.

### v4 (`docs/papers/simcash-paper/v4/draft-paper.md`)
**Created:** ~Dec 16 | **Deleted:** Dec 18 (then rebuilt, deleted again Dec 21)

Most complete manual draft. Included appendices for prompt audit and iteration tables.

### v5 (`docs/papers/simcash-paper/v5/`)
**Created:** Dec 17 | **Deleted:** Dec 18

The breakthrough: **programmatic paper generation.** Instead of writing the paper manually, v5 built a LaTeX paper generator with 130+ TDD tests. Data-driven content extracted from experiment databases. This became the `paper_generator/` module that survived.

**Narrative significance:** The evolution from v1 (markdown draft) to v5 (code-generated LaTeX paper) in 5 days mirrors the project's broader arc: from manual work to automated systems.

---

## 3. Refactor Plans (`docs/plans/refactor/`)

**Created:** Dec 10-11 | **Deleted:** Dec 12-15 (as phases completed)

An extensive multi-phase refactoring plan with 19 phases:
- Phase 9: Castro module slimming
- Phase 10: Core module consolidation
- Phase 11: StateProvider and persistence
- Phase 12: Castro migration to core infrastructure
- Phase 13-18: Progressive simplification to YAML-only experiments
- Phase 19: Documentation overhaul

Each phase had its own development plan, work notes, and sub-phases. Plans were deleted as soon as their phase completed — a pattern of "disposable planning documents."

---

## 4. Bootstrap Evaluation Plans (`docs/plans/bootstrap/`)

**Created:** Dec 10-13 | **Deleted:** Dec 15

Multiple iterations of bootstrap evaluation planning:
- `development-plan.md` — core bootstrap architecture
- `bilateral_evaluation.md` — paired comparison design
- `scheduled_settlement_event.md` — RTGS correctness for bootstrap
- `phases/phase_7.md`, `phase_7b.md`, `phase_7c.md`, `phase_8_investigate_zero_deltas.md`

These documents reveal the intellectual journey of getting bootstrap evaluation right — from zero deltas (a bug) to correct paired comparison.

---

## 5. Castro Architecture Documents

### `experiments/castro/ARCHITECTURE.md`
**Created:** Dec 3 | **Deleted:** Dec 3 (same day!)

Created and deleted within hours. Replaced by a more comprehensive architecture report.

### `experiments/castro/architecture.md`
**Created:** ~Dec 9 | **Deleted:** Dec 11

Comprehensive Castro architecture documentation, superseded by the YAML-only experiments paradigm.

---

## 6. Optimizer Prompt Plans (`docs/plans/new-optimizer/`, `docs/plans/optimizer_prompt/`)

**Created:** Dec 12 | **Deleted:** Dec 15

Multiple planning documents for the optimizer prompt system — the instructions given to LLMs when generating policies. These went through significant iteration:
- `new-optimizer-plan.md` with phases 1-4
- Work notes tracking implementation progress
- Eventually became the sophisticated prompt architecture documented in the web platform

---

## 7. Experiment Framework Integration Plans

**Created:** Dec 11 | **Deleted:** Dec 15

Four integration plans that together represented the vision for a unified experiment system:
- `01-verbose-logging-integration.md`
- `02-persistence-integration.md`
- `03-live-state-provider-integration.md`
- `04-cli-cleanup.md`

---

## 8. BIS Research Documents

**Created:** Nov 27 | **Deleted:** Nov 27 (same day, reorganized)

- `bis-ai-cash-management-rtgs-model.md`
- `bis-simcash-model-comparison.md`
- `simcash-rtgs-model.md`

Research summaries comparing SimCash to BIS RTGS models. Moved to `docs/research/bis/` on the same day they were created — a case of reorganization rather than deletion.

---

## 9. Feature Requests & Bug Reports (docs/requests/)

Multiple feature requests were created, implemented, and deleted:
- `store-actual-evaluation-costs.md` — merged into persist-policy-evaluation-metrics
- `filter-system-prompt-by-constraints.md` — implemented, deleted
- `improve-bootstrap-convergence-detection.md` — implemented, deleted
- `persist-policy-evaluation-metrics.md` — implemented, deleted

**Pattern:** Feature requests were written as detailed documents, used as implementation specs, then deleted once done. The "docs as disposable specifications" pattern.

---

## 10. Handover Prompts (v2-v5)

**Created and deleted throughout Dec 13-18**

Series of handover prompts for Claude Code sessions working on the paper:
- `v2-handover-prompt.md` — post-bootstrap evaluation
- `v3-handover-prompt.md` — Castro-compliant experiments
- `v4-handover-prompt.md` — extended metrics
- `v5-handover-prompt.md` — paper_generator workflow

Each handover prompt was a detailed context document for starting a new Claude Code session. They represent the earliest form of "agent briefing documents" — a precursor to the CLAUDE.md files that would later define the multi-agent workflow.

---

## Patterns in Document Lifecycle

1. **Create-Execute-Delete:** Planning documents were created as specs, used during implementation, and deleted once complete. The codebase was the source of truth, not the docs.

2. **Rapid Versioning:** The paper went through 5 versions in 5 days, each representing a fundamentally different approach (manual draft → code-generated).

3. **Reorganization over Deletion:** Many "deleted" docs were actually moved (BIS research, grand plan → legacy, Castro → refactored paths).

4. **Handover as Protocol:** The handover prompts evolved from simple context docs into the formalized CLAUDE.md agent briefing system that powered the multi-agent era.

5. **Disposable Plans:** Plans were not treated as permanent artifacts. They were working documents that served their purpose and were cleaned up, keeping the docs/ directory focused on current truth.
