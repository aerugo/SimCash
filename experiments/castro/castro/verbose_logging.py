"""Verbose logging for Castro experiments.

Provides structured verbose output for:
1. Policy parameter changes (--verbose-policy)
2. Monte Carlo run details (--verbose-monte-carlo)
3. LLM interaction metadata (--verbose-llm)
4. Rejection analysis (--verbose-rejections)

Example:
    >>> from castro.verbose_logging import VerboseConfig, VerboseLogger
    >>> config = VerboseConfig.all()
    >>> logger = VerboseLogger(config)
    >>> logger.log_policy_change(...)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


@dataclass
class VerboseConfig:
    """Configuration for verbose logging flags.

    Each flag controls a category of verbose output:
    - policy: Show before/after policy parameters
    - monte_carlo: Show per-seed simulation results
    - llm: Show LLM call metadata (model, tokens, latency)
    - rejections: Show why policies are rejected

    Example:
        >>> config = VerboseConfig(policy=True, monte_carlo=True)
        >>> if config.policy:
        ...     print("Policy logging enabled")
    """

    policy: bool = False
    monte_carlo: bool = False
    llm: bool = False
    rejections: bool = False

    @property
    def any(self) -> bool:
        """Return True if any verbose flag is enabled.

        Returns:
            True if at least one verbose flag is enabled.
        """
        return self.policy or self.monte_carlo or self.llm or self.rejections

    @classmethod
    def all(cls) -> VerboseConfig:
        """Create config with all verbose flags enabled.

        Returns:
            VerboseConfig with all flags set to True.
        """
        return cls(policy=True, monte_carlo=True, llm=True, rejections=True)

    @classmethod
    def from_flags(
        cls,
        *,
        verbose: bool = False,
        verbose_policy: bool | None = None,
        verbose_monte_carlo: bool | None = None,
        verbose_llm: bool | None = None,
        verbose_rejections: bool | None = None,
    ) -> VerboseConfig:
        """Create config from CLI flags.

        When `verbose=True` and no individual flags are set, all are enabled.
        When individual flags are explicitly set, they override.

        Args:
            verbose: Enable all verbose output.
            verbose_policy: Override policy verbose flag.
            verbose_monte_carlo: Override monte_carlo verbose flag.
            verbose_llm: Override llm verbose flag.
            verbose_rejections: Override rejections verbose flag.

        Returns:
            VerboseConfig with appropriate flags set.
        """
        # If verbose=True and no individual flags, enable all
        if verbose:
            return cls(
                policy=verbose_policy if verbose_policy is not None else True,
                monte_carlo=verbose_monte_carlo if verbose_monte_carlo is not None else True,
                llm=verbose_llm if verbose_llm is not None else True,
                rejections=verbose_rejections if verbose_rejections is not None else True,
            )

        # Otherwise use individual flags
        return cls(
            policy=verbose_policy or False,
            monte_carlo=verbose_monte_carlo or False,
            llm=verbose_llm or False,
            rejections=verbose_rejections or False,
        )


@dataclass
class MonteCarloSeedResult:
    """Result from a single Monte Carlo seed.

    Attributes:
        seed: The RNG seed used.
        cost: Total cost in cents.
        settled: Number of transactions settled.
        total: Total number of transactions.
        settlement_rate: Fraction of transactions settled.
    """

    seed: int
    cost: int
    settled: int
    total: int
    settlement_rate: float


@dataclass
class LLMCallMetadata:
    """Metadata from an LLM API call.

    Attributes:
        agent_id: Agent being optimized.
        model: Model name (e.g., "gpt-4o").
        prompt_tokens: Number of input tokens.
        completion_tokens: Number of output tokens.
        latency_seconds: API call latency.
        context_summary: Optional summary of context provided.
    """

    agent_id: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_seconds: float
    context_summary: dict[str, Any] | None = None


@dataclass
class RejectionDetail:
    """Details about why a policy was rejected.

    Attributes:
        agent_id: Agent whose policy was rejected.
        proposed_policy: The rejected policy.
        validation_errors: List of validation error messages.
        rejection_reason: Reason for rejection (e.g., "cost_not_improved").
        old_cost: Previous cost (if cost rejection).
        new_cost: New cost (if cost rejection).
        retry_count: Current retry attempt.
        max_retries: Maximum retries allowed.
    """

    agent_id: str
    proposed_policy: dict[str, Any]
    validation_errors: list[str] = field(default_factory=list)
    rejection_reason: str | None = None
    old_cost: int | None = None
    new_cost: int | None = None
    retry_count: int | None = None
    max_retries: int | None = None


class VerboseLogger:
    """Logger for structured verbose experiment output.

    Produces rich console output based on enabled verbose flags.
    Each logging method checks its corresponding flag before output.

    Example:
        >>> config = VerboseConfig(policy=True)
        >>> logger = VerboseLogger(config)
        >>> logger.log_policy_change(
        ...     agent_id="BANK_A",
        ...     old_policy={"parameters": {"threshold": 3.0}},
        ...     new_policy={"parameters": {"threshold": 2.0}},
        ...     old_cost=1000,
        ...     new_cost=800,
        ...     accepted=True,
        ... )
    """

    def __init__(
        self,
        config: VerboseConfig,
        console: Console | None = None,
    ) -> None:
        """Initialize the verbose logger.

        Args:
            config: VerboseConfig controlling which output to produce.
            console: Rich Console for output. Creates default if None.
        """
        self._config = config
        self._console = console or Console()

    def log_iteration_start(self, iteration: int, total_cost: int) -> None:
        """Log the start of an optimization iteration.

        Args:
            iteration: Iteration number.
            total_cost: Total cost in cents.
        """
        if not self._config.any:
            return

        cost_str = f"${total_cost / 100:,.2f}"
        self._console.print(f"\n[bold cyan]Iteration {iteration}[/bold cyan]")
        self._console.print(f"  Total cost: {cost_str}")

    def log_policy_change(
        self,
        agent_id: str,
        old_policy: dict[str, Any],
        new_policy: dict[str, Any],
        old_cost: int,
        new_cost: int,
        accepted: bool,
    ) -> None:
        """Log a policy parameter change.

        Shows before/after parameters with percentage deltas.

        Args:
            agent_id: Agent being optimized.
            old_policy: Previous policy.
            new_policy: Proposed new policy.
            old_cost: Cost with old policy.
            new_cost: Cost with new policy.
            accepted: Whether the change was accepted.
        """
        if not self._config.policy:
            return

        # Extract parameters
        old_params = old_policy.get("parameters", {})
        new_params = new_policy.get("parameters", {})

        # Build parameter comparison table
        table = Table(title=f"Policy Change: {agent_id}", show_header=True)
        table.add_column("Parameter", style="cyan")
        table.add_column("Old", justify="right")
        table.add_column("New", justify="right")
        table.add_column("Delta", justify="right")

        # Get all parameter keys
        all_keys = set(old_params.keys()) | set(new_params.keys())

        for key in sorted(all_keys):
            old_val = old_params.get(key)
            new_val = new_params.get(key)

            old_str = f"{old_val}" if old_val is not None else "-"
            new_str = f"{new_val}" if new_val is not None else "-"

            # Calculate delta
            delta_str = ""
            if (
                old_val is not None
                and new_val is not None
                and isinstance(old_val, (int, float))
                and isinstance(new_val, (int, float))
                and old_val != 0
            ):
                delta_pct = ((new_val - old_val) / old_val) * 100
                if delta_pct >= 0:
                    delta_str = f"[green]+{delta_pct:.0f}%[/green]"
                else:
                    delta_str = f"[red]{delta_pct:.0f}%[/red]"

            table.add_row(key, old_str, new_str, delta_str)

        self._console.print(table)

        # Cost change
        old_cost_str = f"${old_cost / 100:,.2f}"
        new_cost_str = f"${new_cost / 100:,.2f}"

        if old_cost != 0:
            cost_delta_pct = ((new_cost - old_cost) / old_cost) * 100
            cost_delta_str = f"({cost_delta_pct:+.1f}%)"
        else:
            cost_delta_str = ""

        self._console.print(
            f"  Evaluation: {old_cost_str} → {new_cost_str} {cost_delta_str}"
        )

        # Decision
        if accepted:
            self._console.print("  Decision: [green]ACCEPTED[/green]")
        else:
            self._console.print("  Decision: [red]REJECTED[/red]")

        self._console.print()

    def log_monte_carlo_evaluation(
        self,
        seed_results: list[MonteCarloSeedResult],
        mean_cost: int,
        std_cost: int,
        deterministic: bool = False,
    ) -> None:
        """Log Monte Carlo evaluation results.

        Shows per-seed breakdown with best/worst identification.
        In deterministic mode, shows single evaluation result without statistics.

        Args:
            seed_results: Results from each seed.
            mean_cost: Mean cost across seeds.
            std_cost: Standard deviation of costs.
            deterministic: If True, show deterministic mode output (no statistics).
        """
        if not self._config.monte_carlo:
            return

        num_samples = len(seed_results)

        # Deterministic mode: simplified output
        if deterministic and num_samples == 1:
            result = seed_results[0]
            cost_str = f"${result.cost / 100:,.2f}"
            settled_str = f"{result.settled}/{result.total}"
            rate_str = f"{result.settlement_rate * 100:.1f}%"

            self._console.print(f"\n[bold]Deterministic Evaluation:[/bold]")
            self._console.print(f"  Cost: {cost_str}")
            self._console.print(f"  Settled: {settled_str} ({rate_str})")
            self._console.print(f"  Seed: 0x{result.seed:08x} (for debugging)")
            self._console.print()
            return

        # Monte Carlo mode: full statistics
        self._console.print(f"\n[bold]Monte Carlo Evaluation ({num_samples} samples):[/bold]")

        # Find best and worst seeds
        if seed_results:
            best_result = min(seed_results, key=lambda r: r.cost)
            worst_result = max(seed_results, key=lambda r: r.cost)
        else:
            best_result = worst_result = None

        # Per-seed table
        table = Table(show_header=True, header_style="bold")
        table.add_column("Seed", style="dim")
        table.add_column("Cost", justify="right")
        table.add_column("Settled", justify="right")
        table.add_column("Rate", justify="right")
        table.add_column("Note", style="italic")

        for result in seed_results:
            seed_str = f"0x{result.seed:08x}"[:10]
            cost_str = f"${result.cost / 100:,.2f}"
            settled_str = f"{result.settled}/{result.total}"
            rate_str = f"{result.settlement_rate * 100:.1f}%"

            note = ""
            if result is best_result:
                note = "[green]Best[/green]"
            elif result is worst_result:
                note = "[red]Worst[/red]"

            table.add_row(seed_str, cost_str, settled_str, rate_str, note)

        self._console.print(table)

        # Summary statistics
        mean_str = f"${mean_cost / 100:,.2f}"
        std_str = f"${std_cost / 100:,.2f}"
        self._console.print(f"  Mean: {mean_str} (std: {std_str})")

        if best_result:
            self._console.print(
                f"  Best seed: 0x{best_result.seed:08x} (for debugging)"
            )
        if worst_result:
            self._console.print(
                f"  Worst seed: 0x{worst_result.seed:08x} (for debugging)"
            )

        self._console.print()

    def log_llm_call(self, metadata: LLMCallMetadata) -> None:
        """Log LLM API call metadata.

        Shows model, tokens, latency, and context summary.

        Args:
            metadata: LLM call metadata.
        """
        if not self._config.llm:
            return

        self._console.print(f"\n[bold]LLM Call for {metadata.agent_id}:[/bold]")
        self._console.print(f"  Model: {metadata.model}")
        self._console.print(f"  Prompt tokens: {metadata.prompt_tokens:,}")
        self._console.print(f"  Completion tokens: {metadata.completion_tokens:,}")
        self._console.print(f"  Latency: {metadata.latency_seconds:.1f}s")

        if metadata.context_summary:
            self._console.print("  Key context provided:")
            for key, value in metadata.context_summary.items():
                if key == "current_cost" and isinstance(value, (int, float)):
                    self._console.print(f"    - {key}: ${value / 100:,.2f}")
                elif "cost" in key.lower() and isinstance(value, (int, float)):
                    self._console.print(f"    - {key}: ${value / 100:,.2f}")
                else:
                    self._console.print(f"    - {key}: {value}")

        self._console.print()

    def log_rejection(self, rejection: RejectionDetail) -> None:
        """Log policy rejection details.

        Shows validation errors and rejection reason.

        Args:
            rejection: Rejection details.
        """
        if not self._config.rejections:
            return

        self._console.print(f"\n[bold red]Policy Rejected: {rejection.agent_id}[/bold red]")

        # Show proposed parameters if available
        proposed_params = rejection.proposed_policy.get("parameters", {})
        if proposed_params:
            self._console.print("  Proposed policy:")
            for key, value in proposed_params.items():
                # Mark invalid values
                is_invalid = any(key in err for err in rejection.validation_errors)
                if is_invalid:
                    self._console.print(f"    {key}: [red]{value}[/red] [dim]# INVALID[/dim]")
                else:
                    self._console.print(f"    {key}: {value}")

        # Show validation errors
        if rejection.validation_errors:
            self._console.print("\n  Validation errors:")
            for i, error in enumerate(rejection.validation_errors, 1):
                self._console.print(f"    {i}. {error}")

        # Show cost rejection reason
        if rejection.rejection_reason == "cost_not_improved":
            old_str = f"${rejection.old_cost / 100:,.2f}" if rejection.old_cost else "?"
            new_str = f"${rejection.new_cost / 100:,.2f}" if rejection.new_cost else "?"
            self._console.print(
                f"\n  Decision: [red]REJECTED[/red] (cost not improved: {old_str} → {new_str})"
            )

        # Show retry info
        if rejection.retry_count is not None and rejection.max_retries is not None:
            self._console.print(
                f"  Retry: {rejection.retry_count}/{rejection.max_retries}..."
            )

        self._console.print()
