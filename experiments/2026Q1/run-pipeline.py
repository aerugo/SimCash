#!/usr/bin/env python3
"""
SimCash Parallel Experiment Runner
Reads experiment-plan.yaml, runs 2 experiments at a time via API,
polls progress every 60s, updates the YAML in place.
"""

import yaml, json, requests, time, os, sys, threading, copy
from datetime import datetime, timezone

WORKSPACE = "/Users/ned/.openclaw/workspace-stefan"
PLAN_FILE = f"{WORKSPACE}/experiment-plan.yaml"
RESULTS_DIR = f"{WORKSPACE}/api-results"
LOG_FILE = f"{RESULTS_DIR}/pipeline.log"
KEY_FILE = f"{WORKSPACE}/.simcash-api-key"

os.makedirs(RESULTS_DIR, exist_ok=True)

with open(KEY_FILE) as f:
    API_KEY = f.read().strip()

API_BASE = "https://simcash-997004209370.europe-north1.run.app/api/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
MAX_PARALLEL = 2
POLL_INTERVAL = 60

lock = yaml.SafeLoader  # for thread safety on YAML writes
file_lock = threading.Lock()


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def load_plan():
    with open(PLAN_FILE) as f:
        return yaml.safe_load(f)


def save_plan(plan):
    with file_lock:
        with open(PLAN_FILE, "w") as f:
            yaml.dump(plan, f, default_flow_style=False, allow_unicode=True, sort_keys=False, width=120)


