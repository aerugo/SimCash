# Experiment Data

This directory should contain the experiment databases:

- `exp1.db` - 2-Period Deterministic experiment (3 passes)
- `exp2.db` - 12-Period Stochastic experiment (3 passes)
- `exp3.db` - 3-Period Symmetric experiment (3 passes)

## Getting the Data

Copy from the main results directory:

```bash
cp ../../../api/results/exp{1,2,3}.db .
```

Or regenerate by running experiments:

```bash
cd api
payment-sim experiment run configs/exp1_2period.yaml --output ../results/exp1.db
payment-sim experiment run configs/exp2_12period.yaml --output ../results/exp2.db
payment-sim experiment run configs/exp3_joint.yaml --output ../results/exp3.db
```

## Note

These files are excluded from git (see `.gitignore`) because they are large binary files (~20MB each). The paper generation script expects them to exist in this directory.
