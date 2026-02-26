#!/usr/bin/env python3
"""
SimCash Parallel Experiment Runner v2
=====================================
Hardened pipeline using split config/state files, atomic writes,
idempotent launches, graceful shutdown, and proper logging.
"""

import yaml, json, requests, time, os, sys, threading, signal, hashlib, tempfile, copy
from datetime import datetime, timezone

WORKSPACE = "/Users/ned/.openclaw/workspace-stefan"
CONFIG_FILE = f"{WORKSPACE}/experiment-config.yaml"
STATE_FILE = f"{WORKSPACE}/experiment-state.yaml"
RESULTS_DIR = f"{WORKSPACE}/api-results"
LOG_FILE = f"{RESULTS_DIR}/pipeline-v2.log"
KEY_FILE = f"{WORKSPACE}/.simcash-api-key"

os.makedirs(RESULTS_DIR, exist_ok=True)

with open(KEY_FILE) as f:
    API_KEY = f.read().strip()

API_BASE = "https://simcash-997004209370.europe-north1.run.app/api/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

# ─── Globals ────────────────────────────────────────────────────────────────

file_lock = threading.Lock()
shutdown_flag = threading.Event()

# ─── Graceful shutdown (2d) ─────────────────────────────────────────────────

def _shutdown_handler(signum, frame):
    sig_name = signal.Signals(signum).name
    log(f"⚡ Received {sig_name} — finishing current polls, then exiting...")
    shutdown_flag.set()

signal.signal(signal.SIGTERM, _shutdown_handler)
signal.signal(signal.SIGINT, _shutdown_handler)

# ─── Atomic YAML writes (2c) ───────────────────────────────────────────────

def atomic_yaml_write(path, data):
    """Write YAML atomically: write to temp file, then os.rename()."""
    dir_name = os.path.dirname(os.path.abspath(path))
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".yaml.tmp")
    try:
        with os.fdopen(fd, "w") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True,
                      sort_keys=False, width=120)
        os.rename(tmp_path, path)
    except:
        try:
            os.unlink(tmp_path)
        except:
            pass
        raise

# ─── Logging (2a fix: no double-logging) ───────────────────────────────────
# The v1 bug: log() prints to stdout AND writes to file. If the script is run
# with stdout redirected to the same log file (e.g. >> pipeline.log), every
# line appears twice. Fix: write only to log file; print to stderr for console.

_log_lock = threading.Lock()

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    with _log_lock:
        # Write to log file only
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
        # Console output goes to stderr (won't conflict with file redirects)
        print(line, file=sys.stderr, flush=True)

# ─── Config/State helpers ──────────────────────────────────────────────────

def load_config():
    with open(CONFIG_FILE) as f:
        return yaml.safe_load(f)

def load_state():
    with open(STATE_FILE) as f:
        return yaml.safe_load(f) or {"experiments": {}}

def save_state(state):
    with file_lock:
        atomic_yaml_write(STATE_FILE, state)

def get_exp_state(state, name):
    """Get or initialize state entry for an experiment."""
    if name not in state["experiments"]:
        state["experiments"][name] = {"status": "pending"}
    return state["experiments"][name]

# ─── API helpers ───────────────────────────────────────────────────────────

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

# ─── Experiment helpers ────────────────────────────────────────────────────

def safe_name(name):
    return name.lower().replace(" ", "_").replace("\u2014", "-").replace("/", "_")

def create_experiment(exp_config):
    """Create an experiment via API, return experiment_id."""
    use_llm = exp_config.get("use_llm", True)
    payload = {
        "scenario_id": exp_config["scenario_id"],
        "use_llm": use_llm,
        "rounds": exp_config["rounds"],
        "starting_fraction": exp_config.get("starting_fraction", 0.5),
        "num_eval_samples": exp_config.get("num_eval_samples", 50),
    }
    if use_llm:
        payload["optimization_model"] = exp_config["optimization_model"]
        payload["constraint_preset"] = exp_config.get("constraint_preset", "full")
    result = api_post("/experiments", payload)
    if result and "experiment_id" in result:
        return result["experiment_id"]
    return None

def run_auto(exp_id):
    try:
        r = requests.post(f"{API_BASE}/experiments/{exp_id}/auto", headers=HEADERS, timeout=30)
        return r.status_code == 200
    except Exception as e:
        log(f"  Auto-run start error for {exp_id}: {e}")
        return False

