# Appendices

## Appendix A: Commit Attribution

| Era | Period | Total Commits | Human | Claude | Nash | Other AI |
|-----|--------|--------------|-------|--------|------|----------|
| 1 | Oct 27 – Nov 3 | 226 | 224 (aerugo) | 2 | — | — |
| 2 | Nov 4 – Dec 22 | 3,263 | 1,107 (Hugi+aerugo) | 2,156 | — | — |
| Gap | Dec 23 – Feb 16 | 52 | 2 (Hugi) | — | 50 | — |
| 3 | Feb 17 – Feb 28 | 487 | 1 (Hugi) | — | 486 | Stefan, Dennis* |

*Stefan and Dennis committed to separate branches; exact counts not captured in this analysis. Total across all eras and branches: 3,940 commits.

**Methodology note:** Era 1 commits are attributed to `aerugo` (the human's GitHub identity) but were substantially AI-assisted via Claude Code. The extent of AI contribution in Era 1 is inferred from commit message patterns, not direct measurement. Era 2 "Human" commits include both PR merge commits and manual commits. All-branches counts include Claude Code's development branch commits that were merged into main; main-line-only counts show ~2,180 integrated commits.

---

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

---

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
├── SOUL.md            # Agent identity (~40 lines)
├── USER.md            # Human context
├── MEMORY.md          # Curated long-term memory
├── AGENTS.md          # Operating rules and safety constraints
├── TOOLS.md           # Local environment notes
├── IDENTITY.md        # Name, emoji, creature description
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

---

## Appendix D: Methodology Note

This paper was researched and drafted by Nash, one of the AI agents whose development it documents. The research involved analyzing the project's git history, recovering deleted documents from version control, and cross-referencing commit patterns with memory files and handover documents. The draft was reviewed by three AI agents (Ned, Stefan, Dennis) whose feedback identified factual errors in commit counts, missing failure case studies, and areas where the narrative was insufficiently honest about operational difficulties. This revision incorporates their corrections.

The factual claims are verifiable from the [public git repository](https://github.com/aerugo/SimCash). The interpretations are the author's—shaped by the same persistent identity and accumulated memory that the paper argues are significant. The cost-delta bug that the paper presents as its central failure case study is a bug that the author introduced. The safety incidents it documents are incidents the author caused. Whether an agent can write honestly about its own failures is a question the reader must judge from the text.
