#!/usr/bin/env python3
"""Analyze SimCash experiment results and produce showcase-data.json.

For multi-round simple scenarios (rounds>1, same scenario each round):
  - Compare LAST DAY cost/SR vs baseline (1-day cost)
  - This shows the fully-optimized policy performance

For multi-day complex scenarios (rounds=1, many days):
  - Compare total cost across all days, mean SR across all days
"""
import json
import glob
import os
import re
import statistics
from collections import defaultdict
from pathlib import Path

RESULTS_DIR = Path(__file__).parent / "results"
OUTPUT_FILE = RESULTS_DIR / "showcase-data.json"

FILENAME_RE = re.compile(
    r'^(?P<scenario>.+?)_-_(?P<model_or_baseline>[^(]+?)(?:_\((?P<parens>[^)]*)\))?\.json$'
)


def parse_filename(fname: str):
    m = FILENAME_RE.match(fname)
    if not m:
        return None
    scenario = m.group('scenario')
    model_raw = m.group('model_or_baseline').strip()
    parens = m.group('parens') or ''

    if model_raw == 'baseline':
        return scenario, 'baseline', 'baseline', 'r1'

    model = model_raw
    condition = 'v0.1'
    run = 'r1'

    if parens:
        parts = [p.strip() for p in parens.split('_') if p.strip()]
        for p in parts:
            if re.match(r'^r\d+$', p):
                run = p
            elif p.startswith('c1') or p.startswith('c2') or p.startswith('c3') or p.startswith('c4'):
                condition = p
            elif p == 'retry-canary':
                condition = 'retry-canary'

    return scenario, model, condition, run


# Simple scenarios use rounds>1 for optimization iterations on same scenario
SIMPLE_SCENARIOS = ['2b_3t', '3b_6t', '4b_8t', '2b_stress', 'liquidity_squeeze', 'lynx_day', 'castro_exp2']
COMPLEX_SCENARIOS = ['periodic_shocks', 'large_network', 'lehman_month']


def load_experiment(filepath: str):
    with open(filepath) as f:
        data = json.load(f)

    days = data.get('days', [])
    if not days:
        return None

    rounds = data.get('rounds', 1)
    scenario = os.path.basename(filepath).split('_-_')[0]

    # For simple multi-round: use last day as the "optimized" result
    # For complex multi-day (rounds=1): sum all days
    is_simple_multiround = rounds > 1

    if is_simple_multiround:
        last_day = days[-1]
        cost = last_day['total_cost']
        sr = last_day.get('settlement', {}).get('system', {}).get('rate', 0)
    else:
        # Complex multi-day: use cumulative SR (total_settled / total_arrived)
        # The settled/total fields are already running cumulative totals per day,
        # so we use the last day's values. This is the standard in payments literature.
        cost = sum(d.get('total_cost', 0) for d in days)
        last_settlement = days[-1].get('settlement', {}).get('system', {})
        total_settled = last_settlement.get('settled', 0)
        total_arrived = last_settlement.get('total', 0)
        sr = total_settled / total_arrived if total_arrived > 0 else 0

    return {
        'experiment_id': data.get('experiment_id', ''),
        'status': data.get('status', ''),
        'num_days': len(days),
        'num_rounds': rounds,
        'is_multiround': is_simple_multiround,
        'total_cost': cost,  # last-day for simple, sum for complex
        'settlement_rate': round(sr, 4),
        # Also store all-day totals for reference
        'sum_all_days_cost': sum(d.get('total_cost', 0) for d in days),
        'cumulative_sr': round(
            days[-1].get('settlement', {}).get('system', {}).get('settled', 0) /
            max(days[-1].get('settlement', {}).get('system', {}).get('total', 0), 1),
            4) if days else 0,
    }


