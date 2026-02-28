#!/usr/bin/env python3
"""Add experiment links to Q1 campaign paper markdown files.

Links every data point to its source experiment on simcash-487714.web.app.
"""
import json
import re
from pathlib import Path

RESULTS_DIR = Path(__file__).parent / "results"
PAPER_DIR = Path(__file__).parent.parent.parent / "web" / "backend" / "docs" / "papers" / "q1-campaign"
BASE_URL = "https://simcash-487714.web.app/experiment"


def build_id_map():
    mapping = {}
    for f in sorted(RESULTS_DIR.glob("*.json")):
        if f.stem == "showcase-data":
            continue
        d = json.loads(f.read_text())
        eid = d.get("experiment_id", "")
        if eid:
            mapping[f.stem] = eid
    return mapping


def link(text, eid):
    return f"[{text}]({BASE_URL}/{eid})"


def get_eid(id_map, scenario, model, run=1):
    """Get experiment ID for scenario/model/run combo."""
    if model == "baseline":
        stem = f"{scenario}_-_baseline"
    elif run == 1:
        stem = f"{scenario}_-_{model}"
    else:
        stem = f"{scenario}_-_{model}_(r{run})"
    return id_map.get(stem)


def link_results_table(content, id_map):
    """Link every cell in results.md tables to experiment runs."""
    lines = content.split("\n")
    new_lines = []

    # Track which table we're in based on headers
    table_models = None  # e.g. ["flash", "pro"] based on header

    for line in lines:
        # Detect table headers to determine column mapping
        if line.startswith("| Scenario |"):
            # Parse what models the columns represent
            cols = [c.strip() for c in line.split("|")[1:-1]]
            table_models = []
            for c in cols:
                cl = c.lower()
                if "flash" in cl and ("cost" in cl or "δ" in cl or "sr" in cl):
                    table_models.append(("flash", "cost" if "cost" in cl else "delta" if "δ" in cl else "sr"))
                elif "pro" in cl and ("cost" in cl or "δ" in cl or "sr" in cl):
                    table_models.append(("pro", "cost" if "cost" in cl else "delta" if "δ" in cl else "sr"))
                elif "glm" in cl and ("cost" in cl or "δ" in cl or "sr" in cl):
                    table_models.append(("glm", "cost" if "cost" in cl else "delta" if "δ" in cl else "sr"))
                elif "baseline" in cl and ("cost" in cl or "sr" in cl):
                    table_models.append(("baseline", "cost" if "cost" in cl else "sr"))
                else:
                    table_models.append(None)
            new_lines.append(line)
            continue

        if line.startswith("|---") or line.startswith("| ---"):
            new_lines.append(line)
            continue

        # Match data rows
        m = re.match(r'^\| \[?`(\w+)`\]?\([^)]*\)? \|', line)
        if not m:
            m = re.match(r'^\| `(\w+)` \|', line)

        if m and table_models:
            scenario = m.group(1)
            cells = line.split("|")[1:-1]  # strip leading/trailing empty

            # Link scenario name to baseline
            baseline_eid = get_eid(id_map, scenario, "baseline")
            if baseline_eid and f"[`{scenario}`]" not in cells[0]:
                cells[0] = cells[0].replace(f"`{scenario}`", f"[`{scenario}`]({BASE_URL}/{baseline_eid})")

            # Link each model's cost/SR values
            for i, col_info in enumerate(table_models):
                if col_info is None or i >= len(cells):
                    continue
                model, dtype = col_info
                eid = get_eid(id_map, scenario, model)
                if not eid:
                    continue
                cell = cells[i].strip()
                # Skip if already linked, empty, or just dashes
                if f"]({BASE_URL}" in cell or cell in ("—", ""):
                    continue
                # Link the cell content
                cells[i] = f" {link(cell.strip(), eid)} "

            line = "|" + "|".join(cells) + "|"

        new_lines.append(line)

    return "\n".join(new_lines)


def link_free_rider_table(content, id_map):
    """Link the smart free-rider comparison table."""
    lines = content.split("\n")
    new_lines = []
    in_freerider = False

    for line in lines:
        if "Smart Free-Rider" in line:
            in_freerider = True
        if in_freerider and line.startswith("| Scenario |"):
            in_freerider = True  # confirm
        
        if in_freerider:
            m = re.match(r'^\| `(\w+)` \|', line)
            if m:
                scenario = m.group(1)
                cells = line.split("|")[1:-1]

                # Link scenario
                baseline_eid = get_eid(id_map, scenario, "baseline")
                if baseline_eid and f"[`{scenario}`]" not in cells[0]:
                    cells[0] = cells[0].replace(f"`{scenario}`", f"[`{scenario}`]({BASE_URL}/{baseline_eid})")

                # Flash cost is col 1, Pro cost is col 2
                flash_eid = get_eid(id_map, scenario, "flash")
                pro_eid = get_eid(id_map, scenario, "pro")
                if flash_eid and len(cells) > 1 and f"]({BASE_URL}" not in cells[1]:
                    cells[1] = f" {link(cells[1].strip(), flash_eid)} "
                if pro_eid and len(cells) > 2 and f"]({BASE_URL}" not in cells[2]:
                    cells[2] = f" {link(cells[2].strip(), pro_eid)} "

                line = "|" + "|".join(cells) + "|"
                if line.count("|") < 4:  # safety check
                    pass  # don't corrupt

        new_lines.append(line)

    return "\n".join(new_lines)


