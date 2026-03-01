# Experiments

*Replicating Castro et al. (2025)*

SimCash implements three canonical scenarios from Castro et al. (2025), each designed to
test different aspects of multi-agent coordination:

## Experiment 1: Asymmetric Equilibrium

| Property | Value |
|----------|-------|
| Ticks | 2 per day |
| Payments | Asymmetric — A sends 15% at tick 1; B sends 15% at tick 0, 5% at tick 1 |
| Mode | Deterministic-temporal |
| Expected | Asymmetric: A≈0%, B≈20% |
| Result | A=0.1%, B=17% — matches prediction ✓ |

Bank A free-rides on Bank B's liquidity provision. B must commit reserves to settle
payments to A, which then gives A incoming liquidity to fund its own obligations.

## Experiment 2: Stochastic Coordination

| Property | Value |
|----------|-------|
| Ticks | 12 per day |
| Payments | Poisson arrivals (λ=2/tick), LogNormal amounts (μ=$100, σ=$50) |
| Mode | Bootstrap (50 paired samples) |
| Expected | Near-symmetric convergence |
| Result | A≈5.7–8.5%, B≈5.8–6.3% across 3 passes (near-symmetric) |

The flagship experiment. Stochastic arrivals create genuine uncertainty, and bootstrap
evaluation ensures statistical rigor in policy comparison.

## Experiment 3: Symmetric Coordination

| Property | Value |
|----------|-------|
| Ticks | 3 per day |
| Payments | Symmetric — both banks send 20% at ticks 0 and 1 |
| Mode | Deterministic-temporal |
| Expected | Symmetric ≈20% |
| Result | Coordination failures in all 3 passes — one agent free-rides (1–10%) while the other overcommits (29–30%), but both end up worse off than the 50% baseline |

> 💡 The divergence between Experiments 2 and 3 is revealing: stochastic environments with
> statistical evaluation produce better coordination than deterministic environments.
> Bootstrap evaluation acts as a kind of "hedge" against greedy exploitation.

## Methodology Differences from Castro et al.

- **Implementation**: Castro uses a custom simulator; SimCash reimplements the model in Rust with Python orchestration
- **Action space**: Castro discretizes to 21 values (0%, 5%, ..., 100%); SimCash allows continuous values in [0,1]
- **Evaluation**: Both use bootstrap paired comparison for stochastic scenarios; SimCash adds CV and CI acceptance criteria
- **Agent dynamics**: Both optimize agents sequentially within iterations