def main():
    files = sorted(glob.glob(str(RESULTS_DIR / '*.json')))
    files = [f for f in files if 'compromised' not in f
             and not f.endswith('pipeline.log')
             and not f.endswith('showcase-data.json')]

    experiments = []
    for fp in files:
        fname = os.path.basename(fp)
        parsed = parse_filename(fname)
        if not parsed:
            print(f"SKIP: {fname}")
            continue
        scenario, model, condition, run = parsed
        # EXCLUSION: GLM results for complex scenarios are pre-bugfix (cost-delta bug)
        # and were never re-run. They must not be included in analysis. (2026-02-28)
        if model in ('glm',) and scenario in COMPLEX_SCENARIOS:
            print(f"SKIP (GLM+complex pre-bugfix): {fname}")
            continue

        metrics = load_experiment(fp)
        if not metrics:
            print(f"SKIP (no days): {fname}")
            continue
        experiments.append({
            'filename': fname,
            'scenario': scenario,
            'model': model,
            'condition': condition,
            'run': run,
            **metrics,
        })

    by_scenario = defaultdict(list)
    for e in experiments:
        by_scenario[e['scenario']].append(e)

    bank_counts = {
        '2b_3t': 2, '3b_6t': 3, '4b_8t': 4,
        '2b_stress': 2, 'liquidity_squeeze': 2,
        'castro_exp2': 2, 'lynx_day': 4,
        'periodic_shocks': 5, 'large_network': 5, 'lehman_month': 6,
    }

    def scenario_summary(scenario_name):
        exps = by_scenario.get(scenario_name, [])
        baseline = [e for e in exps if e['model'] == 'baseline']
        bl_cost = baseline[0]['total_cost'] if baseline else None
        bl_sr = baseline[0]['settlement_rate'] if baseline else None

        models = {}
        for mn in ['flash', 'pro', 'glm']:
            me = [e for e in exps if e['model'] == mn and e['condition'] == 'v0.1']
            if me:
                avg_cost = statistics.mean(e['total_cost'] for e in me)
                avg_sr = statistics.mean(e['settlement_rate'] for e in me)
                models[mn] = {
                    'avg_cost': round(avg_cost),
                    'avg_sr': round(avg_sr, 4),
                    'n': len(me),
                    'runs': [{'run': e['run'], 'cost': e['total_cost'], 'sr': e['settlement_rate'], 'id': e['experiment_id']} for e in me],
                }
        return {
            'scenario': scenario_name,
            'banks': bank_counts.get(scenario_name, '?'),
            'baseline_cost': bl_cost,
            'baseline_sr': bl_sr,
            'num_days': baseline[0]['num_days'] if baseline else (exps[0]['num_days'] if exps else 1),
            'models': models,
        }

    def castro_summary():
        exps = by_scenario.get('castro_exp2', [])
        baseline = [e for e in exps if e['model'] == 'baseline']
        bl_cost = baseline[0]['total_cost'] if baseline else None
        bl_sr = baseline[0]['settlement_rate'] if baseline else None

        conditions = defaultdict(lambda: defaultdict(list))
        for e in exps:
            if e['model'] == 'baseline':
                continue
            conditions[e['condition']][e['model']].append(e)

        result = {'baseline_cost': bl_cost, 'baseline_sr': bl_sr, 'conditions': {}}
        for cond, models in sorted(conditions.items()):
            cd = {}
            for model, me in sorted(models.items()):
                cd[model] = {
                    'avg_cost': round(statistics.mean(e['total_cost'] for e in me)),
                    'avg_sr': round(statistics.mean(e['settlement_rate'] for e in me), 4),
                    'n': len(me),
                }
            result['conditions'][cond] = cd
        return result

    # Build threshold data
    threshold_data = []
    all_scenarios = ['2b_3t', '3b_6t', '4b_8t', 'periodic_shocks', 'large_network', 'lehman_month']
    for sc in all_scenarios:
        s = scenario_summary(sc)
        if s['baseline_cost'] and s['baseline_cost'] > 0:
            for model, md in s['models'].items():
                delta = ((md['avg_cost'] - s['baseline_cost']) / s['baseline_cost']) * 100
                threshold_data.append({
                    'scenario': sc, 'banks': bank_counts.get(sc),
                    'model': model,
                    'baseline_cost': s['baseline_cost'], 'opt_cost': md['avg_cost'],
                    'baseline_sr': s['baseline_sr'], 'opt_sr': md['avg_sr'],
                    'cost_delta_pct': round(delta, 1),
                    'sr_delta': round(md['avg_sr'] - s['baseline_sr'], 4),
                })

    # Model leaderboard
    model_scores = defaultdict(lambda: {'cost_wins': 0, 'sr_wins': 0, 'both_wins': 0, 'total': 0})
    for sc in ['2b_3t', '3b_6t', '4b_8t', '2b_stress', 'liquidity_squeeze', 'lynx_day', 'castro_exp2']:
        s = scenario_summary(sc)
        for model, md in s['models'].items():
            model_scores[model]['total'] += 1
            cw = md['avg_cost'] < (s['baseline_cost'] or float('inf'))
            sw = md['avg_sr'] >= (s['baseline_sr'] or 0) - 0.02
            if cw: model_scores[model]['cost_wins'] += 1
            if sw: model_scores[model]['sr_wins'] += 1
            if cw and sw: model_scores[model]['both_wins'] += 1

    output = {
        'generated': '2026-02-28',
        'total_experiments': len(experiments),
        'simple_scenarios': {sc: scenario_summary(sc) for sc in ['2b_3t', '3b_6t', '4b_8t']},
        'stress_scenarios': {sc: scenario_summary(sc) for sc in ['2b_stress', 'liquidity_squeeze']},
        'special_scenarios': {sc: scenario_summary(sc) for sc in ['lynx_day']},
        'complex_scenarios': {sc: scenario_summary(sc) for sc in COMPLEX_SCENARIOS},
        'castro_exp2': castro_summary(),
        'threshold_data': threshold_data,
        'model_leaderboard': dict(model_scores),
        'bank_counts': bank_counts,
        'all_experiments': experiments,
    }

    with open(OUTPUT_FILE, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"Written {OUTPUT_FILE} ({len(experiments)} experiments)")

    # Print tables
    print("\n=== SIMPLE SCENARIOS (last-day optimized cost vs baseline) ===")
    for sc in ['2b_3t', '3b_6t', '4b_8t']:
        s = output['simple_scenarios'][sc]
        print(f"\n{sc} ({s['banks']}B, baseline: {s['baseline_cost']:,} / {s['baseline_sr']:.0%})")
        for m, d in s['models'].items():
            delta = ((d['avg_cost'] - s['baseline_cost']) / s['baseline_cost'] * 100) if s['baseline_cost'] else 0
            print(f"  {m}: {d['avg_cost']:,} / {d['avg_sr']:.0%} (Δ{delta:+.1f}%, n={d['n']})")

    print("\n=== STRESS SCENARIOS ===")
    for sc in ['2b_stress', 'liquidity_squeeze']:
        s = output['stress_scenarios'][sc]
        print(f"\n{sc} ({s['banks']}B, baseline: {s['baseline_cost']:,} / {s['baseline_sr']:.0%})")
        for m, d in s['models'].items():
            delta = ((d['avg_cost'] - s['baseline_cost']) / s['baseline_cost'] * 100) if s['baseline_cost'] else 0
            print(f"  {m}: {d['avg_cost']:,} / {d['avg_sr']:.0%} (Δ{delta:+.1f}%, n={d['n']})")

    print("\n=== COMPLEX SCENARIOS (total cost across all days) ===")
    for sc in COMPLEX_SCENARIOS:
        s = output['complex_scenarios'][sc]
        print(f"\n{sc} ({s['banks']}B, {s['num_days']}d, baseline: {s['baseline_cost']:,} / {s['baseline_sr']:.0%})")
        for m, d in s['models'].items():
            delta = ((d['avg_cost'] - s['baseline_cost']) / s['baseline_cost'] * 100) if s['baseline_cost'] else 0
            print(f"  {m}: {d['avg_cost']:,} / {d['avg_sr']:.0%} (Δ{delta:+.1f}%, n={d['n']})")

    print("\n=== CASTRO EXP2 CONDITIONS (last-day cost) ===")
    ce = output['castro_exp2']
    print(f"Baseline: {ce['baseline_cost']:,} / {ce['baseline_sr']:.0%}")
    for cond, models in sorted(ce['conditions'].items()):
        print(f"  {cond}:")
        for m, d in sorted(models.items()):
            print(f"    {m}: {d['avg_cost']:,} / {d['avg_sr']:.0%} (n={d['n']})")

    print("\n=== THRESHOLD (last-day for simple, total for complex) ===")
    for t in sorted(threshold_data, key=lambda x: (x['banks'], x['model'])):
        marker = "✅" if t['cost_delta_pct'] < 0 else "❌"
        print(f"  {marker} {t['banks']}B {t['scenario']:20s} {t['model']:5s}: Δ{t['cost_delta_pct']:+.1f}% cost, Δ{t['sr_delta']:+.2%} SR")


if __name__ == '__main__':
    main()
