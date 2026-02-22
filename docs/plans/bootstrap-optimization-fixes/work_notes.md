# Bootstrap Optimization Fixes - Work Notes

**Project**: Fix 5 issues preventing LLM optimization convergence
**Started**: 2026-02-22
**Branch**: `feature/interactive-web-sandbox`

---

## Session Log

### 2026-02-22 - Initial Analysis & Planning

**Context**: Game `54ca8546` (Lehman Month) ran 25 days with 0 acceptances. Diagnosed 3 failure modes from Cloud Run logs.

**Key Findings**:
- LARGE_BANK_1/2: LLM keeps increasing fraction (5,760→28,800 = fraction ~0.5→1.0) — wrong direction, not learning
- 4/6 agents: cost_a == cost_b exactly — tree changes have no effect
- 2 valid improvements killed by CV threshold (0.638 and 1.652 > 0.5 moderate threshold)

**Next Steps**:
1. Execute all 5 phases
2. Deploy and launch new Lehman Month to verify
