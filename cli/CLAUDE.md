# CLI Tool - Payment Simulator Terminal Interface

## You Are Here: `/cli`

This is the **command-line interface** for the payment simulator. It provides terminal-based access to simulation functionality for debugging, scripting, and direct interaction.

**Your role**: You're an expert in building user-friendly CLI tools with Rust using clap, with a focus on clear output formatting and intuitive commands.

---

## 🎯 Quick Reference

### Project Structure
```
cli/
├── src/
│   ├── main.rs              ← Entry point, clap configuration
│   ├── commands/            ← Command implementations
│   │   ├── mod.rs
│   │   ├── create.rs        ← Create simulation
│   │   ├── tick.rs          ← Advance simulation
│   │   ├── submit.rs        ← Submit transaction
│   │   ├── state.rs         ← Query state
│   │   └── replay.rs        ← Replay with seed
│   └── display/             ← Output formatting
│       ├── mod.rs
│       ├── formatters.rs    ← Pretty printing
│       └── tables.rs        ← Tabular output
├── tests/
│   └── cli_tests.rs         ← CLI integration tests
└── Cargo.toml
```

---

## 🔴 CLI-Specific Critical Rules

### 1. User Experience First

```rust
// ✅ GOOD: Clear, helpful messages
fn handle_error(err: SimulationError) {
    eprintln!("Error: {}", err);
    eprintln!("Hint: Check that all agent IDs exist in the configuration");
    std::process::exit(1);
}

// ❌ BAD: Cryptic error
fn handle_error(err: SimulationError) {
    eprintln!("{:?}", err);  // Debug output is not user-friendly
    std::process::exit(1);
}
```

**Rule**: CLI users see your output directly. Make it helpful, not cryptic.

### 2. Consistent Output Format

```rust
// ✅ GOOD: Structured output
#[derive(Serialize)]
struct TickOutput {
    tick: usize,
    day: usize,
    arrivals: usize,
    settlements: usize,
    queued: usize,
}

// Support both human-readable and JSON
if args.json {
    println!("{}", serde_json::to_string_pretty(&output)?);
} else {
    println!("Tick {}/{}: {} arrivals, {} settlements, {} queued",
        output.tick, output.day, output.arrivals, output.settlements, output.queued);
}
```

**Rule**: Always support both human-readable and machine-parseable (JSON) output.

### 3. Scriptability

```rust
// ✅ GOOD: Exit codes and piping support
fn main() {
    let result = run_command();
    
    match result {
        Ok(output) => {
            println!("{}", output);
            std::process::exit(0);  // Success
        }
        Err(err) => {
            eprintln!("{}", err);
            std::process::exit(1);  // Failure
        }
    }
}

// ❌ BAD: Always exit 0
fn main() {
    let result = run_command();
    println!("{:?}", result);
    // Exits 0 even on errors!
}
```

**Rule**: Proper exit codes enable shell scripting and CI integration.

### 4. Progressive Verbosity

```rust
// ✅ GOOD: Control output verbosity
if verbose >= 2 {
    println!("DEBUG: Processing transaction {}", tx.id);
}
if verbose >= 1 {
    println!("INFO: Settled {} transactions", count);
}
// Always show critical info
println!("Settlement rate: {:.2}%", rate * 100.0);
```

**Rule**: Support `-v`, `-vv`, `-vvv` for increasing detail levels.

---

## Common CLI Patterns

### Pattern 1: Clap Command Structure

