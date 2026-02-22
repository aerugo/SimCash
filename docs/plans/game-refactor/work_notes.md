# Game Module Refactor - Work Notes

**Project**: Refactor game.py god-class and main.py monolith
**Started**: 2026-02-22
**Branch**: `feature/interactive-web-sandbox`

---

## Session Log

### 2026-02-22 - Planning

**Context**: Dennis deep review identified 11 issues. Prioritizing P0 (multi-sample duplication) and P1 (diverging paths, god-class decomposition).

**Approach**: Incremental extraction — each phase produces a working commit. No big-bang rewrite.

**Next**: Execute Phase 1 (extract multi-sample averaging)

### 2026-02-22 - Execution Complete

**Completed Phases 1-5, 7:**
- game.py: 1,447 → 603 lines (58% reduction)
- New files: sim_runner.py (252), bootstrap_gate.py (217), serialization.py (191)
- Unified optimization paths (deleted _real_optimize, ~160 lines)
- Fixed 32 test failures from refactor (patch targets, method renames)
- Cleanup: duplicate route, dotenv at module level, WS test fix

**Phase 6 deferred:** main.py WS handler extraction has low ROI — it's tightly coupled to FastAPI globals (game_manager, game_auto_tasks, locks). Would need dependency injection refactor for marginal benefit.

**Final line counts:**
- game.py: 603 | sim_runner.py: 252 | bootstrap_gate.py: 217 | serialization.py: 191
- streaming_optimizer.py: 680 | main.py: 1,623 (down 8 from duplicate route removal)
- Tests: 314 passing, 13 pre-existing failures (auth, docs, e2e LLM flaky)