def api_get(path):
    try:
        r = requests.get(f"{API_BASE}{path}", headers=HEADERS, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log(f"  API GET {path} error: {e}")
        return None


def api_post(path, data=None):
    try:
        r = requests.post(f"{API_BASE}{path}", headers=HEADERS, json=data, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log(f"  API POST {path} error: {e}")
        return None


def create_experiment(exp):
    """Create an experiment via API, return experiment_id."""
    use_llm = exp.get("use_llm", True)
    payload = {
        "scenario_id": exp["scenario_id"],
        "use_llm": use_llm,
        "rounds": exp["rounds"],
        "starting_fraction": exp.get("starting_fraction", 0.5),
        "num_eval_samples": exp.get("num_eval_samples", 50),
    }
    if use_llm:
        payload["optimization_model"] = exp["optimization_model"]
        payload["constraint_preset"] = exp.get("constraint_preset", "full")
    if exp.get("prompt_profile"):
        payload["prompt_profile"] = exp["prompt_profile"]
    if exp.get("max_policy_proposals"):
        payload["max_policy_proposals"] = exp["max_policy_proposals"]
    result = api_post("/experiments", payload)
    if result and "experiment_id" in result:
        return result["experiment_id"]
    return None


def run_auto_fire_and_forget(exp_id):
    """Start auto endpoint (fire-and-forget — returns immediately, runs in background)."""
    try:
        r = requests.post(
            f"{API_BASE}/experiments/{exp_id}/auto",
            headers=HEADERS,
            timeout=30,
        )
        return r.status_code == 200
    except Exception as e:
        log(f"  Auto-run start error for {exp_id}: {e}")
        return False


def wait_for_completion(exp_id, name):
    """Poll until experiment completes, handling stalls."""
    while True:
        status = get_progress(exp_id)
        if not status:
            time.sleep(POLL_INTERVAL)
            continue

        st = status.get("status", "?")
        cr = status.get("current_round", "?")
        rounds = status.get("rounds", "?")

        if st in ("complete", "degraded"):
            return True
        elif st == "stalled":
            stall_reason = status.get("stall_reason", "unknown")
            log(f"  ⏸️ {name}: stalled ({stall_reason}) — waiting 180s then resuming...")
            time.sleep(180)
            api_post(f"/experiments/{exp_id}/resume")
            continue
        elif st == "failed":
            return False

        # Day-level progress from partial results
        day_info = ""
        partial = get_results(exp_id)
        if partial and partial.get("days"):
            n_days = len(partial["days"])
            day_info = f", day {n_days}"
        log(f"  ⏳ {name}: round {cr}/{rounds}{day_info} [{st}]")
        time.sleep(POLL_INTERVAL)


def get_progress(exp_id):
    """Poll experiment status."""
    return api_get(f"/experiments/{exp_id}")


def get_results(exp_id):
    """Get full results."""
    return api_get(f"/experiments/{exp_id}/results")


def safe_name(name):
    """Make a filesystem-safe name."""
    return name.lower().replace(" ", "_").replace("—", "-").replace("/", "_")


def resume_experiment(exp, plan, idx):
    """Resume monitoring an already-running experiment (after script restart)."""
    name = exp["name"]
    exp_id = exp["experiment_id"]

    # The auto endpoint may or may not still be active server-side.
    # Poll until complete, and if it stalls, re-trigger auto.
    last_round = -1
    stall_count = 0
    stall_ticks = 0

    while True:
        status = get_progress(exp_id)
        if not status:
            time.sleep(POLL_INTERVAL)
            continue

        st = status.get("status", "?")
        cr = status.get("current_round", 0)

        if st == "complete" or st == "degraded":
            break
        elif st == "stalled":
            stall_reason = status.get("stall_reason", "unknown")
            log(f"  ⏸️ {name} stalled: {stall_reason} — waiting 180s then resuming...")
            time.sleep(180)
            api_post(f"/experiments/{exp_id}/resume")
            continue
        elif st == "failed":
            log(f"❌ {name} ({exp_id}) failed on server")
            exp["status"] = "failed"
            exp["completed_at"] = datetime.now(timezone.utc).isoformat()
            save_plan(plan)
            return

        # Check day-level progress from partial results
        partial = get_results(exp_id)
        n_days = len(partial["days"]) if partial and partial.get("days") else 0
        progress_key = (cr, n_days)

        if progress_key == (last_round, stall_count):
            stall_ticks += 1
            if stall_ticks >= 10:  # 10 minutes of no progress at all
                log(f"  ⚠️ {name} stalled at round {cr} day {n_days}, re-triggering auto...")
                api_post(f"/experiments/{exp_id}/auto")
                stall_ticks = 0
        else:
            stall_ticks = 0
            last_round = cr
            stall_count = n_days

        day_info = f", day {n_days}" if n_days else ""
        log(f"  ⏳ {name}: round {cr}/{status.get('rounds','?')}{day_info} [{st}]")
        time.sleep(POLL_INTERVAL)

    # Collect results
    results = get_results(exp_id)
    if results:
        result_file = f"{RESULTS_DIR}/{safe_name(name)}.json"
        with open(result_file, "w") as f:
            json.dump(results, f)

        days = results.get("days", [])
        if days:
            last_day = days[-1]
            # Sum costs across ALL days (each day is independent, not cumulative)
            total_cost = 0
            for day in days:
                day_costs = day.get("costs", {})
                total_cost += sum(c.get("total", 0) for c in day_costs.values())
            settlement = last_day.get("settlement", {}).get("system", {}).get("rate")
            exp["final_cost"] = total_cost
            exp["settlement_rate"] = settlement
            exp["result_file"] = result_file
            # Verify no negative costs (bug check for rev 00168+)
            neg_days = [d["day"] for d in days if d.get("total_cost", 0) < 0]
            if neg_days:
                log(f"⚠️ WARNING: Negative costs on days {neg_days} for {name}")

        exp["status"] = "complete"
        exp["completed_at"] = datetime.now(timezone.utc).isoformat()
        save_plan(plan)
        log(f"✅ COMPLETE {name}: cost={exp.get('final_cost')}, settlement={exp.get('settlement_rate')}")
    else:
        exp["status"] = "failed"
        exp["completed_at"] = datetime.now(timezone.utc).isoformat()
        save_plan(plan)
        log(f"❌ FAILED to get results for {name}")


def run_single_experiment(exp, plan, idx):
    """Run one experiment end-to-end: create, auto, collect results, update plan."""
    name = exp["name"]
    model_label = exp.get('optimization_model', 'no-LLM')
    log(f"🚀 LAUNCH [{idx+1}] {name} ({model_label})")

    # Create
    exp_id = create_experiment(exp)
    if not exp_id:
        log(f"❌ FAILED to create {name}")
        exp["status"] = "failed"
        exp["completed_at"] = datetime.now(timezone.utc).isoformat()
        save_plan(plan)
        return

    exp["experiment_id"] = exp_id
    exp["status"] = "running"
    exp["started_at"] = datetime.now(timezone.utc).isoformat()
    save_plan(plan)
    log(f"  Created {exp_id} for {name}")

    # Fire-and-forget auto start
    if not run_auto_fire_and_forget(exp_id):
        log(f"❌ FAILED to start auto for {name} ({exp_id})")
        exp["status"] = "failed"
        exp["completed_at"] = datetime.now(timezone.utc).isoformat()
        save_plan(plan)
        return

    # Poll until completion
    success = wait_for_completion(exp_id, name)

    # Collect results
    if success:
        # Check final status for quality info
        final_status = get_progress(exp_id)
        quality = final_status.get("quality", "ok") if final_status else "unknown"
        opt_summary = final_status.get("optimization_summary", {}) if final_status else {}
        if quality == "degraded":
            log(f"  ⚠️ {name} completed with degraded quality: {opt_summary.get('failed', '?')} failed optimizations")
        results = get_results(exp_id)
        if results:
            result_file = f"{RESULTS_DIR}/{safe_name(name)}.json"
            with open(result_file, "w") as f:
                json.dump(results, f)

            # Extract summary — sum costs across ALL days
            days = results.get("days", [])
            if days:
                last_day = days[-1]
                total_cost = 0
                for day in days:
                    day_costs = day.get("costs", {})
                    total_cost += sum(c.get("total", 0) for c in day_costs.values())
                settlement = last_day.get("settlement", {}).get("system", {}).get("rate")

                exp["final_cost"] = total_cost
                exp["settlement_rate"] = settlement
                exp["result_file"] = result_file
                # Verify no negative costs
                neg_days = [d["day"] for d in days if d.get("total_cost", 0) < 0]
                if neg_days:
                    log(f"⚠️ WARNING: Negative costs on days {neg_days} for {name}")

            exp["status"] = "complete"
            exp["completed_at"] = datetime.now(timezone.utc).isoformat()
            save_plan(plan)
            log(f"✅ COMPLETE {name}: cost={exp.get('final_cost')}, settlement={exp.get('settlement_rate')}, file={result_file}")
        else:
            exp["status"] = "failed"
            exp["completed_at"] = datetime.now(timezone.utc).isoformat()
            save_plan(plan)
            log(f"❌ FAILED to get results for {name} ({exp_id})")
    else:
        exp["status"] = "failed"
        exp["completed_at"] = datetime.now(timezone.utc).isoformat()
        save_plan(plan)
        log(f"❌ FAILED auto-run for {name} ({exp_id})")


def main():
    log("=" * 60)
    log("SimCash Pipeline Starting")
    log("=" * 60)

    plan = load_plan()
    experiments = plan.get("experiments", [])

    # Resume any experiments that were already running (e.g. after script restart)
    running = [(i, e) for i, e in enumerate(experiments) if e["status"] == "running" and e.get("experiment_id")]
    pending = [(i, e) for i, e in enumerate(experiments) if e["status"] == "pending"]
    log(f"Found {len(running)} running, {len(pending)} pending experiments, {MAX_PARALLEL} parallel slots")

    active_threads = []

    # Resume running experiments first
    for idx, exp in running:
        log(f"🔄 RESUMING [{idx+1}] {exp['name']} ({exp['experiment_id']})")
        t = threading.Thread(
            target=resume_experiment,
            args=(exp, plan, idx),
            daemon=True,
        )
        t.start()
        active_threads.append(t)

    while pending or active_threads:
        # Clean up finished threads
        active_threads = [t for t in active_threads if t.is_alive()]

        # Peek at next pending experiment
        if pending and not active_threads:
            # No active threads — safe to launch anything
            pass
        elif pending and pending[0][1].get("exclusive"):
            # Next experiment is exclusive — wait for all active to drain
            if active_threads:
                time.sleep(10)
                continue
        elif pending and active_threads:
            # Next experiment is parallel — check if any active are exclusive
            any_exclusive = False  # can't easily check, but if active_threads exist and next is not exclusive, fill slots
            pass

        # Launch new experiments to fill slots
        while pending:
            next_idx, next_exp = pending[0]
            is_exclusive = next_exp.get("exclusive", False)

            if is_exclusive:
                # Exclusive: only launch if no other experiments running
                if active_threads:
                    break  # wait for active to finish
                log(f"  🔒 Running exclusive (no parallel): {next_exp['name']}")
                pending.pop(0)
                t = threading.Thread(
                    target=run_single_experiment,
                    args=(next_exp, plan, next_idx),
                    daemon=True,
                )
                t.start()
                active_threads.append(t)
                break  # don't launch anything else alongside exclusive
            else:
                # Normal: fill up to max_parallel
                if len(active_threads) >= MAX_PARALLEL:
                    break
                pending.pop(0)
                t = threading.Thread(
                    target=run_single_experiment,
                    args=(next_exp, plan, next_idx),
                    daemon=True,
                )
                t.start()
                active_threads.append(t)
                time.sleep(2)

        # Wait a bit before checking again
        time.sleep(10)

    log("=" * 60)
    log("PIPELINE COMPLETE — all experiments done")
    log("=" * 60)

    # Final summary
    plan = load_plan()
    for exp in plan.get("experiments", []):
        status_emoji = "✅" if exp["status"] == "complete" else "❌" if exp["status"] == "failed" else "⏳"
        log(f"  {status_emoji} {exp['name']}: {exp['status']} cost={exp.get('final_cost')} settlement={exp.get('settlement_rate')}")


if __name__ == "__main__":
    main()
