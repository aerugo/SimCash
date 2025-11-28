# Exit Codes and Error Handling

This document describes the exit codes returned by the CLI and how errors are handled.

## Exit Code Summary

| Code | Name | Description |
|------|------|-------------|
| `0` | Success | Command completed successfully |
| `1` | Error | General error (config, database, simulation failure) |
| `130` | Interrupted | User interrupted with Ctrl+C (SIGINT) |

---

## Exit Code 0: Success

The command completed successfully without errors.

### Examples

```bash
# Successful simulation
payment-sim run --config scenario.yaml
echo $?  # Output: 0

# Successful database operation
payment-sim db init
echo $?  # Output: 0
```

---

## Exit Code 1: Error

A general error occurred. The error message is printed to stderr.

### Common Causes

#### Configuration Errors

```bash
# Invalid configuration file
payment-sim run --config invalid.yaml
# Error: Invalid configuration: validation error for agent 'BANK_A'...
```

**Causes**:
- Missing required fields
- Invalid field values
- Schema validation failure
- File not found

#### Database Errors

```bash
# Simulation not found
payment-sim replay --simulation-id nonexistent
# Error: Simulation nonexistent not found in database
```

**Causes**:
- Database file not found
- Schema validation failure
- Query errors
- Missing tables

#### Simulation Errors

```bash
# FFI/Rust errors
payment-sim run --config broken.yaml
# Error: Simulation failed: ...
```

**Causes**:
- Rust panic (caught at FFI boundary)
- Invalid state transitions
- Memory allocation failures

#### Command Usage Errors

```bash
# Missing required option
payment-sim run
# Error: Missing option '--config' / '-c'

# Mutually exclusive options
payment-sim run --config cfg.yaml --verbose --event-stream
# Error: --verbose and --event-stream are mutually exclusive

# Filter without mode
payment-sim run --config cfg.yaml --filter-agent BANK_A
# Error: Event filters (--filter-*) require either --verbose or --event-stream mode
```

### Error Output

Errors are printed to stderr with color formatting:

```
[red]✗ Error: <message>[/red]
```

With `--verbose` or without `--quiet`, a stack trace may follow:

```
Traceback (most recent call last):
  File "...", line N, in function
    ...
```

---

## Exit Code 130: Interrupted

The user interrupted the command with Ctrl+C (SIGINT).

### Example

```bash
# User presses Ctrl+C during long simulation
payment-sim run --config large_scenario.yaml
^C
# Error: Interrupted by user
echo $?  # Output: 130
```

### Behavior

When interrupted:
1. Current tick completes (atomic)
2. Partial data may be persisted (if `--persist`)
3. Error message printed to stderr
4. Exit with code 130

### Scripting

Handle interruption in scripts:

```bash
#!/bin/bash
payment-sim run --config scenario.yaml --persist
exit_code=$?

if [ $exit_code -eq 130 ]; then
    echo "Simulation interrupted - partial results may be in database"
elif [ $exit_code -ne 0 ]; then
    echo "Simulation failed with error"
fi
```

---

## Error Handling by Command

### run

| Error | Exit Code | Message |
|-------|-----------|---------|
| Config not found | 1 | `Error: Path '...' does not exist` |
| Invalid config | 1 | `Error: Invalid configuration: ...` |
| Invalid file format | 1 | `Error: Unsupported file format: ...` |
| Mutually exclusive flags | 1 | `Error: --verbose and --event-stream are mutually exclusive` |
| Filter without mode | 1 | `Error: Event filters (--filter-*) require...` |
| Full-replay without persist | 1 | `Error: --full-replay requires --persist` |
| Database error | 1 | `Error: ...` |
| Simulation failure | 1 | `Error: ...` |
| User interrupt | 130 | `Error: Interrupted by user` |

### replay

| Error | Exit Code | Message |
|-------|-----------|---------|
| Simulation not found | 1 | `Error: Simulation ... not found in database` |
| Config not found | 1 | `Error: Configuration not found in database` |
| Invalid tick range | 1 | `Error: Invalid from_tick: ...` |
| Database error | 1 | `Error: ...` |
| User interrupt | 130 | `Error: Interrupted by user` |

### db subcommands

| Error | Exit Code | Message |
|-------|-----------|---------|
| Database init failed | 1 | `✗ Error initializing database: ...` |
| Migration failed | 1 | `✗ Error applying migrations: ...` |
| Validation failed | 1 | `✗ Schema validation failed` |
| Simulation not found | 1 | `✗ Simulation not found: ...` |
| Query error | 1 | `✗ Error: ...` |

### checkpoint subcommands

| Error | Exit Code | Message |
|-------|-----------|---------|
| State file not found | 1 | `Error: State file not found: ...` |
| Invalid JSON | 1 | `Error: Invalid JSON in state file: ...` |
| Config not found | 1 | `Error: Config file not found: ...` |
| Checkpoint not found | 1 | `Error: Checkpoint not found: ...` |
| No checkpoints | 1 | `Error: No checkpoints found for simulation ...` |

### policy-schema

| Error | Exit Code | Message |
|-------|-----------|---------|
| Schema extraction failed | 1 | `Error: ...` |

---

## Error Handling Best Practices

### In Scripts

```bash
#!/bin/bash
set -e  # Exit on error

# Run simulation
if ! payment-sim run --config scenario.yaml --persist; then
    echo "Simulation failed"
    exit 1
fi

# Get simulation ID from output
sim_id=$(payment-sim run --config scenario.yaml --persist --quiet | jq -r '.simulation.simulation_id')

# Replay with error handling
payment-sim replay --simulation-id "$sim_id" --verbose || {
    echo "Replay failed for $sim_id"
    exit 1
}
```

### In CI/CD

```yaml
# GitHub Actions example
- name: Run Simulation
  run: |
    payment-sim run --config scenario.yaml --persist --quiet
  continue-on-error: false

- name: Handle Failure
  if: failure()
  run: |
    echo "Simulation failed - check logs"
```

### Checking Specific Exit Codes

```bash
payment-sim run --config scenario.yaml
exit_code=$?

case $exit_code in
    0)
        echo "Success"
        ;;
    1)
        echo "Error occurred"
        # Check stderr for details
        ;;
    130)
        echo "Interrupted by user"
        ;;
    *)
        echo "Unexpected exit code: $exit_code"
        ;;
esac
```

---

## Quiet Mode Error Handling

With `--quiet`, informational messages are suppressed, but errors still go to stderr:

```bash
# Only errors visible
payment-sim run --config invalid.yaml --quiet 2>&1 | head -1
# Error: Invalid configuration: ...
```

### Separating Output and Errors

```bash
# Capture output and errors separately
payment-sim run --config scenario.yaml --quiet >output.json 2>errors.log

if [ -s errors.log ]; then
    echo "Errors occurred:"
    cat errors.log
fi
```

---

## Debugging Errors

### Verbose Error Output

For detailed error information, don't use `--quiet`:

```bash
# Full error with traceback
payment-sim run --config broken.yaml
```

### Debug Mode

For performance diagnostics with errors:

```bash
payment-sim run --config scenario.yaml --verbose --debug
```

### Check Configuration

Validate configuration before running:

```bash
# Check config syntax
python -c "import yaml; yaml.safe_load(open('scenario.yaml'))"

# Check config structure
payment-sim run --config scenario.yaml --ticks 1 --quiet
```

---

## Related Documentation

- [run Command](commands/run.md) - Run command options
- [Output Modes](output-modes.md) - Output and quiet mode
- [Filtering](filtering.md) - Event filtering options
