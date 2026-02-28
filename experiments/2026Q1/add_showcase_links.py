#!/usr/bin/env python3
"""Add experiment links to showcase.md tables."""
import json, glob, os, re

BASE = "https://simcash-487714.web.app/experiment"

# Build ID map from results files
id_map = {}
for f in glob.glob('experiments/2026Q1/results/*.json'):
    name = os.path.basename(f).replace('.json', '')
    if name in ('showcase-data', 'pipeline'): continue
    with open(f) as fh:
        d = json.load(fh)
    eid = d.get('experiment_id', '')
    if eid:
        id_map[name] = eid

def link(eid, text):
    return f"[{text}]({BASE}/{eid})"

def get_id(scenario, model, run=1):
    """Get experiment ID for a scenario/model/run combo."""
    suffix = ""
    if run > 1:
        suffix = f"_(r{run})"
    key = f"{scenario}_-_{model}{suffix}"
    return id_map.get(key)

# Read showcase.md
with open('web/backend/docs/showcase.md') as f:
    content = f.read()

# === Section 1: Simple scenarios table ===
# | 2B 3T | 2 | 99,900 | 100% | **15,671** | 100% | 36,491 | 100% | 60,013 | 64% |
# Cols: Scenario | Banks | Baseline Cost | Baseline SR | Flash Cost | Flash SR | Pro Cost | Pro SR | GLM Cost | GLM SR

section1_map = {
    "2B 3T": "2b_3t",
    "3B 6T": "3b_6t",
    "4B 8T": "4b_8t",
}

for display_name, scenario in section1_map.items():
    bl = id_map.get(f"{scenario}_-_baseline")
    fl = id_map.get(f"{scenario}_-_flash")
    pr = id_map.get(f"{scenario}_-_pro")
    gl = id_map.get(f"{scenario}_-_glm")
    
    # Find the line
    pattern = rf"\| {re.escape(display_name)} \|"
    match = re.search(pattern, content)
    if not match:
        print(f"WARNING: Could not find {display_name} in section 1")
        continue
    
    # Find the full line
    line_start = content.rfind('\n', 0, match.start()) + 1
    line_end = content.find('\n', match.start())
    old_line = content[line_start:line_end]
    
    # Parse cells
    cells = [c.strip() for c in old_line.split('|')[1:-1]]
    # cells: [Scenario, Banks, Baseline Cost, Baseline SR, Flash Cost, Flash SR, Pro Cost, Pro SR, GLM Cost, GLM SR]
    
    if bl:
        cells[0] = link(bl, cells[0])
        cells[2] = link(bl, cells[2])
        cells[3] = link(bl, cells[3])
    if fl:
        cells[4] = link(fl, cells[4])
        cells[5] = link(fl, cells[5])
    if pr:
        cells[6] = link(pr, cells[6])
        cells[7] = link(pr, cells[7])
    if gl:
        cells[8] = link(gl, cells[8])
        cells[9] = link(gl, cells[9])
    
    new_line = "| " + " | ".join(cells) + " |"
    content = content[:line_start] + new_line + content[line_end:]

# === Section 2: Threshold table ===
section2_scenarios = {
    "2B 3T": ("2b_3t", "flash", "pro"),
    "3B 6T": ("3b_6t", "flash", "pro"),
    "4B 8T": ("4b_8t", "flash", "pro"),
    "Periodic Shocks": ("periodic_shocks", None, None),  # no r1 flash/pro
    "Large Network": ("large_network", "flash", "pro"),
    "Lehman Month": ("lehman_month", "flash", "pro"),
}