def check_experiment_alive(exp_id):
    """Check if an experiment is still running on the API (2b: idempotent launches)."""
    status = api_get(f"/experiments/{exp_id}")
    if status and status.get("status") in ("running", "optimizing", "evaluating", "pending"):
        return True
    return False

def poll_until_done(exp_id, name, state, state_obj):
    """Poll until experiment completes. Handles stalls and shutdown."""
    last_progress = None
    stall_ticks = 0

    while not shutdown_flag.is_set():
        status = api_get(f"/experiments/{exp_id}")
        if not status:
            time.sleep(60)
            continue

        st = status.get("status", "?")
        cr = status.get("current_round", 0)
        rounds = status.get("rounds", "?")

        if st in ("complete", "degraded"):
            return True
        elif st == "stalled":
            stall_reason = status.get("stall_reason", "unknown")
            log(f"  ⏸️ {name}: stalled ({stall_reason}) — waiting 180s then resuming...")
            # Wait 180s but check shutdown every 10s
            for _ in range(18):
                if shutdown_flag.is_set():
                    return None
                time.sleep(10)
            api_post(f"/experiments/{exp_id}/resume")
            continue
        elif st == "failed":
            return False

        # Day-level progress
        partial = api_get(f"/experiments/{exp_id}/results")
        n_days = len(partial["days"]) if partial and partial.get("days") else 0
        progress_key = (cr, n_days)

        if progress_key == last_progress:
            stall_ticks += 1
            if stall_ticks >= 10:
                log(f"  ⚠️ {name} stalled at round {cr} day {n_days}, re-triggering auto...")
                api_post(f"/experiments/{exp_id}/auto")
                stall_ticks = 0
        else:
            stall_ticks = 0
            last_progress = progress_key

        day_info = f", day {n_days}" if n_days else ""
        log(f"  ⏳ {name}: round {cr}/{rounds}{day_info} [{st}]")

        # Interruptible sleep
        for _ in range(6):  # 60s in 10s chunks
            if shutdown_flag.is_set():
                return None
            time.sleep(10)

    return None  # shutdown requested

def collect_results(exp_id, name, state, state_obj):
    """Collect results and update state."""
    es = get_exp_state(state_obj, name)

    # Check quality
    final_status = api_get(f"/experiments/{exp_id}")
    if final_status:
        quality = final_status.get("quality", "ok")
        opt_summary = final_status.get("optimization_summary", {})
        if quality == "degraded":
            log(f"  ⚠️ {name} completed with degraded quality: {opt_summary.get('failed', '?')} failed optimizations")

    results = api_get(f"/experiments/{exp_id}/results")
    if results:
        result_file = f"{RESULTS_DIR}/{safe_name(name)}.json"
        with open(result_file, "w") as f:
            json.dump(results, f)

        # Checksum
        with open(result_file, "rb") as f:
            checksum = hashlib.sha256(f.read()).hexdigest()[:16]

        days = results.get("days", [])
        if days:
            last_day = days[-1]
            costs = last_day.get("costs", {})
            total_cost = sum(c.get("total", 0) for c in costs.values()) if isinstance(costs, dict) else last_day.get("total_cost", 0)
            settlement = last_day.get("settlement", {}).get("system", {}).get("rate")
            es["final_cost"] = total_cost
            es["settlement_rate"] = settlement

        es["result_file"] = result_file
        es["checksum"] = checksum
        es["status"] = "complete"
        es["completed_at"] = datetime.now(timezone.utc).isoformat()
        save_state(state_obj)
        log(f"✅ COMPLETE {name}: cost={es.get('final_cost')}, settlement={es.get('settlement_rate')}")
        return True
    else:
        es["status"] = "failed"
        es["completed_at"] = datetime.now(timezone.utc).isoformat()
        save_state(state_obj)
        log(f"❌ FAILED to get results for {name}")
        return False

# ─── Experiment runners ────────────────────────────────────────────────────

