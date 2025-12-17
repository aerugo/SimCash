# SimCash Paper v5 - AI Agent Instructions

## ⚠️ CRITICAL: Output vs Source Files

### When READING/EVALUATING the paper output:
**ALWAYS read `output/paper.tex`** - This is the rendered LaTeX with actual data values.

```bash
# CORRECT - Read the rendered output
Read output/paper.tex

# WRONG - Don't read these for evaluation
# output/paper_src.tex  ← Has {{placeholders}}, not actual values
# output/paper.pdf      ← Binary file, can't read content
```

### When EDITING the paper:
**ALWAYS edit source files in `src/`** - Never edit output files directly.

```bash
# CORRECT - Edit the source generators
Edit src/sections/abstract.py
Edit src/sections/results.py
Edit src/template.py

# WRONG - Never edit output files
# output/paper.tex      ← Generated file, will be overwritten
# output/paper_src.tex  ← Generated file, will be overwritten
```

## File Structure

```
docs/papers/simcash-paper/v5/
├── src/                    ← EDIT these files
│   ├── sections/           ← Section content generators
│   │   ├── abstract.py     ← Uses var('placeholder') for data
│   │   ├── results.py
│   │   └── ...
│   ├── template.py         ← Template variable definitions
│   ├── paper_builder.py    ← Build orchestration
│   └── ...
├── output/                 ← READ paper.tex, never edit
│   ├── paper.tex           ← ✅ Read this for evaluation
│   ├── paper_src.tex       ← ❌ Has {{placeholders}}, not values
│   └── paper.pdf           ← ❌ Binary, can't read
└── config.yaml             ← Run ID mappings (read-only)
```

## Workflow

1. **To see current paper content**: Read `output/paper.tex`
2. **To modify paper content**: Edit files in `src/sections/*.py`
3. **To add/change data values**: Edit `src/template.py`
4. **To regenerate**: Run `python -m src.cli --config config.yaml --output-dir output/`

## Template System

Section generators use `var('variable_name')` to create placeholders:

```python
# In src/sections/abstract.py
from src.template import var

def generate_abstract(provider=None):
    return rf"""
Our results across {var('total_passes')} independent runs show
{var('overall_convergence_pct')}\% convergence.
"""
```

This generates:
- `paper_src.tex`: `Our results across {{total_passes}} independent runs...`
- `paper.tex`: `Our results across 9 independent runs...`

## Quick Reference

| Task | Action |
|------|--------|
| See paper content | `Read output/paper.tex` |
| Check what placeholders exist | `Read output/paper_src.tex` |
| Edit section text | `Edit src/sections/<section>.py` |
| Add new data variable | `Edit src/template.py` |
| Regenerate paper | `python -m src.cli --config config.yaml --output-dir output/` |
