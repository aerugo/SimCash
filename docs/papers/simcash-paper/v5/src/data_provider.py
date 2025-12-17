"""Data provider for accessing experiment results.

This module defines the DataProvider protocol and DatabaseDataProvider implementation
for accessing experiment data from DuckDB databases.

All paper values must flow through this interface to ensure consistency.
This is the single source of truth for experiment data.

Example:
    >>> provider = DatabaseDataProvider(Path("data/"))
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


class DatabaseDataProvider:
    """DataProvider implementation using DuckDB databases.

    Reads experiment data from {exp_id}.db files in the data directory.
    Each database contains a policy_evaluations table with iteration results.

    Example:
        >>> provider = DatabaseDataProvider(Path("data/"))
        >>> results = provider.get_iteration_results("exp1", pass_num=1)
        >>> assert results[0]["cost"] >= 0  # Cost in cents
    """

    def __init__(self, data_dir: Path) -> None:
        """Initialize with directory containing exp{1,2,3}.db files.

        Args:
            data_dir: Path to directory with database files
        """
        self._data_dir = data_dir
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
        """Get run_id for experiment pass (cached).

        Run IDs are determined by sorting unique run_ids and selecting
        by pass number index.

        Args:
            exp_id: Experiment identifier
            pass_num: Pass number (1, 2, or 3)

        Returns:
            Run ID string

        Raises:
            ValueError: If pass_num exceeds available passes
        """
        cache_key = (exp_id, pass_num)
        if cache_key not in self._run_id_cache:
            conn = self._get_connection(exp_id)
            result = conn.execute(
                """
                SELECT DISTINCT run_id
                FROM policy_evaluations
                ORDER BY run_id
                """
            ).fetchall()

            run_ids = [r[0] for r in result]
            if pass_num < 1 or pass_num > len(run_ids):
                raise ValueError(
                    f"Pass {pass_num} not found for {exp_id}. "
                    f"Available passes: 1-{len(run_ids)}"
                )

            self._run_id_cache[cache_key] = run_ids[pass_num - 1]

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