def run_experiment(exp_config, state_obj):
    """Run one experiment end-to-end with idempotent launch."""
    name = exp_config["name"]
    es = get_exp_state(state_obj, name)
    model_label = exp_config.get("optimization_model", "no-LLM")

    # 2b: Idempotent launch — check if already running
    if es.get("experiment_id") and es.get("status") == "running":
        exp_id = es["experiment_id"]
        if check_experiment_alive(exp_id):
            log(f"🔄 RESUMING {name} ({exp_id}) — already running on API")
        else:
            log(f"⚠️ {name} ({exp_id}) was 'running' but not alive on API, re-creating...")
            es["status"] = "pending"
            es.pop("experiment_id", None)

    if es.get("status") == "complete":
        log(f"⏭️ SKIP {name} — already complete")
        return

    # Create if needed
    if not es.get("experiment_id") or es.get("status") == "pending":
        log(f"🚀 LAUNCH {name} ({model_label})")
        exp_id = create_experiment(exp_config)
        if not exp_id:
            log(f"❌ FAILED to create {name}")
            es["status"] = "failed"
            es["completed_at"] = datetime.now(timezone.utc).isoformat()
            save_state(state_obj)
            return
        es["experiment_id"] = exp_id
        es["status"] = "running"
        es["started_at"] = datetime.now(timezone.utc).isoformat()
        save_state(state_obj)
        log(f"  Created {exp_id} for {name}")

        if not run_auto(exp_id):
            log(f"❌ FAILED to start auto for {name} ({exp_id})")
            es["status"] = "failed"
            es["completed_at"] = datetime.now(timezone.utc).isoformat()
            save_state(state_obj)
            return

    exp_id = es["experiment_id"]

    # Poll
    result = poll_until_done(exp_id, name, es, state_obj)

    if result is None:
        # Shutdown requested — leave as running for next restart
        log(f"  ⏸️ {name} interrupted by shutdown — will resume next run")
        save_state(state_obj)
        return
    elif result:
        collect_results(exp_id, name, es, state_obj)
    else:
        es["status"] = "failed"
        es["completed_at"] = datetime.now(timezone.utc).isoformat()
        save_state(state_obj)
        log(f"❌ FAILED {name} ({exp_id})")

# ─── Main loop ─────────────────────────────────────────────────────────────

def main():
    log("=" * 60)
    log("SimCash Pipeline v2 Starting")
    log("=" * 60)

    config = load_config()
    state_obj = load_state()
    settings = config.get("settings", {})
    max_parallel = settings.get("max_parallel", 2)
    experiments = config.get("experiments", [])

    # Categorize
    running = []
    pending = []
    for exp in experiments:
        name = exp["name"]
        es = get_exp_state(state_obj, name)
        if es.get("status") == "running":
            running.append(exp)
        elif es.get("status") in ("pending", None):
            pending.append(exp)

    log(f"Found {len(running)} running, {len(pending)} pending, {max_parallel} parallel slots")

    active_threads = []

    # Resume running experiments
    for exp in running:
        log(f"🔄 RESUMING {exp['name']}")
        t = threading.Thread(target=run_experiment, args=(exp, state_obj), daemon=True)
        t.start()
        active_threads.append(t)

    while (pending or active_threads) and not shutdown_flag.is_set():
        active_threads = [t for t in active_threads if t.is_alive()]

        if not pending:
            time.sleep(10)
            continue

        next_exp = pending[0]
        is_exclusive = next_exp.get("exclusive", False)

        if is_exclusive and active_threads:
            time.sleep(10)
            continue

        if not is_exclusive and len(active_threads) >= max_parallel:
            time.sleep(10)
            continue

        # Launch
        pending.pop(0)
        if is_exclusive:
            log(f"  🔒 Running exclusive: {next_exp['name']}")
        t = threading.Thread(target=run_experiment, args=(next_exp, state_obj), daemon=True)
        t.start()
        active_threads.append(t)

        if is_exclusive:
            # Don't launch anything else alongside exclusive
            while t.is_alive() and not shutdown_flag.is_set():
                time.sleep(10)
            continue

        time.sleep(2)

    # Wait for remaining threads on shutdown
    if shutdown_flag.is_set():
        log("Waiting for active experiments to reach safe state...")
        for t in active_threads:
            t.join(timeout=30)
        save_state(state_obj)
        log("State saved. Exiting gracefully.")
        return

    log("=" * 60)
    log("PIPELINE v2 COMPLETE — all experiments done")
    log("=" * 60)

    # Final summary
    state_obj = load_state()
    for exp in experiments:
        name = exp["name"]
        es = state_obj["experiments"].get(name, {})
        st = es.get("status", "?")
        emoji = "✅" if st == "complete" else "❌" if st == "failed" else "⏳"
        log(f"  {emoji} {name}: {st} cost={es.get('final_cost')} settlement={es.get('settlement_rate')}")


if __name__ == "__main__":
    main()
