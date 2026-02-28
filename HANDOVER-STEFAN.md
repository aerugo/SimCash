# Handover: Q1 2026 Campaign Paper — For Stefan

## What's Live

### Papers on the Docs Site

**Q1 Campaign paper** (new — your experiment data):
- [Introduction & Setup](https://simcash-487714.web.app/docs/papers/q1-campaign/introduction) — research question, 3 models, 10 scenarios, 132 experiments, methodology
- [Results](https://simcash-487714.web.app/docs/papers/q1-campaign/results) — data tables with interactive charts, complexity threshold, smart free-rider effect
- [Discussion & Conclusion](https://simcash-487714.web.app/docs/papers/q1-campaign/discussion) — tragedy of the commons, mechanism design implications
- [Detailed Data (Appendix)](https://simcash-487714.web.app/docs/papers/q1-campaign/appendix) — every run for every scenario, v0.2 variant tables

**Original SimCash paper** (unchanged):
- [Introduction](https://simcash-487714.web.app/docs/papers/simcash/introduction)

**Experiment Showcase** (standalone summary):
- [Showcase](https://simcash-487714.web.app/docs/showcase)

### Experiment Links

Every data point in every table is a clickable link to the source experiment run. 234 links total across the paper — click any cost, settlement rate, or delta value to see the full simulation (policies, balance histories, per-agent costs, day-by-day progression).

Example: clicking "13,660" in the 2B 3T Flash row takes you to https://simcash-487714.web.app/experiment/eaf07a54

### Interactive Charts

The Results page embeds 3 live charts (recharts):
1. **Cost comparison** — grouped bars: baseline vs Flash vs Pro for simple scenarios
2. **Complex cost delta** — bars showing % cost increase for 5+ bank scenarios
3. **Settlement degradation** — line chart: cumulative SR dropping over 25 days with baseline reference

Charts are API-driven (`/api/docs/chart-data/{chart_id}`), not hardcoded.

---

## Where to Edit

### Paper Content

All on branch `experiments/2026q1-stefan`:

```
web/backend/docs/papers/q1-campaign/
├── introduction.md    # Research question, setup, methodology
├── results.md         # Data tables + chart markers (← most of the links)
├── discussion.md      # Interpretation, implications
└── appendix.md        # Full per-run data for all 130 experiments
```

Standard Markdown with remark-gfm (tables), KaTeX math (`$$...$$`), and `rehype-raw` for inline HTML.

### Charts

Placed with HTML comments — move them anywhere in any doc page:
```markdown
<!-- CHART: cost-comparison -->
<!-- CHART: complex-cost-delta -->
<!-- CHART: settlement-degradation -->
```

**Adding a new chart:**
1. Define chart ID + data shape in `web/backend/app/docs_api.py` → `_build_chart()`
2. Create React component in `web/frontend/src/components/PaperChart.tsx`
3. Register in `web/frontend/src/views/DocsView.tsx` → `CHART_COMPONENTS` map
4. Place `<!-- CHART: your-id -->` in markdown

### Doc Page Registry

To add/remove paper sections, edit `DOC_PAGES` in `web/backend/app/docs_api.py`:
```python
{"id": "papers/q1-campaign/new-section", "title": "Your Title", "icon": "📄",
 "category": "paper", "paper": "q1-campaign",
 "paper_title": "Q1 2026: The Complexity Threshold", "order": 4},
```
Then create the `.md` file at `web/backend/docs/papers/q1-campaign/new-section.md`.

---

## Updating Data

### After adding new experiment results

```bash
# 1. Drop new JSONs into experiments/2026Q1/results/
# 2. Regenerate chart data
python3 experiments/2026Q1/generate_paper_data.py

# 3. Re-run the link script (adds links to any new rows)
python3 experiments/2026Q1/add_links.py

# 4. Commit and deploy
```

### Data pipeline

| Script | What it does |
|--------|-------------|
| `experiments/2026Q1/generate_paper_data.py` | Processes all JSONs → `paper-data.json` + `chart-data.json` |
| `experiments/2026Q1/add_links.py` | Adds experiment links to paper markdown tables |

---

## Key Files

| What | Where |
|------|-------|
| Paper markdown | `web/backend/docs/papers/q1-campaign/*.md` |
| Chart data (deployed) | `web/backend/docs/papers/q1-campaign/chart-data.json` |
| Chart components | `web/frontend/src/components/PaperChart.tsx` |
| Chart→markdown wiring | `web/frontend/src/views/DocsView.tsx` (`CHART_COMPONENTS` + `preprocessCharts`) |
| Chart API endpoint | `web/backend/app/docs_api.py` (`_build_chart`) |
| Doc page registry | `web/backend/app/docs_api.py` (`DOC_PAGES`) |
| Raw experiment JSONs | `experiments/2026Q1/results/` (131 files) |
| Data generator | `experiments/2026Q1/generate_paper_data.py` |
| Link generator | `experiments/2026Q1/add_links.py` |
| Original SimCash paper | `web/backend/docs/papers/simcash/*.md` (**do not edit**) |

---

## Data Notes

- **GLM complex scenarios excluded** — periodic_shocks, large_network, lehman_month GLM runs are pre-bugfix (cost-delta bug). Filtered by both the data generator and marked in the appendix.
- **Cumulative SR** = total_settled / total_arrived across ALL days (not mean of daily rates). Standard for payments research.
- **130 experiment IDs** mapped across 234 links in the paper.
- **v0.2 variants** (castro_exp2 only): c1-info, c2-floor, c3-guidance, c4-composition — all 3 models × 3 runs = 36 experiments, fully documented in appendix.
- **Missing r1 runs**: `liquidity_squeeze` and `periodic_shocks` only have r2/r3 (r1 files don't exist).

---

## Deploying

```bash
cd SimCash
git checkout experiments/2026q1-stefan
# ... make edits ...
git add -A && git commit -m "your message"

# Build
gcloud builds submit --config=cloudbuild.yaml \
  --substitutions=SHORT_SHA=$(git rev-parse --short=7 HEAD)

# If auto-deploy step fails, deploy manually:
SHORT_SHA=$(git rev-parse --short=7 HEAD)
gcloud run deploy simcash \
  --image europe-north1-docker.pkg.dev/simcash-487714/cloud-run-source-deploy/simcash:$SHORT_SHA \
  --region europe-north1 --platform managed
```