for display_name, (scenario, flash_model, pro_model) in section2_scenarios.items():
    bl = id_map.get(f"{scenario}_-_baseline")
    fl = id_map.get(f"{scenario}_-_flash") if flash_model else None
    pr = id_map.get(f"{scenario}_-_pro") if pro_model else None
    
    # Match in section 2 context (has Days column)
    # | Scenario | Banks | Days | Baseline Cost | Baseline SR | Flash Cost (Δ%) | Flash SR | Pro Cost (Δ%) | Pro SR |
    pattern = rf"\| {re.escape(display_name)} \| \d+ \| \d+"
    match = re.search(pattern, content)
    if not match:
        continue
    
    line_start = content.rfind('\n', 0, match.start()) + 1
    line_end = content.find('\n', match.start())
    old_line = content[line_start:line_end]
    cells = [c.strip() for c in old_line.split('|')[1:-1]]
    # [Scenario, Banks, Days, Baseline Cost, Baseline SR, Flash Cost, Flash SR, Pro Cost, Pro SR]
    
    if bl:
        cells[0] = link(bl, cells[0])
        cells[3] = link(bl, cells[3])
        cells[4] = link(bl, cells[4])
    if fl:
        cells[5] = link(fl, cells[5])
        cells[6] = link(fl, cells[6])
    if pr:
        cells[7] = link(pr, cells[7])
        cells[8] = link(pr, cells[8])
    
    new_line = "| " + " | ".join(cells) + " |"
    content = content[:line_start] + new_line + content[line_end:]

# === Section 3: Castro v0.2 prompt conditions ===
# Need to map conditions to experiment files
castro_conditions = {
    "v0.1": ("flash", "pro", "glm"),       # base run
    "C1-info": ("flash_(c1-info)", "pro_(c1-info)", "glm_(c1-info)"),
    "C2-floor": ("flash_(c2-floor)", "pro_(c2-floor)", "glm_(c2-floor)"),
    "C3-guidance": ("flash_(c3-guidance)", "pro_(c3-guidance)", "glm_(c3-guidance)"),
    "C4-comp": ("flash_(c4-composition)", "pro_(c4-composition)", "glm_(c4-composition)"),
}

for condition, (fl_key, pr_key, gl_key) in castro_conditions.items():
    fl = id_map.get(f"castro_exp2_-_{fl_key}")
    pr = id_map.get(f"castro_exp2_-_{pr_key}")
    gl = id_map.get(f"castro_exp2_-_{gl_key}")
    bl = id_map.get("castro_exp2_-_baseline")
    
    pattern = rf"\| {re.escape(condition)} \|"
    matches = list(re.finditer(pattern, content))
    # Find the one in the v0.2 results table (not in the condition description table)
    for match in matches:
        line_start = content.rfind('\n', 0, match.start()) + 1
        line_end = content.find('\n', match.start())
        old_line = content[line_start:line_end]
        cells = [c.strip() for c in old_line.split('|')[1:-1]]
        
        # Results table has 7 cols: Condition | Flash Cost | Flash SR | Pro Cost | Pro SR | GLM Cost | GLM SR
        if len(cells) == 7:
            if condition == "Baseline (FIFO)" and bl:
                cells[0] = link(bl, cells[0])
            if fl:
                cells[1] = link(fl, cells[1])
                cells[2] = link(fl, cells[2])
            if pr:
                cells[3] = link(pr, cells[3])
                cells[4] = link(pr, cells[4])
            if gl:
                cells[5] = link(gl, cells[5])
                cells[6] = link(gl, cells[6])
            
            new_line = "| " + " | ".join(cells) + " |"
            content = content[:line_start] + new_line + content[line_end:]
            break

# Also link the Baseline (FIFO) row in section 3
bl = id_map.get("castro_exp2_-_baseline")
if bl:
    pattern = r"\| Baseline \(FIFO\) \|"
    match = re.search(pattern, content)
    if match:
        line_start = content.rfind('\n', 0, match.start()) + 1
        line_end = content.find('\n', match.start())
        old_line = content[line_start:line_end]
        cells = [c.strip() for c in old_line.split('|')[1:-1]]
        if len(cells) == 7:
            cells[0] = link(bl, cells[0])
            new_line = "| " + " | ".join(cells) + " |"
            content = content[:line_start] + new_line + content[line_end:]

