#!/usr/bin/env bash
# Custom command: /test-determinism
# Description: Run comprehensive determinism verification tests

set -e

echo "🎲 Running Determinism Verification Tests..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check for float contamination in Rust code
echo ""
echo "1️⃣ Checking for float contamination in money code..."
if rg "f32|f64" backend/src/ --type rust | grep -v "test" | grep -v "debug" | grep -v "log"; then
    echo "❌ FAIL: Found float usage in production code!"
    echo "   Money must always be i64 (cents)"
    exit 1
else
    echo "✅ PASS: No floats found in money code"
fi

# Run Rust determinism tests
echo ""
echo "2️⃣ Running Rust determinism tests..."
cd backend
if cargo test determinism --quiet; then
    echo "✅ PASS: Rust determinism tests passed"
else
    echo "❌ FAIL: Rust determinism tests failed"
    exit 1
fi
cd ..

# Run Python FFI determinism tests
echo ""
echo "3️⃣ Running Python FFI determinism tests..."
if pytest api/tests/integration/test_rust_ffi_determinism.py -v; then
    echo "✅ PASS: Python FFI determinism tests passed"
else
    echo "❌ FAIL: Python FFI determinism tests failed"
    exit 1
fi

# Run determinism stress test (same seed 10 times)
echo ""
echo "4️⃣ Running determinism stress test (10 iterations)..."
python3 <<EOF
from payment_simulator.backends.rust_backend import RustBackend
import yaml

with open('config/simple.yaml') as f:
    config = yaml.safe_load(f)

results = []
for i in range(10):
    backend = RustBackend(config)
    run_results = []
    for _ in range(50):
        run_results.append(backend.tick())
    results.append(run_results)

# All 10 runs should be identical
for i in range(1, 10):
    if results[i] != results[0]:
        print(f"❌ FAIL: Run {i+1} differs from run 1")
        exit(1)

print("✅ PASS: All 10 runs produced identical results")
EOF

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ All determinism checks passed!"
echo ""
echo "Your simulation is deterministic and ready for research use."
