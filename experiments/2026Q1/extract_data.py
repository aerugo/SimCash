#!/usr/bin/env python3
"""Extract experiment data for appendix tables."""
import json, os, glob

results_dir = os.path.dirname(__file__) + "/results"
files = sorted(glob.glob(f"{results_dir}/*.json"))

for f in files:
    name = os.path.basename(f)
    if name in ("pipeline.log", "showcase-data.json"):
        continue
    try:
        data = json.load(open(f))
    except:
        print(f"ERROR: {name}")
        continue
    
    exp_id = data.get("experiment_id", "???")
    days = data.get("days", [])
    n_days = len(days)
    
    if not days:
        print(f"{name}\t{exp_id}\t0\t0\t0")
        continue
    
    last = days[-1]
    total_cost = last.get("total_cost", 0)
    
    total_settled = sum(d.get("total_settled", 0) for d in days)
    total_arrivals = sum(d.get("total_arrivals", 0) for d in days)
    sr = total_settled / total_arrivals * 100 if total_arrivals > 0 else 0
    
    print(f"{name}\t{exp_id}\t{total_cost}\t{sr:.1f}\t{n_days}")