def link_stress_table(content, id_map):
    """Link the 2b_stress table."""
    lines = content.split("\n")
    new_lines = []
    in_stress = False

    for line in lines:
        if "2b_stress" in line and "##" in line:
            in_stress = True

        if in_stress and line.startswith("| Model |"):
            in_stress = True

        if in_stress:
            m = re.match(r'^\| (\w+) \|', line)
            if m and m.group(1) in ("Baseline", "Flash", "Pro", "GLM"):
                model = m.group(1).lower()
                eid = get_eid(id_map, "2b_stress", model)
                if eid:
                    cells = line.split("|")[1:-1]
                    display = m.group(1)
                    cells[0] = cells[0].replace(display, f"[{display}]({BASE_URL}/{eid})", 1)
                    line = "|" + "|".join(cells) + "|"

        new_lines.append(line)

    return "\n".join(new_lines)


def link_appendix(content, id_map):
    """Link every row in appendix tables."""
    lines = content.split("\n")
    new_lines = []
    current_scenario = None

    # Map section headers to scenario keys
    scenario_map = {
        "2b_3t": "2b_3t",
        "3b_6t": "3b_6t",
        "4b_8t": "4b_8t",
        "large network": "large_network",
        "lehman month": "lehman_month",
        "periodic shocks": "periodic_shocks",
        "castro_exp2": "castro_exp2",
        "lynx_day": "lynx_day",
        "liquidity_squeeze": "liquidity_squeeze",
        "2b_stress": "2b_stress",
    }

    for line in lines:
        # Detect scenario headers
        if line.startswith("### "):
            header_lower = line[4:].lower().strip()
            for key, val in scenario_map.items():
                if header_lower.startswith(key):
                    current_scenario = val
                    break

        # Match table rows: | r1 | Flash | ... | or | — | Baseline | ... |
        row_match = re.match(r'^\| (r\d+|—) \| (\w+) \|', line)
        if row_match and current_scenario:
            run_label = row_match.group(1)
            model_display = row_match.group(2)
            model = model_display.lower()

            if run_label == "—":
                run = 1
                model = "baseline"
            elif run_label == "r1":
                run = 1
            else:
                run = int(run_label[1:])

            eid = get_eid(id_map, current_scenario, model, run)
            if eid:
                line = line.replace(
                    f"| {run_label} | {model_display} |",
                    f"| {run_label} | [{model_display}]({BASE_URL}/{eid}) |",
                    1
                )

        new_lines.append(line)

    return "\n".join(new_lines)


def link_introduction(content, id_map):
    """Link scenario names in introduction tables to baselines."""
    lines = content.split("\n")
    new_lines = []
    for line in lines:
        m = re.match(r'^\| `(\w+)` \|', line)
        if m:
            scenario = m.group(1)
            eid = get_eid(id_map, scenario, "baseline")
            if eid:
                line = line.replace(f"`{scenario}`", f"[`{scenario}`]({BASE_URL}/{eid})", 1)
        new_lines.append(line)
    return "\n".join(new_lines)


def count_links(text):
    return text.count(BASE_URL)


def main():
    id_map = build_id_map()
    print(f"Loaded {len(id_map)} experiment IDs")

    # Reset files to un-linked state first (re-read originals from git if needed)
    # For now, just process — the script is idempotent (skips already-linked cells)

    processors = {
        "results.md": [link_results_table, link_free_rider_table, link_stress_table],
        "appendix.md": [link_appendix],
        "introduction.md": [link_introduction],
    }

    total_added = 0
    for filename, procs in processors.items():
        filepath = PAPER_DIR / filename
        if not filepath.exists():
            print(f"  SKIP {filename}")
            continue

        content = filepath.read_text()
        before = count_links(content)

        for proc in procs:
            content = proc(content, id_map)

        after = count_links(content)
        added = after - before

        filepath.write_text(content)
        print(f"  {filename}: {after} links total (+{added} new)")
        total_added += added

    print(f"\nTotal: +{total_added} links added")


if __name__ == "__main__":
    main()