```rust
use clap::{Parser, Subcommand};

#[derive(Parser)]
#[command(name = "paysim")]
#[command(about = "Payment Simulator CLI", long_about = None)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
    
    /// Enable verbose output
    #[arg(short, long, action = clap::ArgAction::Count)]
    verbose: u8,
    
    /// Output in JSON format
    #[arg(long)]
    json: bool,
}

#[derive(Subcommand)]
enum Commands {
    /// Create a new simulation from config file
    Create {
        /// Path to configuration file
        #[arg(short, long)]
        config: String,
        
        /// Override simulation seed
        #[arg(short, long)]
        seed: Option<u64>,
    },
    
    /// Advance simulation by one or more ticks
    Tick {
        /// Number of ticks to advance
        #[arg(default_value = "1")]
        count: usize,
    },
    
    /// Submit a transaction to the simulation
    Submit {
        /// Sender agent ID
        sender: String,
        
        /// Receiver agent ID
        receiver: String,
        
        /// Amount in dollars (converted to cents internally)
        #[arg(value_parser = parse_dollars)]
        amount: i64,
    },
    
    /// Display current simulation state
    State {
        /// Show only specific agent
        #[arg(short, long)]
        agent: Option<String>,
    },
}

fn parse_dollars(s: &str) -> Result<i64, String> {
    let dollars: f64 = s.parse()
        .map_err(|_| format!("Invalid amount: {}", s))?;
    Ok((dollars * 100.0).round() as i64)
}
```

**Key points**:
- Use `clap` derive macros for clean command definition
- Provide help text for every command and argument
- Support common flags: `-v`, `--json`, `--help`
- Parse user-friendly formats (dollars) to internal format (cents)

### Pattern 2: Pretty Output Formatting

```rust
use comfy_table::{Table, Row, Cell, presets::UTF8_FULL};

fn display_agent_state(agents: &[Agent]) {
    let mut table = Table::new();
    table.load_preset(UTF8_FULL);
    table.set_header(vec!["Agent", "Balance", "Credit", "Queue Size", "Status"]);
    
    for agent in agents {
        table.add_row(vec![
            Cell::new(&agent.id),
            Cell::new(format_money(agent.balance)),
            Cell::new(format_money(agent.credit_limit)),
            Cell::new(agent.queue.len()),
            Cell::new(agent_status(&agent)),
        ]);
    }
    
    println!("{}", table);
}

fn format_money(cents: i64) -> String {
    format!("${}.{:02}", cents / 100, cents.abs() % 100)
}

fn agent_status(agent: &Agent) -> &str {
    if agent.balance < 0 {
        "⚠️  Overdraft"
    } else if agent.queue.is_empty() {
        "✅ Idle"
    } else {
        "⏳ Queued"
    }
}
```

**Key points**:
- Use `comfy-table` for beautiful tabular output
- Format money as dollars for humans (internal: cents)
- Use emojis sparingly for status indicators
- Align columns for readability

### Pattern 3: JSON Output Support

```rust
use serde::{Serialize, Deserialize};

#[derive(Serialize)]
struct StateOutput {
    tick: usize,
    day: usize,
    agents: Vec<AgentSummary>,
    transactions: TransactionSummary,
}

#[derive(Serialize)]
struct AgentSummary {
    id: String,
    balance: i64,
    credit_limit: i64,
    queue_size: usize,
}

fn output_state(state: &SimulationState, json: bool) {
    if json {
        let output = StateOutput {
            tick: state.time.current_tick,
            day: state.time.current_day,
            agents: state.agents.values()
                .map(|a| AgentSummary {
                    id: a.id.clone(),
                    balance: a.balance,
                    credit_limit: a.credit_limit,
                    queue_size: a.queue.len(),
                })
                .collect(),
            transactions: /* ... */,
        };
        
        println!("{}", serde_json::to_string_pretty(&output).unwrap());
    } else {
        display_agent_state(&state.agents.values().collect());
    }
}
```

**Key points**:
- Create serializable output structs
- Always use `to_string_pretty` for human-readable JSON
- Maintain same information in both formats
- JSON output enables piping to `jq`, `grep`, etc.

### Pattern 4: Interactive Prompts (Optional)

```rust
use dialoguer::{Confirm, Input, Select};

fn confirm_destructive_action() -> bool {
    Confirm::new()
        .with_prompt("This will reset all agent balances. Continue?")
        .default(false)
        .interact()
        .unwrap_or(false)
}

fn prompt_for_agent(available: &[String]) -> String {
    Select::new()
        .with_prompt("Select agent")
        .items(available)
        .interact()
        .map(|idx| available[idx].clone())
        .unwrap_or_else(|_| {
            eprintln!("Selection cancelled");
            std::process::exit(1);
        })
}
```

