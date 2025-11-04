# Building the Payment Simulator

## Quick Start (One Command Setup!)

From the `api` directory:

```bash
# Setup everything: dependencies + Rust module build + editable install
uv sync --extra dev

# Run tests
.venv/bin/python -m pytest
```

That's it! `uv sync --extra dev` handles everything automatically.

## What Happens Automatically

When you run `uv sync --extra dev`, the following happens:

1. **Maturin** (configured in `pyproject.toml`) is invoked as the build backend
2. **Rust compilation**: The backend Rust code is compiled with PyO3 bindings
3. **Python extension**: A `.so` file (`payment_simulator_core_rs`) is generated
4. **Package installation**: The package is installed in editable mode, so code changes are immediately available

## Configuration Details

### pyproject.toml

The key configuration that makes this work:

```toml
[build-system]
requires = ["maturin>=1.9.6"]
build-backend = "maturin"

[tool.maturin]
module-name = "payment_simulator_core_rs"
manifest-path = "../backend/Cargo.toml"
features = ["pyo3"]
bindings = "pyo3"
```

This tells `uv` to use `maturin` to build the package, which automatically compiles the Rust code.

### backend/src/lib.rs

The Rust module exports via PyO3:

```rust
#[cfg(feature = "pyo3")]
#[pymodule]
fn payment_simulator_core_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<ffi::orchestrator::PyOrchestrator>()?;
    Ok(())
}
```

Note: The function name must match the `module-name` in `pyproject.toml`.

## Common Commands

```bash
# Initial setup
uv sync --extra dev

# Rebuild after Rust changes (two options):
# Option 1 (recommended): Use uv sync with reinstall flag
uv sync --extra dev --reinstall-package payment-simulator

# Option 2: Direct reinstall (faster, but doesn't sync dependencies)
uv pip install -e . --force-reinstall --no-deps

# Run all tests
.venv/bin/python -m pytest

# Run specific tests
.venv/bin/python -m pytest tests/ffi/test_determinism.py -v

# Run with coverage
.venv/bin/python -m pytest --cov=payment_simulator --cov-report=html

# Check what's installed
uv pip list | grep payment
```

## Troubleshooting

### Import Error: "No module named 'payment_simulator_core_rs'"

**Solution**: Run `uv sync --extra dev` to build and install the Rust module.

### Tests not found or wrong Python version

**Solution**: Use `.venv/bin/python -m pytest` instead of just `pytest` to ensure you're using the correct virtual environment.

### Rust compilation errors

**Solution**: Make sure you have Rust toolchain installed:
```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

### Module name mismatch

If you see "dynamic module does not define module export function", ensure:
1. The `#[pymodule]` function name in `backend/src/lib.rs` matches
2. The `module-name` in `api/pyproject.toml`

Both should be `payment_simulator_core_rs`.

## Why This Approach?

**Integrated Build**: Instead of manually running `maturin build` and installing wheels, the build is integrated into the Python package installation process.

**Developer Convenience**: One command (`uv pip install -e .`) handles everything - no need to remember separate Rust and Python build steps.

**Automatic Rebuilds**: When you make Rust changes, just run `uv pip install -e . --force-reinstall --no-deps` to rebuild.

**Virtual Environment**: Everything is contained in `.venv`, making the setup reproducible and isolated.