# === Section 4: Stress tests ===
# High Stress table
stress_models = {"Flash": "flash", "Pro": "pro", "GLM": "glm", "Baseline": "baseline"}
for display, model in stress_models.items():
    eid = id_map.get(f"2b_stress_-_{model}")
    if not eid: continue
    pattern = rf"\| {re.escape(display)} \|"
    # Find in stress section (after "High Stress")
    stress_start = content.find("High Stress")
    if stress_start < 0: continue
    match = re.search(pattern, content[stress_start:])
    if not match: continue
    abs_pos = stress_start + match.start()
    line_start = content.rfind('\n', 0, abs_pos) + 1
    line_end = content.find('\n', abs_pos)
    old_line = content[line_start:line_end]
    cells = [c.strip() for c in old_line.split('|')[1:-1]]
    # [Model, Cost, SR, vs Baseline]
    if len(cells) == 4:
        cells[0] = link(eid, cells[0])
        cells[1] = link(eid, cells[1])
        cells[2] = link(eid, cells[2])
        new_line = "| " + " | ".join(cells) + " |"
        content = content[:line_start] + new_line + content[line_end:]

# Liquidity Squeeze table - note: r1 missing for flash/pro/glm, use r2
squeeze_models = {"Flash": ("flash_(r2)", "flash"), "Pro": ("pro_(r2)", "pro"), "GLM": ("glm_(r2)", "glm"), "Baseline": ("baseline",)}
for display, keys in squeeze_models.items():
    eid = None
    for k in keys:
        eid = id_map.get(f"liquidity_squeeze_-_{k}")
        if eid: break
    if not eid: continue
    pattern = rf"\| {re.escape(display)} \|"
    squeeze_start = content.find("Liquidity Squeeze")
    if squeeze_start < 0: continue
    match = re.search(pattern, content[squeeze_start:])
    if not match: continue
    abs_pos = squeeze_start + match.start()
    line_start = content.rfind('\n', 0, abs_pos) + 1
    line_end = content.find('\n', abs_pos)
    old_line = content[line_start:line_end]
    cells = [c.strip() for c in old_line.split('|')[1:-1]]
    if len(cells) == 4:
        cells[0] = link(eid, cells[0])
        cells[1] = link(eid, cells[1])
        cells[2] = link(eid, cells[2])
        new_line = "| " + " | ".join(cells) + " |"
        content = content[:line_start] + new_line + content[line_end:]

# === Section 5: Lynx Day ===
lynx_models = {"Flash": "flash", "Pro": "pro", "GLM": "glm", "Baseline": "baseline"}
lynx_start = content.find("Lynx Day")
if lynx_start >= 0:
    for display, model in lynx_models.items():
        eid = id_map.get(f"lynx_day_-_{model}")
        if not eid: continue
        pattern = rf"\| {re.escape(display)} \|"
        match = re.search(pattern, content[lynx_start:])
        if not match: continue
        abs_pos = lynx_start + match.start()
        line_start = content.rfind('\n', 0, abs_pos) + 1
        line_end = content.find('\n', abs_pos)
        old_line = content[line_start:line_end]
        cells = [c.strip() for c in old_line.split('|')[1:-1]]
        if len(cells) == 3:  # Model | Cost | SR
            cells[0] = link(eid, cells[0])
            cells[1] = link(eid, cells[1])
            cells[2] = link(eid, cells[2])
            new_line = "| " + " | ".join(cells) + " |"
            content = content[:line_start] + new_line + content[line_end:]

# === Section 6: Smart Free-Rider table ===
freerider_scenarios = {
    "2b_3t": ("2B 3T", "2b_3t"),
    "3b_6t": ("3B 6T", "3b_6t"),
    "4b_8t": ("4B 8T", "4b_8t"),
    "castro_exp2": ("Castro Exp2", "castro_exp2"),
    "large_network": ("Large Network", "large_network"),
    "lehman_month": ("Lehman Month", "lehman_month"),
}