**When to use**:
- ✅ Destructive operations (delete, reset)
- ✅ Interactive mode (`--interactive` flag)
- ❌ Normal operations (breaks scriptability)
- ❌ Any operation that should work in CI

---

## CLI-Specific Testing

### Integration Tests

```rust
// tests/cli_tests.rs
use assert_cmd::Command;
use predicates::prelude::*;

#[test]
fn test_create_simulation() {
    let mut cmd = Command::cargo_bin("paysim").unwrap();
    
    cmd.arg("create")
        .arg("--config")
        .arg("../config/simple.yaml")
        .assert()
        .success()
        .stdout(predicate::str::contains("Simulation created"));
}

#[test]
fn test_invalid_config_shows_error() {
    let mut cmd = Command::cargo_bin("paysim").unwrap();
    
    cmd.arg("create")
        .arg("--config")
        .arg("nonexistent.yaml")
        .assert()
        .failure()
        .stderr(predicate::str::contains("not found"));
}

#[test]
fn test_json_output() {
    let mut cmd = Command::cargo_bin("paysim").unwrap();
    
    cmd.arg("state")
        .arg("--json")
        .assert()
        .success()
        .stdout(predicate::str::is_json());
}

#[test]
fn test_tick_advances_simulation() {
    let mut cmd = Command::cargo_bin("paysim").unwrap();
    
    // Create simulation
    cmd.arg("create")
        .arg("--config")
        .arg("../config/simple.yaml")
        .assert()
        .success();
    
    // Advance one tick
    let mut cmd = Command::cargo_bin("paysim").unwrap();
    cmd.arg("tick")
        .assert()
        .success()
        .stdout(predicate::str::contains("Tick 1"));
}
```

**Key points**:
- Use `assert_cmd` for CLI testing
- Test both success and failure cases
- Verify output format (JSON, tables)
- Test exit codes

### Snapshot Testing

```rust
use insta::assert_snapshot;

#[test]
fn test_state_output_format() {
    let output = get_state_output();
    assert_snapshot!(output);
}
```

**When to use**:
- ✅ Complex formatted output (tables, reports)
- ✅ Regression detection
- ❌ Simple success/failure checks
- ❌ Non-deterministic output

---

## Common CLI Mistakes

### ❌ Mistake 1: Panic in CLI

```rust
// BAD: Panic on error
fn load_config(path: &str) -> Config {
    std::fs::read_to_string(path).unwrap()  // Panics!
}

// GOOD: Handle gracefully
fn load_config(path: &str) -> Result<Config, CliError> {
    std::fs::read_to_string(path)
        .map_err(|e| CliError::ConfigNotFound {
            path: path.to_string(),
            reason: e.to_string(),
        })?;
    // ...
}
```

### ❌ Mistake 2: Inconsistent Output

```rust
// BAD: Mixed formats
println!("Success!");
println!("{:?}", result);  // Debug format
println!("Done");

// GOOD: Consistent format
if json {
    println!("{}", serde_json::to_string_pretty(&result)?);
} else {
    println!("✅ Success: {}", format_result(&result));
}
```

### ❌ Mistake 3: No Progress Indication

```rust
// BAD: Silent long operation
for i in 0..1000 {
    orchestrator.tick();
}

// GOOD: Show progress
use indicatif::ProgressBar;

let pb = ProgressBar::new(1000);
for i in 0..1000 {
    orchestrator.tick();
    pb.inc(1);
}
pb.finish_with_message("Done");
```

### ❌ Mistake 4: Ignoring Signals

```rust
// BAD: Can't interrupt
loop {
    orchestrator.tick();
}

// GOOD: Handle Ctrl+C
use ctrlc;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};

let running = Arc::new(AtomicBool::new(true));
let r = running.clone();

ctrlc::set_handler(move || {
    r.store(false, Ordering::SeqCst);
}).expect("Error setting Ctrl-C handler");

while running.load(Ordering::SeqCst) {
    orchestrator.tick();
}
println!("\nInterrupted by user");
```

