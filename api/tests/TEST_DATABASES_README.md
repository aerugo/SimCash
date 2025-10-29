# Test Databases

This directory contains DuckDB database files created during local test runs.

## Purpose

- **Local debugging**: Databases persist here so you can inspect them after tests
- **Manual inspection**: Query databases with DuckDB CLI or Python
- **Development workflow**: See actual data structures and performance

## Behavior

### ✅ **Test Success** (default)
- Database is **automatically cleaned up**
- Keeps filesystem clean during normal development

### ❌ **Test Failure**
- Database is **kept for debugging**
- You can inspect what went wrong
- Manually delete when done: `rm test_databases/*.db`

### 🔧 **Manual Creation**
- You can create databases here anytime for experiments
- See examples in test files or use DatabaseManager directly

## Usage

### Query a Test Database

```python
# Using Python
import duckdb
conn = duckdb.connect('test_databases/manual_test.db')
result = conn.execute('SELECT * FROM daily_agent_metrics').fetchall()
print(result)
conn.close()
```

```bash
# Using DuckDB CLI (if installed)
duckdb test_databases/manual_test.db
D SELECT agent_id, day, total_cost FROM daily_agent_metrics;
D .tables
D .schema daily_agent_metrics
```

### Create Test Data Manually

```python
from pathlib import Path
from payment_simulator.persistence.connection import DatabaseManager
import polars as pl

# Create database
db_path = Path('test_databases/my_experiment.db')
manager = DatabaseManager(db_path)
manager.setup()

# Insert data
data = [{"simulation_id": "exp1", "agent_id": "BANK_A", ...}]
df = pl.DataFrame(data)
manager.conn.execute('INSERT INTO daily_agent_metrics SELECT * FROM df')

# Query
result = manager.conn.execute('SELECT * FROM daily_agent_metrics').fetchall()
print(result)

manager.close()
```

## CI/CD Behavior

In CI environments (GitHub Actions), tests use temporary directories instead:
- Faster cleanup
- No disk space accumulation
- Complete isolation between test runs

Detected via: `CI=true` or `GITHUB_ACTIONS=true` environment variables

## Files in This Directory

All files are gitignored (see [.gitignore](../.gitignore)):
- `*.db` - DuckDB database files
- `*.db.wal` - Write-Ahead Log files (DuckDB internals)

**Do not commit these files to git!**

## Schema

All databases have the same schema (auto-generated from Pydantic models):

### Tables
- `transactions` - All payment transactions
- `simulation_runs` - Simulation metadata
- `daily_agent_metrics` - Daily agent statistics (Phase 3)
- `collateral_events` - Collateral management events (Phase 8)
- `schema_migrations` - Migration tracking

### Example Queries

```sql
-- See all agent metrics for a simulation
SELECT agent_id, day, opening_balance, closing_balance, total_cost
FROM daily_agent_metrics
WHERE simulation_id = 'sim-12345'
ORDER BY day, agent_id;

-- Check transaction settlement rates
SELECT
    sender_id,
    COUNT(*) as total,
    SUM(CASE WHEN status = 'settled' THEN 1 ELSE 0 END) as settled,
    ROUND(100.0 * SUM(CASE WHEN status = 'settled' THEN 1 ELSE 0 END) / COUNT(*), 2) as settlement_pct
FROM transactions
GROUP BY sender_id;

-- Agent cost breakdown
SELECT
    agent_id,
    SUM(liquidity_cost) as total_liquidity,
    SUM(delay_cost) as total_delay,
    SUM(total_cost) as total_all_costs
FROM daily_agent_metrics
GROUP BY agent_id
ORDER BY total_all_costs DESC;
```

## Cleanup

```bash
# Remove all test databases
rm test_databases/*.db test_databases/*.db.wal

# Keep directory for future tests
# (it will be recreated automatically)
```
