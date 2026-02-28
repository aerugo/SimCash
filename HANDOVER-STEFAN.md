# Handover: Q1 2026 Campaign Paper — For Stefan

## Where to Look

### Live Site
- **Original SimCash paper** (unchanged): https://simcash-487714.web.app/docs/papers/simcash/introduction
- **Q1 Campaign paper** (new): https://simcash-487714.web.app/docs/papers/q1-campaign/introduction
- **Experiment Showcase** (summary page): https://simcash-487714.web.app/docs/showcase

The Q1 paper has 4 sections in the sidebar under **"Q1 2026: The Complexity Threshold"**:
1. Introduction & Setup
2. Results (with interactive charts)
3. Discussion & Conclusion
4. Detailed Data (appendix)

### Interactive Charts
The Results page has 3 embedded recharts graphs:
- **Cost comparison** — grouped bars: baseline vs Flash vs Pro for simple scenarios
- **Complex cost delta** — bars showing % cost increase for 5+ bank scenarios
- **Settlement degradation** — line chart: cumulative SR dropping over 25 days (Periodic Shocks Flash) with baseline reference line

Charts are API-driven — data comes from `/api/docs/chart-data/{chart_id}`.

---

## Where to Edit

All paper content lives in the repo at:

```
web/backend/docs/papers/q1-campaign/
├── introduction.md    # Research question, setup, methodology
├── results.md         # Data tables + chart markers
├── discussion.md      # Interpretation, implications
└── appendix.md        # Per-scenario detailed data
```

**Branch:** `experiments/2026q1-stefan`

### Editing Content
Each file is standard Markdown with remark-gfm (tables, strikethrough) and KaTeX math support. Just edit the `.md` files and deploy.

### Adding/Moving Charts
Charts are placed with HTML comments:
```markdown
<!-- CHART: cost-comparison -->
<!-- CHART: complex-cost-delta -->
<!-- CHART: settlement-degradation -->
```
Move these anywhere in any doc page — they'll render inline.

### Updating Chart Data
1. If you re-run experiments or add new results to `experiments/2026Q1/results/`:
   ```bash
   python3 experiments/2026Q1/generate_paper_data.py
   ```
   This regenerates both `experiments/2026Q1/paper-data.json` and `web/backend/docs/papers/q1-campaign/chart-data.json`.

2. Commit and deploy.

### Adding New Charts
1. Define a new chart ID in `web/backend/app/docs_api.py` → `_build_chart()` function
2. Create a React component in `web/frontend/src/components/PaperChart.tsx`
3. Register it in `web/frontend/src/views/DocsView.tsx` → `CHART_COMPONENTS` map
4. Place `<!-- CHART: your-chart-id -->` in any markdown file

### Registering New Paper Sections
If you want to add sections, edit `DOC_PAGES` in `web/backend/app/docs_api.py`:
```python
{"id": "papers/q1-campaign/your-section", "title": "Your Title", "icon": "📄",
 "category": "paper", "paper": "q1-campaign",
 "paper_title": "Q1 2026: The Complexity Threshold", "order": 4},
```
Then create the corresponding `.md` file.

---

## Key Files Reference

| What | Where |
|------|-------|
| Paper markdown | `web/backend/docs/papers/q1-campaign/*.md` |
| Chart data (deployed) | `web/backend/docs/papers/q1-campaign/chart-data.json` |
| Chart components | `web/frontend/src/components/PaperChart.tsx` |
| Chart→markdown wiring | `web/frontend/src/views/DocsView.tsx` (CHART_COMPONENTS + preprocessCharts) |
| Chart API endpoint | `web/backend/app/docs_api.py` (`_build_chart`) |
| Doc page registry | `web/backend/app/docs_api.py` (DOC_PAGES) |
| Raw experiment JSONs | `experiments/2026Q1/results/` (131 files) |
| Data generator | `experiments/2026Q1/generate_paper_data.py` |
| Original SimCash paper | `web/backend/docs/papers/simcash/*.md` (DO NOT EDIT) |

---

## Data Notes

- **GLM complex scenarios excluded** — periodic_shocks, large_network, lehman_month GLM runs are pre-bugfix (cost-delta bug). They sit in results/ but are filtered out by the data generator.
- **Cumulative SR** = total_settled / total_arrived across ALL days (not mean of daily rates). This is standard for payments research.
- **123 valid experiments** processed from 131 total files (8 GLM complex excluded).
- The `all-scenarios` chart endpoint returns the full summary table if you need it for custom views.

---

## Deploying Changes

```bash
cd SimCash
git checkout experiments/2026q1-stefan
# ... make edits ...
git add -A && git commit -m "your message"
gcloud builds submit --config=cloudbuild.yaml \
  --substitutions=SHORT_SHA=$(git rev-parse --short=7 HEAD)
```

Then deploy manually (Cloud Build SA lacks run.services.get):
```bash
SHORT_SHA=$(git rev-parse --short=7 HEAD)
gcloud run deploy simcash \
  --image europe-north1-docker.pkg.dev/simcash-487714/cloud-run-source-deploy/simcash:$SHORT_SHA \
  --region europe-north1 --platform managed
```