# Find the free-rider section
freerider_start = content.find("Smart Free-Rider Effect")
if freerider_start >= 0:
    # Find the table after it (not the header table in section 2)
    table_start = content.find("| Scenario | Flash Cost | Pro Cost |", freerider_start)
    if table_start >= 0:
        for scenario_key, (display, sc) in freerider_scenarios.items():
            bl = id_map.get(f"{sc}_-_baseline")
            fl = id_map.get(f"{sc}_-_flash")
            pr = id_map.get(f"{sc}_-_pro")
            
            # Escape for regex but handle special chars
            esc = re.escape(display)
            # Try to find this scenario line after the table header
            pattern = rf"\| {esc} \|"
            match = re.search(pattern, content[table_start:])
            if not match: continue
            abs_pos = table_start + match.start()
            line_start = content.rfind('\n', 0, abs_pos) + 1
            line_end = content.find('\n', abs_pos)
            old_line = content[line_start:line_end]
            cells = [c.strip() for c in old_line.split('|')[1:-1]]
            # [Scenario, Flash Cost, Pro Cost, Flash wins?]
            if len(cells) == 4:
                if bl: cells[0] = link(bl, cells[0])
                if fl: cells[1] = link(fl, cells[1])
                if pr: cells[2] = link(pr, cells[2])
                new_line = "| " + " | ".join(cells) + " |"
                content = content[:line_start] + new_line + content[line_end:]

# === Stress scenario table in section 6 (2b_stress) ===
stress_section = content.find("2b_stress")
if stress_section >= 0:
    # Find the table nearby
    for display, model in [("Flash", "flash"), ("Pro", "pro"), ("GLM", "glm"), ("Baseline", "baseline")]:
        eid = id_map.get(f"2b_stress_-_{model}")
        if not eid: continue
        pattern = rf"\| {re.escape(display)} \|"
        # Search after "2b_stress" heading in section 6
        match = re.search(pattern, content[stress_section:])
        if not match: continue
        abs_pos = stress_section + match.start()
        line_start = content.rfind('\n', 0, abs_pos) + 1
        line_end = content.find('\n', abs_pos)
        old_line = content[line_start:line_end]
        cells = [c.strip() for c in old_line.split('|')[1:-1]]
        # Check it's already linked (from section 4)
        if f"{BASE}/" in old_line:
            continue  # already linked

# === Section 6: Complex scenario comparison table ===
complex_start = content.find("Smart Free-Rider Effect", content.find("Smart Free-Rider Effect") + 1) if content.count("Smart Free-Rider Effect") > 1 else -1
# Actually find the second table with complex scenarios
pattern2 = r"\| Complex Scenario \| Flash Cost"
match2 = re.search(pattern2, content)
if match2:
    table2_start = match2.start()
    complex_scenarios = {
        "Periodic Shocks": "periodic_shocks",
        "Large Network": "large_network",
        "Lehman Month": "lehman_month",
    }
    for display, sc in complex_scenarios.items():
        fl = id_map.get(f"{sc}_-_flash") or id_map.get(f"{sc}_-_flash_(r2)")
        pr = id_map.get(f"{sc}_-_pro") or id_map.get(f"{sc}_-_pro_(r2)")
        
        pattern = rf"\| {re.escape(display)} \|"
        match = re.search(pattern, content[table2_start:])
        if not match: continue
        abs_pos = table2_start + match.start()
        line_start = content.rfind('\n', 0, abs_pos) + 1
        line_end = content.find('\n', abs_pos)
        old_line = content[line_start:line_end]
        cells = [c.strip() for c in old_line.split('|')[1:-1]]
        # [Complex Scenario, Flash Cost Δ, Pro Cost Δ, Flash SR, Pro SR]
        if len(cells) == 5:
            if fl:
                cells[1] = link(fl, cells[1])
                cells[3] = link(fl, cells[3])
            if pr:
                cells[2] = link(pr, cells[2])
                cells[4] = link(pr, cells[4])
            new_line = "| " + " | ".join(cells) + " |"
            content = content[:line_start] + new_line + content[line_end:]

# Now add per-run links in a new section at the bottom (before Methodology Notes)
methodology_marker = "## Methodology Notes"
runs_section = """
## All Experiment Runs

Every experiment was run 3 times (r1, r2, r3) for reproducibility. Click any link to see the full experiment details.

"""