---

## Example Commands

### Create Simulation

```bash
# From config file
paysim create --config config/simple.yaml

# Override seed for different run
paysim create --config config/simple.yaml --seed 54321

# JSON output for scripting
paysim create --config config/simple.yaml --json
```

### Run Simulation

```bash
# Single tick
paysim tick

# Multiple ticks
paysim tick 100

# With verbose output
paysim tick 10 -vv

# JSON output
paysim tick --json
```

### Submit Transaction

```bash
# Amount in dollars (converted to cents)
paysim submit BANK_A BANK_B 1000.50

# With priority
paysim submit BANK_A BANK_B 1000 --priority 8

# Divisible payment
paysim submit BANK_A BANK_B 5000 --divisible
```

### Query State

```bash
# All agents
paysim state

# Specific agent
paysim state --agent BANK_A

# JSON for parsing
paysim state --json | jq '.agents[] | select(.balance < 0)'
```

### Replay Simulation

```bash
# Replay with same seed
paysim replay --seed 12345 --ticks 100

# Compare two runs
paysim replay --seed 12345 --ticks 100 --json > run1.json
paysim replay --seed 12345 --ticks 100 --json > run2.json
diff run1.json run2.json  # Should be identical!
```

---

## CLI Architecture

### Command Flow

```
User Input
    ↓
Clap Parsing
    ↓
Command Handler (commands/*)
    ↓
Backend Interaction (use payment_simulator_core_rs)
    ↓
Format Output (display/*)
    ↓
Print to stdout/stderr
    ↓
Exit with code
```

### Key Design Principles

1. **Separation**: Parse args → Execute → Format → Output
2. **Reusability**: Formatters used across multiple commands
3. **Testability**: Each layer testable independently
4. **Scriptability**: JSON output, exit codes, piping support

---

## Dependencies

```toml
[dependencies]
# Backend simulation engine
payment-simulator-core-rs = { path = "../backend" }

# CLI framework
clap = { version = "4.5", features = ["derive"] }

# Output formatting
comfy-table = "7.1"
colored = "2.1"
indicatif = "0.17"

# Interactive prompts (optional)
dialoguer = { version = "0.11", optional = true }

# JSON output
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"

# Error handling
anyhow = "1.0"
thiserror = "1.0"

# Testing
[dev-dependencies]
assert_cmd = "2.0"
predicates = "3.1"
insta = "1.39"
```

---

## Checklist Before Committing

- [ ] All commands have `--help` text
- [ ] Both human and JSON output supported
- [ ] Exit codes correct (0 success, 1 error)
- [ ] Error messages are helpful, not cryptic
- [ ] Long operations show progress
- [ ] Ctrl+C handled gracefully
- [ ] Tests cover success and failure cases
- [ ] Money displayed as dollars, internally cents
- [ ] Verbose mode works (-v, -vv, -vvv)
- [ ] CLI compiles and runs independently

---

## CLI vs API vs Frontend

| Feature | CLI | API | Frontend |
|---------|-----|-----|----------|
| User | Developer/scripter | Programs | End users |
| Output | Terminal (text/tables) | JSON (HTTP) | Visual (charts) |
| Input | Args/flags | HTTP requests | Forms/buttons |
| Testing | assert_cmd | httptest | playwright |
| Errors | stderr + exit code | HTTP status | Alert/toast |

**When to use CLI**:
- ✅ Debugging during development
- ✅ Automated scripts and CI
- ✅ Quick one-off simulations
- ✅ Comparing runs deterministically
- ❌ Production monitoring (use API)
- ❌ Non-technical users (use Frontend)

---

*Last updated: 2025-10-27*
*For Rust core patterns, see `/backend/CLAUDE.md`*
*For general project context, see root `/CLAUDE.md`*