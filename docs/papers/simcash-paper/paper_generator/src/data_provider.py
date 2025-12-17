"""Data provider for accessing experiment results.

This module defines the DataProvider protocol and DatabaseDataProvider implementation
for accessing experiment data from DuckDB databases.

All paper values must flow through this interface to ensure consistency.
This is the single source of truth for experiment data.

A config.yaml file is REQUIRED for DatabaseDataProvider to ensure reproducible
run_id selection. The config explicitly maps experiment passes to specific run_ids.

Example:
    >>> from src.config import load_config
    >>> config = load_config(Path("config.yaml"))
    >>> provider = DatabaseDataProvider(Path("data/"), config=config)
    >>> results = provider.get_iteration_results("exp1", pass_num=1)
    >>> for r in results:
    ...     print(f"Iter {r['iteration']}: {r['agent_id']} cost={r['cost']} cents")
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol, TypedDict, runtime_checkable

import duckdb


class AgentIterationResult(TypedDict):
    """Per-agent results for one iteration of an experiment.

    All monetary values are in cents (integer) to maintain precision.

    Attributes:
        iteration: 1-indexed iteration number
        agent_id: Agent identifier ("BANK_A" or "BANK_B")
        cost: Total cost for this iteration in cents (NOT dollars)
        liquidity_fraction: Initial liquidity as fraction (0.0 to 1.0)
        accepted: Whether this policy proposal was accepted
    """

    iteration: int
    agent_id: str
    cost: int
    liquidity_fraction: float
    accepted: bool


class BootstrapStats(TypedDict):
    """Bootstrap evaluation statistics for one agent's policy.

    Used for stochastic experiments (Exp2) where policies are evaluated
    across multiple random seeds. All monetary values in cents.

    Attributes:
        mean_cost: Mean cost across bootstrap samples in cents
        std_dev: Standard deviation of costs in cents
        ci_lower: Lower bound of 95% confidence interval in cents
        ci_upper: Upper bound of 95% confidence interval in cents
        num_samples: Number of bootstrap samples (typically 50)
    """

    mean_cost: int
    std_dev: int
    ci_lower: int
    ci_upper: int
    num_samples: int


class PassSummary(TypedDict):
    """Summary of results for one experiment pass.

    Attributes:
        pass_num: Pass number (1, 2, or 3)
        iterations: Number of iterations to convergence
        bank_a_liquidity: Final liquidity fraction for BANK_A (0.0 to 1.0)
        bank_b_liquidity: Final liquidity fraction for BANK_B (0.0 to 1.0)
        bank_a_cost: Final cost for BANK_A in cents
        bank_b_cost: Final cost for BANK_B in cents
        total_cost: Combined final cost in cents
    """

    pass_num: int
    iterations: int
    bank_a_liquidity: float
    bank_b_liquidity: float
    bank_a_cost: int
    bank_b_cost: int
    total_cost: int


class ConvergenceStats(TypedDict):
    """Aggregate convergence statistics across experiments.

    Attributes:
        exp_id: Experiment identifier
        mean_iterations: Average iterations across passes
        min_iterations: Minimum iterations
        max_iterations: Maximum iterations
        convergence_rate: Fraction of passes that converged (0.0 to 1.0)
        num_passes: Number of passes in this experiment
    """

    exp_id: str
    mean_iterations: float
    min_iterations: int
    max_iterations: int
    convergence_rate: float
    num_passes: int


class AggregateStats(TypedDict):
    """Aggregate statistics across all experiments.

    Attributes:
        total_experiments: Number of experiments
        total_passes: Total number of passes across all experiments
        overall_mean_iterations: Mean iterations across all passes
        overall_convergence_rate: Fraction of all passes that converged
        total_converged: Number of passes that converged
    """

    total_experiments: int
    total_passes: int
    overall_mean_iterations: float
    overall_convergence_rate: float
    total_converged: int


@runtime_checkable
class DataProvider(Protocol):
    """Protocol for accessing experiment data.

    All paper values must come through this interface to ensure:
    1. Single source of truth for all data
    2. Consistent formatting and units
    3. Testability via mock implementations

    Implementations:
        - DatabaseDataProvider: Production implementation using DuckDB
        - MockDataProvider: For testing (not yet implemented)
    """

    def get_iteration_results(
        self, exp_id: str, pass_num: int
    ) -> list[AgentIterationResult]:
        """Get per-agent costs for all iterations of an experiment pass.

        Args:
            exp_id: Experiment identifier ("exp1", "exp2", "exp3")
            pass_num: Pass number (1, 2, or 3)

        Returns:
            List of results ordered by (iteration, agent_id).
            Each result contains cost in cents (not dollars).

        Raises:
            ValueError: If exp_id or pass_num is invalid
        """
        ...

    def get_final_bootstrap_stats(
        self, exp_id: str, pass_num: int
    ) -> dict[str, BootstrapStats]:
        """Get bootstrap statistics for the final iteration.

        Only meaningful for stochastic experiments (Exp2) where bootstrap
        evaluation is used. For deterministic experiments, std_dev will be 0
        and CI bounds will equal the mean.

        Args:
            exp_id: Experiment identifier
            pass_num: Pass number

        Returns:
            Dict mapping agent_id to bootstrap statistics.
            All values in cents.
        """
        ...

    def get_convergence_iteration(self, exp_id: str, pass_num: int) -> int:
        """Get the iteration number where convergence was detected.

        This is the final iteration in the experiment run.

        Args:
            exp_id: Experiment identifier
            pass_num: Pass number

        Returns:
            Iteration number (1-indexed)
        """
        ...

    def get_run_id(self, exp_id: str, pass_num: int) -> str:
        """Get the run_id for an experiment pass.

        Run IDs are unique identifiers for each experiment run,
        formatted as: {exp_id}-{date}-{time}-{hash}

        Args:
            exp_id: Experiment identifier
            pass_num: Pass number

        Returns:
            Run ID string (e.g., "exp1-20251217-001234-abc123")
        """
        ...

    def get_pass_summary(self, exp_id: str, pass_num: int) -> PassSummary:
        """Get summary of results for one experiment pass.

        Args:
            exp_id: Experiment identifier
            pass_num: Pass number

        Returns:
            PassSummary with final iteration stats
        """
        ...

    def get_all_pass_summaries(self, exp_id: str) -> list[PassSummary]:
        """Get summaries for all passes of an experiment.

        Args:
            exp_id: Experiment identifier

        Returns:
            List of PassSummary for each pass
        """
        ...

    def get_convergence_statistics(self, exp_id: str) -> ConvergenceStats:
        """Get aggregate convergence statistics across all passes.

        Args:
            exp_id: Experiment identifier

        Returns:
            ConvergenceStats with mean, min, max iterations and rate
        """
        ...

    def get_num_passes(self, exp_id: str) -> int:
        """Get the number of passes for an experiment.

        Args:
            exp_id: Experiment identifier

        Returns:
            Number of passes (typically 3)
        """
        ...

    def get_experiment_ids(self) -> list[str]:
        """Get list of all experiment identifiers.

        Returns:
            List of experiment IDs (e.g., ["exp1", "exp2", "exp3"])
        """
        ...

    def get_aggregate_stats(self) -> AggregateStats:
        """Get aggregate statistics across all experiments.

        Returns:
            AggregateStats with total passes, mean iterations, convergence rate
        """
        ...


class DatabaseDataProvider:
    """DataProvider implementation using DuckDB databases.

    Reads experiment data from {exp_id}.db files in the data directory.
    Each database contains a policy_evaluations table with iteration results.

    A config file is REQUIRED. Run_ids are looked up from the config file
    which explicitly maps experiment passes to specific run_ids. This ensures
    reproducible paper generation and prevents issues with database ordering.

    Example:
        >>> from src.config import load_config
        >>> config = load_config(Path("config.yaml"))
        >>> provider = DatabaseDataProvider(Path("data/"), config=config)
        >>> results = provider.get_iteration_results("exp1", pass_num=1)
        >>> assert results[0]["cost"] >= 0  # Cost in cents
    """

    def __init__(
        self,
        data_dir: Path,
        config: dict,
    ) -> None:
        """Initialize with directory containing exp{1,2,3}.db files.

        A config file is REQUIRED to ensure reproducible run_id selection.

        Args:
            data_dir: Path to directory with database files
            config: Paper config with explicit run_id mappings (required)
        """
        self._data_dir = data_dir
        self._config = config
        self._run_id_cache: dict[tuple[str, int], str] = {}

    def _get_db_path(self, exp_id: str) -> Path:
        """Get database path for experiment.

        Args:
            exp_id: Experiment identifier ("exp1", "exp2", "exp3")

        Returns:
            Path to database file
        """
        return self._data_dir / f"{exp_id}.db"

    def _get_connection(self, exp_id: str) -> duckdb.DuckDBPyConnection:
        """Get read-only connection to experiment database.

        Args:
            exp_id: Experiment identifier

        Returns:
            DuckDB connection in read-only mode
        """
        db_path = self._get_db_path(exp_id)
        if not db_path.exists():
            raise ValueError(f"Database not found: {db_path}")
        return duckdb.connect(str(db_path), read_only=True)

    def get_run_id(self, exp_id: str, pass_num: int) -> str:
        """Get run_id for experiment pass from config (cached).

        Args:
            exp_id: Experiment identifier
            pass_num: Pass number (1, 2, or 3)

        Returns:
            Run ID string

        Raises:
            KeyError: If exp_id or pass_num not in config
        """
        cache_key = (exp_id, pass_num)
        if cache_key not in self._run_id_cache:
            from src.config import get_run_id as config_get_run_id

            self._run_id_cache[cache_key] = config_get_run_id(
                self._config, exp_id, pass_num
            )

        return self._run_id_cache[cache_key]

    def get_iteration_results(
        self, exp_id: str, pass_num: int
    ) -> list[AgentIterationResult]:
        """Get per-agent costs for all iterations.

        Queries the policy_evaluations table for the specified run and
        returns results ordered by (iteration, agent_id).

        Args:
            exp_id: Experiment identifier
            pass_num: Pass number

        Returns:
            List of AgentIterationResult dicts with costs in cents
        """
        run_id = self.get_run_id(exp_id, pass_num)
        conn = self._get_connection(exp_id)

        result = conn.execute(
            """
            SELECT
                iteration,
                agent_id,
                new_cost AS cost,
                CAST(
                    json_extract(
                        proposed_policy,
                        '$.parameters.initial_liquidity_fraction'
                    ) AS DOUBLE
                ) AS liquidity_fraction,
                accepted
            FROM policy_evaluations
            WHERE run_id = ?
            ORDER BY iteration, agent_id
            """,
            [run_id],
        ).fetchall()

        return [
            AgentIterationResult(
                iteration=row[0],
                agent_id=row[1],
                cost=row[2],
                liquidity_fraction=row[3],
                accepted=row[4],
            )
            for row in result
        ]

    def get_final_bootstrap_stats(
        self, exp_id: str, pass_num: int
    ) -> dict[str, BootstrapStats]:
        """Get bootstrap statistics for final iteration.

        For stochastic experiments, returns mean, std_dev, and CI bounds.
        For deterministic experiments, std_dev=0 and CI bounds equal mean.

        Args:
            exp_id: Experiment identifier
            pass_num: Pass number

        Returns:
            Dict mapping agent_id to BootstrapStats
        """
        run_id = self.get_run_id(exp_id, pass_num)
        conn = self._get_connection(exp_id)

        # Get max iteration for this run
        max_iter_result = conn.execute(
            """
            SELECT MAX(iteration)
            FROM policy_evaluations
            WHERE run_id = ?
            """,
            [run_id],
        ).fetchone()

        if max_iter_result is None or max_iter_result[0] is None:
            raise ValueError(f"No iterations found for {exp_id} pass {pass_num}")

        max_iter = max_iter_result[0]

        result = conn.execute(
            """
            SELECT
                agent_id,
                new_cost AS mean_cost,
                COALESCE(cost_std_dev, 0) AS std_dev,
                confidence_interval_95,
                num_samples
            FROM policy_evaluations
            WHERE run_id = ? AND iteration = ?
            """,
            [run_id, max_iter],
        ).fetchall()

        stats: dict[str, BootstrapStats] = {}
        for row in result:
            agent_id, mean_cost, std_dev, ci_json, num_samples = row

            # Parse CI JSON - can be string or already parsed
            if ci_json:
                ci = json.loads(ci_json) if isinstance(ci_json, str) else ci_json
                ci_lower, ci_upper = int(ci[0]), int(ci[1])
            else:
                # No CI data - use mean as both bounds
                ci_lower, ci_upper = mean_cost, mean_cost

            stats[agent_id] = BootstrapStats(
                mean_cost=mean_cost,
                std_dev=int(std_dev),
                ci_lower=ci_lower,
                ci_upper=ci_upper,
                num_samples=num_samples if num_samples else 1,
            )

        return stats

    def get_convergence_iteration(self, exp_id: str, pass_num: int) -> int:
        """Get iteration where convergence was detected.

        This is simply the maximum iteration number in the run.

        Args:
            exp_id: Experiment identifier
            pass_num: Pass number

        Returns:
            Final iteration number (1-indexed)
        """
        run_id = self.get_run_id(exp_id, pass_num)
        conn = self._get_connection(exp_id)

        result = conn.execute(
            """
            SELECT MAX(iteration)
            FROM policy_evaluations
            WHERE run_id = ?
            """,
            [run_id],
        ).fetchone()

        if result is None or result[0] is None:
            raise ValueError(f"No iterations found for {exp_id} pass {pass_num}")

        return result[0]

    def get_num_passes(self, exp_id: str) -> int:
        """Get the number of passes for an experiment from config.

        Args:
            exp_id: Experiment identifier

        Returns:
            Number of passes defined in config
        """
        from src.config import get_pass_numbers

        return len(get_pass_numbers(self._config, exp_id))

    def get_experiment_ids(self) -> list[str]:
        """Get list of all experiment identifiers from config.

        Returns:
            List of experiment IDs (e.g., ["exp1", "exp2", "exp3"])
        """
        from src.config import get_experiment_ids as config_get_experiment_ids

        return config_get_experiment_ids(self._config)

    def get_aggregate_stats(self) -> AggregateStats:
        """Get aggregate statistics across all experiments.

        Returns:
            AggregateStats with total passes, mean iterations, convergence rate
        """
        exp_ids = self.get_experiment_ids()
        all_convergence_stats = [
            self.get_convergence_statistics(exp_id) for exp_id in exp_ids
        ]

        total_experiments = len(exp_ids)
        total_passes = sum(stats["num_passes"] for stats in all_convergence_stats)

        # Calculate overall mean iterations (weighted by passes)
        total_iterations = sum(
            stats["mean_iterations"] * stats["num_passes"]
            for stats in all_convergence_stats
        )
        overall_mean_iterations = total_iterations / total_passes if total_passes > 0 else 0.0

        # Calculate overall convergence rate
        total_converged = sum(
            int(stats["convergence_rate"] * stats["num_passes"])
            for stats in all_convergence_stats
        )
        overall_convergence_rate = total_converged / total_passes if total_passes > 0 else 0.0

        return AggregateStats(
            total_experiments=total_experiments,
            total_passes=total_passes,
            overall_mean_iterations=overall_mean_iterations,
            overall_convergence_rate=overall_convergence_rate,
            total_converged=total_converged,
        )

    def get_pass_summary(self, exp_id: str, pass_num: int) -> PassSummary:
        """Get summary of results for one experiment pass.

        Args:
            exp_id: Experiment identifier
            pass_num: Pass number

        Returns:
            PassSummary with final iteration stats
        """
        # Get final iteration results
        final_iter = self.get_convergence_iteration(exp_id, pass_num)
        results = self.get_iteration_results(exp_id, pass_num)

        # Filter to final iteration
        final_results = [r for r in results if r["iteration"] == final_iter]

        # Get per-agent values
        bank_a = next((r for r in final_results if r["agent_id"] == "BANK_A"), None)
        bank_b = next((r for r in final_results if r["agent_id"] == "BANK_B"), None)

        if bank_a is None or bank_b is None:
            raise ValueError(f"Missing agent data for {exp_id} pass {pass_num}")

        return PassSummary(
            pass_num=pass_num,
            iterations=final_iter,
            bank_a_liquidity=bank_a["liquidity_fraction"],
            bank_b_liquidity=bank_b["liquidity_fraction"],
            bank_a_cost=bank_a["cost"],
            bank_b_cost=bank_b["cost"],
            total_cost=bank_a["cost"] + bank_b["cost"],
        )

    def get_all_pass_summaries(self, exp_id: str) -> list[PassSummary]:
        """Get summaries for all passes of an experiment.

        Args:
            exp_id: Experiment identifier

        Returns:
            List of PassSummary for each pass
        """
        num_passes = self.get_num_passes(exp_id)
        return [self.get_pass_summary(exp_id, p + 1) for p in range(num_passes)]

    def get_convergence_statistics(self, exp_id: str) -> ConvergenceStats:
        """Get aggregate convergence statistics across all passes.

        Args:
            exp_id: Experiment identifier

        Returns:
            ConvergenceStats with mean, min, max iterations and rate
        """
        summaries = self.get_all_pass_summaries(exp_id)

        if not summaries:
            raise ValueError(f"No passes found for {exp_id}")

        iterations = [s["iterations"] for s in summaries]

        # All passes converged (we don't track non-convergence currently)
        convergence_rate = 1.0

        return ConvergenceStats(
            exp_id=exp_id,
            mean_iterations=sum(iterations) / len(iterations),
            min_iterations=min(iterations),
            max_iterations=max(iterations),
            convergence_rate=convergence_rate,
            num_passes=len(summaries),
        )