all_scenarios = [
    ("2b_3t", "2B 3T"),
    ("2b_stress", "2B Stress"),
    ("3b_6t", "3B 6T"),
    ("4b_8t", "4B 8T"),
    ("castro_exp2", "Castro Exp2"),
    ("lynx_day", "Lynx Day"),
    ("liquidity_squeeze", "Liquidity Squeeze"),
    ("periodic_shocks", "Periodic Shocks"),
    ("large_network", "Large Network"),
    ("lehman_month", "Lehman Month"),
]

models_order = ["baseline", "flash", "pro", "glm"]

for sc_key, sc_display in all_scenarios:
    runs_section += f"### {sc_display}\n\n"
    runs_section += "| Model | r1 | r2 | r3 |\n"
    runs_section += "|-------|----|----|----|\n"
    
    for model in models_order:
        r1 = id_map.get(f"{sc_key}_-_{model}")
        r2 = id_map.get(f"{sc_key}_-_{model}_(r2)")
        r3 = id_map.get(f"{sc_key}_-_{model}_(r3)")
        
        if not r1 and not r2 and not r3:
            continue
        
        r1_link = link(r1, "r1") if r1 else "—"
        r2_link = link(r2, "r2") if r2 else "—"
        r3_link = link(r3, "r3") if r3 else "—"
        
        if model == "baseline":
            r1_link = link(r1, "baseline") if r1 else "—"
            runs_section += f"| **Baseline** | {r1_link} | — | — |\n"
        else:
            runs_section += f"| **{model.capitalize()}** | {r1_link} | {r2_link} | {r3_link} |\n"
    
    runs_section += "\n"

# Add v0.2 Castro variants
runs_section += "### Castro Exp2 — v0.2 Prompt Variants\n\n"
v02_conditions = ["c1-info", "c2-floor", "c3-guidance", "c4-composition"]  # also c4-comp in filenames
v02_display = {"c1-info": "C1-Info", "c2-floor": "C2-Floor", "c3-guidance": "C3-Guidance", "c4-composition": "C4-Composition"}

for condition in v02_conditions:
    cond_display = v02_display[condition]
    runs_section += f"**{cond_display}:**\n\n"
    runs_section += "| Model | r1 | r2 | r3 |\n"
    runs_section += "|-------|----|----|----|\n"
    
    for model in ["flash", "pro", "glm"]:
        # File naming: flash_(c1-info), flash_(c1-info_r2), flash_(c1-info_r3)
        # But c4 uses "c4-composition" for r1 and "c4-comp" for r2/r3
        r1_key = f"castro_exp2_-_{model}_({condition})"
        if condition == "c4-composition":
            r2_key = f"castro_exp2_-_{model}_(c4-comp_r2)"
            r3_key = f"castro_exp2_-_{model}_(c4-comp_r3)"
        else:
            r2_key = f"castro_exp2_-_{model}_({condition}_r2)"
            r3_key = f"castro_exp2_-_{model}_({condition}_r3)"
        
        r1 = id_map.get(r1_key)
        r2 = id_map.get(r2_key)
        r3 = id_map.get(r3_key)
        
        if not r1 and not r2 and not r3:
            continue
        
        r1_link = link(r1, "r1") if r1 else "—"
        r2_link = link(r2, "r2") if r2 else "—"
        r3_link = link(r3, "r3") if r3 else "—"
        runs_section += f"| **{model.capitalize()}** | {r1_link} | {r2_link} | {r3_link} |\n"
    
    runs_section += "\n"

# Also add the retry canary
canary = id_map.get("castro_exp2_-_flash_(c2-floor_retry-canary)")
if canary:
    runs_section += f"**Special:** [C2-Floor Retry Canary (Flash)]({BASE}/{canary})\n\n"

# Insert before methodology
content = content.replace(methodology_marker, runs_section + methodology_marker)

# Write
with open('web/backend/docs/showcase.md', 'w') as f:
    f.write(content)

print("Done! Links added to showcase.md")

# Count links
link_count = content.count(BASE)
print(f"Total experiment links: {link_count}")
