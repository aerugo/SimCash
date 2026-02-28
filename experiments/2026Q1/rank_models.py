#!/usr/bin/env python3
"""
Model ranking analysis for SimCash v0.2 settlement optimization experiments.

Scoring system:
  - Best settlement rate AND best cost: 3 points
  - Best settlement rate AND 2nd best cost: 2 points  
  - Best settlement rate AND worst cost: 1 point
  - Not best settlement rate: 0 points

Groups experiments by (condition, retry_status, run_index) and ranks 
the 3 models against each other within each group.

Usage:
  python3 rank_models.py                          # all v0.2 experiments
  python3 rank_models.py --floor-only             # only conditions with settlement floor
  python3 rank_models.py --plan path/to/plan.yaml # custom plan file
"""

import argparse
import yaml
from collections import defaultdict


def load_experiments(plan_path):
    """Load completed v0.2 experiments from experiment plan."""
    with open(plan_path) as f:
        data = yaml.safe_load(f)
    
    results = []
    for e in data['experiments']:
        if e.get('status') != 'complete':
            continue
        name = e.get('name', '')
        cost = e.get('final_cost')
        sr = e.get('settlement_rate')
        if cost is None or sr is None:
            continue
        
        # Only v0.2 condition experiments
        cond = None
        for c in ['C1-info', 'C2-floor', 'C3-guidance', 'C4-comp']:
            if c in name:
                cond = c
                break
        if not cond:
            continue
        
        m = None
        for pat in ['GLM', 'Flash', 'Pro']:
            if pat in name:
                m = pat
                break
        if not m:
            continue
        
        is_retry = 'retry' in name
        has_floor = cond in ['C2-floor', 'C3-guidance', 'C4-comp']
        
        results.append({
            'name': name, 'cond': cond, 'model': m,
            'cost': cost, 'sr': sr,
            'is_retry': is_retry, 'has_floor': has_floor
        })
    
    return results


def score_models(experiment_list, label):
    """
    Score models across a set of experiments.
    
    Groups by (condition, is_retry) and matches runs by index.
    For each comparison group, ranks models by SR then cost.
    
    Returns dict of {model: points}.
    """
    # Group by (condition, is_retry) then by model
    groups = defaultdict(lambda: defaultdict(list))
    for r in experiment_list:
        key = (r['cond'], r['is_retry'])
        groups[key][r['model']].append(r)
    
    points = defaultdict(int)
    comparisons = 0
    details = []
    
    for (cond, is_retry), model_runs in sorted(groups.items()):
        retry_tag = "retry" if is_retry else "no-retry"
        max_runs = max(len(v) for v in model_runs.values()) if model_runs else 0
        
        for run_idx in range(max_runs):
            run_data = {}
            for m in ['GLM', 'Flash', 'Pro']:
                if m in model_runs and run_idx < len(model_runs[m]):
                    run_data[m] = model_runs[m][run_idx]
            
            if len(run_data) < 2:
                continue
            comparisons += 1
            
            # Rank by SR (higher is better)
            sr_ranked = sorted(run_data.items(), key=lambda x: -x[1]['sr'])
            # Rank by cost (lower is better)
            cost_ranked = sorted(run_data.items(), key=lambda x: x[1]['cost'])
            
            best_sr_val = sr_ranked[0][1]['sr']
            best_sr_models = [m for m, r in run_data.items() if r['sr'] == best_sr_val]
            
            cost_rank = {m: i for i, (m, _) in enumerate(cost_ranked)}
            
            for m in best_sr_models:
                cr = cost_rank[m]
                if cr == 0:
                    pts = 3
                    tag = "3pts (best SR + best cost)"
                elif cr == 1:
                    pts = 2
                    tag = "2pts (best SR + 2nd cost)"
                else:
                    pts = 1
                    tag = "1pt (best SR + worst cost)"
                points[m] += pts
                details.append(
                    f"  {cond:<14} {retry_tag:<10} r{run_idx+1}: "
                    f"{m:<6} {tag}  "
                    f"(SR={run_data[m]['sr']:.0%}, cost={run_data[m]['cost']:,})"
                )
    
    # Print results
    print(f"\n{'='*65}")
    print(f"  {label}")
    print(f"{'='*65}")
    print(f"  Comparisons: {comparisons} (condition × retry_status × run)\n")
    print(f"  {'Model':<8} {'Points':>8} {'Max':>8} {'Score':>8}")
    print(f"  {'-'*36}")
    for m in ['GLM', 'Flash', 'Pro']:
        max_pts = comparisons * 3
        pct = points[m] / max_pts * 100 if max_pts else 0
        print(f"  {m:<8} {points[m]:>8} {max_pts:>8} {pct:>7.0f}%")
    
    print(f"\n  Breakdown:")
    for d in details:
        print(d)
    
    return points


def main():
    parser = argparse.ArgumentParser(description='Rank models by settlement + cost')
    parser.add_argument('--plan', default='experiment-plan.yaml',
                        help='Path to experiment-plan.yaml')
    parser.add_argument('--floor-only', action='store_true',
                        help='Only score conditions with settlement floor (C2/C3/C4)')
    parser.add_argument('--no-retry', action='store_true',
                        help='Only score no-retry experiments')
    parser.add_argument('--retry-only', action='store_true',
                        help='Only score retry experiments')
    parser.add_argument('--quiet', action='store_true',
                        help='Only show summary, no breakdown')
    args = parser.parse_args()
    
    results = load_experiments(args.plan)
    
    if args.floor_only:
        results = [r for r in results if r['has_floor']]
    if args.no_retry:
        results = [r for r in results if not r['is_retry']]
    if args.retry_only:
        results = [r for r in results if r['is_retry']]
    
    print(f"Loaded {len(results)} experiments")
    model_counts = ', '.join(f'{m}={sum(1 for r in results if r["model"]==m)}' for m in ['GLM','Flash','Pro'])
    cond_counts = ', '.join(f'{c}={sum(1 for r in results if r["cond"]==c)}' for c in ['C1-info','C2-floor','C3-guidance','C4-comp'] if any(r['cond']==c for r in results))
    retry_count = sum(1 for r in results if r['is_retry'])
    no_retry_count = sum(1 for r in results if not r['is_retry'])
    print(f"  Models: {model_counts}")
    print(f"  Conditions: {cond_counts}")
    print(f"  Retry: {retry_count}, No-retry: {no_retry_count}")
    
    # Build label
    parts = []
    if args.floor_only:
        parts.append("FLOOR ONLY (C2/C3/C4)")
    else:
        parts.append("ALL CONDITIONS (C1-C4)")
    if args.no_retry:
        parts.append("no-retry only")
    elif args.retry_only:
        parts.append("retry only")
    else:
        parts.append("retry + no-retry")
    label = " — ".join(parts)
    
    score_models(results, label)


if __name__ == '__main__':
    main()
