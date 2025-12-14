"""Verbose logging for experiment runners.

Provides structured verbose output for:
1. Policy parameter changes (--verbose-policy)
2. Bootstrap evaluation details (--verbose-bootstrap)
3. LLM interaction metadata (--verbose-llm)
4. Rejection analysis (--verbose-rejections)

Example:
    >>> from payment_simulator.experiments.runner import VerboseConfig, VerboseLogger
    >>> config = VerboseConfig.all_enabled()
    >>> logger = VerboseLogger(config)
    >>> logger.log_policy_change(...)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rich.console import Console
from rich.table import Table


@dataclass
class VerboseConfig:
    """Configuration for verbose logging flags.

    Each flag controls a category of verbose output:
    - iterations: Show iteration start messages
    - policy: Show before/after policy parameters
    - bootstrap: Show per-sample bootstrap evaluation results
    - llm: Show LLM call metadata (model, tokens, latency)
    - rejections: Show why policies are rejected
    - debug: Show detailed debug info (validation errors, retries, LLM progress)
    - simulations: Show simulation IDs when simulations start (default True)

    Example:
        >>> config = VerboseConfig(policy=True, bootstrap=True)
        >>> if config.policy:
        ...     print("Policy logging enabled")
    """

    iterations: bool = False
    policy: bool = False
    bootstrap: bool = False
    llm: bool = False
    rejections: bool = False
    debug: bool = False
    simulations: bool = True  # Show simulation IDs by default for transparency

    @property
    def any(self) -> bool:
        """Return True if any verbose flag is enabled.

        Returns:
            True if at least one verbose flag is enabled.
        """
        return (
            self.iterations
            or self.policy
            or self.bootstrap
            or self.llm
            or self.rejections
            or self.debug
            or self.simulations
        )

    @classmethod
    def all_enabled(cls) -> VerboseConfig:
        """Create config with all verbose flags enabled (except debug).

        Returns:
            VerboseConfig with all main flags set to True.
        """
        return cls(
            iterations=True,
            policy=True,
            bootstrap=True,
            llm=True,
            rejections=True,
            debug=False,
            simulations=True,
        )

    @classmethod
    def from_cli_flags(
        cls,
        *,
        verbose: bool = False,
        verbose_iterations: bool | None = None,
        verbose_policy: bool | None = None,
        verbose_bootstrap: bool | None = None,
        verbose_llm: bool | None = None,
        verbose_rejections: bool | None = None,
        debug: bool = False,
    ) -> VerboseConfig:
        """Create config from CLI flags.

        When `verbose=True` and no individual flags are set, all are enabled.
        When individual flags are explicitly set, they override.

        Args:
            verbose: Enable all verbose output.
            verbose_iterations: Override iterations verbose flag.
            verbose_policy: Override policy verbose flag.
            verbose_bootstrap: Override bootstrap verbose flag.
            verbose_llm: Override llm verbose flag.
            verbose_rejections: Override rejections verbose flag.
            debug: Enable debug output (validation errors, retries).

        Returns:
            VerboseConfig with appropriate flags set.
        """
        # If verbose=True and no individual flags, enable all
        if verbose:
            return cls(
                iterations=verbose_iterations if verbose_iterations is not None else True,
                policy=verbose_policy if verbose_policy is not None else True,
                bootstrap=verbose_bootstrap if verbose_bootstrap is not None else True,
                llm=verbose_llm if verbose_llm is not None else True,
                rejections=verbose_rejections if verbose_rejections is not None else True,
                debug=debug,
            )

        # Otherwise use individual flags
        return cls(
            iterations=verbose_iterations or False,
            policy=verbose_policy or False,
            bootstrap=verbose_bootstrap or False,
            llm=verbose_llm or False,
            rejections=verbose_rejections or False,
            debug=debug,
        )

    # Backward compatibility aliases
    @classmethod
    def all(cls) -> VerboseConfig:
        """Alias for all_enabled() for backward compatibility."""
        return cls.all_enabled()

    @classmethod
    def from_flags(
        cls,
        *,
        verbose: bool = False,
        verbose_iterations: bool | None = None,
        verbose_policy: bool | None = None,
        verbose_bootstrap: bool | None = None,
        verbose_llm: bool | None = None,
        verbose_rejections: bool | None = None,
        debug: bool = False,
    ) -> VerboseConfig:
        """Alias for from_cli_flags() for backward compatibility."""
        return cls.from_cli_flags(
            verbose=verbose,
            verbose_iterations=verbose_iterations,
            verbose_policy=verbose_policy,
            verbose_bootstrap=verbose_bootstrap,
            verbose_llm=verbose_llm,
            verbose_rejections=verbose_rejections,
            debug=debug,
        )


@dataclass
class BootstrapSampleResult:
    """Result from a single bootstrap sample evaluation.

    Attributes:
        seed: The RNG seed used.
        cost: Total cost in cents (current policy). Integer cents (INV-1).
        settled: Number of transactions settled.
        total: Total number of transactions.
        settlement_rate: Fraction of transactions settled.
        baseline_cost: Cost with baseline policy (for delta comparison).
            None for iteration 1 (establishing baseline).
    """

    seed: int
    cost: int
    settled: int
    total: int
    settlement_rate: float
    baseline_cost: int | None = None

    @property
    def delta_percent(self) -> float | None:
        """Compute percentage improvement vs baseline.

        Returns:
            Positive value means improvement (cost decreased).
            Negative value means regression (cost increased).
            None if no baseline_cost is set.

        Formula: (baseline_cost - cost) / baseline_cost * 100
        """
        if self.baseline_cost is None:
            return None
        if self.baseline_cost == 0:
            # Edge case: zero baseline
            return 0.0 if self.cost == 0 else None
        return (self.baseline_cost - self.cost) / self.baseline_cost * 100


@dataclass
class BootstrapDeltaResult:
    """Result from paired bootstrap evaluation comparing old vs new policy.

    Used for displaying delta-based acceptance results.

    Attributes:
        agent_id: Agent being evaluated.
        deltas: List of (old_cost - new_cost) per bootstrap sample.
            Positive = new policy is cheaper.
        delta_sum: Sum of all deltas.
        accepted: Whether the new policy was accepted.
        old_policy_mean_cost: Mean cost with old policy (integer cents).
        new_policy_mean_cost: Mean cost with new policy (integer cents).
        num_samples: Number of bootstrap samples.
    """

    agent_id: str
    deltas: list[int]
    delta_sum: int
    accepted: bool
    old_policy_mean_cost: int | None = None
    new_policy_mean_cost: int | None = None

    @property
    def num_samples(self) -> int:
        """Number of bootstrap samples."""
        return len(self.deltas)

    @property
    def mean_delta(self) -> float:
        """Mean delta (improvement) per sample."""
        if not self.deltas:
            return 0.0
        return self.delta_sum / len(self.deltas)

    @property
    def improvement_dollars(self) -> float:
        """Total improvement in dollars (positive = cheaper)."""
        return self.delta_sum / 100


@dataclass
class LLMCallMetadata:
    """Metadata from an LLM API call.

    Attributes:
        agent_id: Agent being optimized.
        model: Model name (e.g., "anthropic:claude-sonnet-4-5").
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
        old_cost: Previous cost (if cost rejection). Integer cents (INV-1).
        new_cost: New cost (if cost rejection). Integer cents (INV-1).
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
            old_cost: Cost with old policy. Integer cents (INV-1).
            new_cost: Cost with new policy. Integer cents (INV-1).
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

    def log_bootstrap_evaluation(
        self,
        seed_results: list[BootstrapSampleResult],
        mean_cost: int,
        std_cost: int,
        deterministic: bool = False,
        is_baseline_run: bool | None = None,
    ) -> None:
        """Log bootstrap evaluation results.

        Shows per-sample breakdown with best/worst identification based on
        improvement percentage (delta) when comparing to baseline.

        On baseline run (iteration 1): No Best/Worst labels shown since
        there's no previous policy to compare against.

        On subsequent runs: Best/Worst determined by delta_percent
        (highest improvement = Best, lowest/regression = Worst).

        Args:
            seed_results: Results from each sample.
            mean_cost: Mean cost across samples. Integer cents (INV-1).
            std_cost: Standard deviation of costs. Integer cents (INV-1).
            deterministic: If True, show deterministic mode output (no statistics).
            is_baseline_run: If True, this is iteration 1 (establishing baseline).
                If None, auto-detect from whether baseline_cost is set.
        """
        if not self._config.bootstrap:
            return

        num_samples = len(seed_results)

        # Deterministic mode: simplified output
        if deterministic and num_samples == 1:
            result = seed_results[0]
            cost_str = f"${result.cost / 100:,.2f}"
            settled_str = f"{result.settled}/{result.total}"
            rate_str = f"{result.settlement_rate * 100:.1f}%"

            self._console.print("\n[bold]Deterministic Evaluation:[/bold]")
            self._console.print(f"  Cost: {cost_str}")
            self._console.print(f"  Settled: {settled_str} ({rate_str})")
            self._console.print(f"  Seed: 0x{result.seed:08x} (for debugging)")
            self._console.print()
            return

        # Auto-detect baseline run if not specified
        if is_baseline_run is None:
            # It's a baseline run if no results have baseline_cost set
            is_baseline_run = all(r.baseline_cost is None for r in seed_results)

        # Check if we have delta information
        has_deltas = any(r.delta_percent is not None for r in seed_results)

        # Header varies by mode: "Bootstrap" only for multi-sample evaluation
        if is_baseline_run:
            if num_samples == 1:
                self._console.print("\n[bold]Baseline Evaluation:[/bold]")
            else:
                self._console.print(
                    f"\n[bold]Bootstrap Baseline ({num_samples} samples):[/bold]"
                )
        else:
            if num_samples == 1:
                self._console.print("\n[bold]Policy Evaluation:[/bold]")
            else:
                self._console.print(
                    f"\n[bold]Bootstrap Evaluation ({num_samples} samples):[/bold]"
                )

        # Find best and worst samples based on delta (improvement percentage)
        best_result: BootstrapSampleResult | None = None
        worst_result: BootstrapSampleResult | None = None

        if seed_results and has_deltas and not is_baseline_run:
            # Best = highest delta (most improvement)
            # Worst = lowest delta (least improvement or regression)
            results_with_delta = [r for r in seed_results if r.delta_percent is not None]
            if results_with_delta:
                best_result = max(results_with_delta, key=lambda r: r.delta_percent or 0)
                worst_result = min(results_with_delta, key=lambda r: r.delta_percent or 0)

        # Per-seed table
        table = Table(show_header=True, header_style="bold")
        table.add_column("Seed", style="dim")
        table.add_column("Cost", justify="right")
        if has_deltas and not is_baseline_run:
            table.add_column("Delta", justify="right")
        table.add_column("Settled", justify="right")
        table.add_column("Rate", justify="right")
        table.add_column("Note", style="italic")

        for result in seed_results:
            seed_str = f"0x{result.seed:08x}"[:10]
            cost_str = f"${result.cost / 100:,.2f}"
            settled_str = f"{result.settled}/{result.total}"
            rate_str = f"{result.settlement_rate * 100:.1f}%"

            # Delta column (only when comparing to baseline)
            delta_str = ""
            if has_deltas and not is_baseline_run:
                if result.delta_percent is not None:
                    if result.delta_percent >= 0:
                        delta_str = f"[green]+{result.delta_percent:.1f}%[/green]"
                    else:
                        delta_str = f"[red]{result.delta_percent:.1f}%[/red]"
                else:
                    delta_str = "-"

            # Note column (Best/Worst only when not baseline run)
            note = ""
            if not is_baseline_run:
                if result is best_result:
                    note = "[green]Best[/green]"
                elif result is worst_result:
                    note = "[red]Worst[/red]"

            if has_deltas and not is_baseline_run:
                table.add_row(seed_str, cost_str, delta_str, settled_str, rate_str, note)
            else:
                table.add_row(seed_str, cost_str, settled_str, rate_str, note)

        self._console.print(table)

        # Summary statistics
        mean_str = f"${mean_cost / 100:,.2f}"
        std_str = f"${std_cost / 100:,.2f}"
        self._console.print(f"  Mean: {mean_str} (std: {std_str})")

        # Mean delta if we have deltas
        if has_deltas and not is_baseline_run:
            deltas = [r.delta_percent for r in seed_results if r.delta_percent is not None]
            if deltas:
                mean_delta = sum(deltas) / len(deltas)
                if mean_delta >= 0:
                    self._console.print(
                        f"  Mean improvement: [green]+{mean_delta:.1f}%[/green]"
                    )
                else:
                    self._console.print(
                        f"  Mean improvement: [red]{mean_delta:.1f}%[/red]"
                    )

        if best_result and not is_baseline_run:
            self._console.print(
                f"  Best seed: 0x{best_result.seed:08x} (for debugging)"
            )
        if worst_result and not is_baseline_run:
            self._console.print(
                f"  Worst seed: 0x{worst_result.seed:08x} (for debugging)"
            )

        self._console.print()

    def log_bootstrap_deltas(self, result: BootstrapDeltaResult) -> None:
        """Log paired bootstrap evaluation results with deltas.

        Shows the delta-based comparison between old and new policies.
        This is called AFTER policy generation to show acceptance decision.

        Args:
            result: Bootstrap delta evaluation result.
        """
        if not self._config.bootstrap:
            return

        num_samples = result.num_samples
        agent_id = result.agent_id

        # Header varies by mode: "Bootstrap" only for multi-sample evaluation
        if num_samples == 1:
            self._console.print(
                f"\n[bold]Paired Policy Evaluation - {agent_id}:[/bold]"
            )
        else:
            self._console.print(
                f"\n[bold]Bootstrap Paired Evaluation ({num_samples} samples) - {agent_id}:[/bold]"
            )

        # Show per-sample deltas in a compact table
        table = Table(show_header=True, header_style="bold")
        table.add_column("Sample", style="dim", justify="right")
        table.add_column("Delta (¢)", justify="right")
        table.add_column("Note", style="italic")

        for i, delta in enumerate(result.deltas):
            sample_str = f"#{i + 1}"

            if delta > 0:
                delta_str = f"[green]+{delta:,}[/green]"
                note = "improvement"
            elif delta < 0:
                delta_str = f"[red]{delta:,}[/red]"
                note = "regression"
            else:
                delta_str = "0"
                note = "no change"

            table.add_row(sample_str, delta_str, note)

        self._console.print(table)

        # Summary
        mean_delta_cents = result.mean_delta
        delta_sum = result.delta_sum
        improvement_dollars = result.improvement_dollars

        if delta_sum > 0:
            self._console.print(
                f"  Delta sum: [green]+{delta_sum:,}¢[/green] "
                f"(+${improvement_dollars:,.2f} total improvement)"
            )
        elif delta_sum < 0:
            self._console.print(
                f"  Delta sum: [red]{delta_sum:,}¢[/red] "
                f"(${improvement_dollars:,.2f} regression)"
            )
        else:
            self._console.print(f"  Delta sum: {delta_sum}¢ (no net change)")

        self._console.print(f"  Mean delta: {mean_delta_cents:,.1f}¢ per sample")

        # Decision
        if result.accepted:
            self._console.print("  Decision: [green]ACCEPTED[/green] (delta_sum > 0)")
        else:
            self._console.print("  Decision: [red]REJECTED[/red] (delta_sum ≤ 0)")

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
            # Use `is not None` to handle zero cost (valid value) correctly
            old_str = f"${rejection.old_cost / 100:,.2f}" if rejection.old_cost is not None else "?"
            new_str = f"${rejection.new_cost / 100:,.2f}" if rejection.new_cost is not None else "?"
            self._console.print(
                f"\n  Decision: [red]REJECTED[/red] (cost not improved: {old_str} → {new_str})"
            )

        # Show retry info
        if rejection.retry_count is not None and rejection.max_retries is not None:
            self._console.print(
                f"  Retry: {rejection.retry_count}/{rejection.max_retries}..."
            )

        self._console.print()

    def log_debug_llm_request_start(self, agent_id: str, attempt: int) -> None:
        """Log the start of an LLM request (debug mode).

        Args:
            agent_id: Agent being optimized.
            attempt: Current attempt number (1-indexed).
        """
        if not self._config.debug:
            return

        if attempt == 1:
            self._console.print(
                f"    [dim cyan]→ Sending LLM request for {agent_id}...[/dim cyan]"
            )
        else:
            self._console.print(
                f"    [dim yellow]→ Retry attempt {attempt} for {agent_id}...[/dim yellow]"
            )

    def log_debug_validation_error(
        self,
        agent_id: str,
        attempt: int,
        max_attempts: int,
        errors: list[str],
    ) -> None:
        """Log validation errors during optimization (debug mode).

        Args:
            agent_id: Agent being optimized.
            attempt: Current attempt number (1-indexed).
            max_attempts: Maximum retry attempts.
            errors: List of validation error messages.
        """
        if not self._config.debug:
            return

        self._console.print(
            f"    [red]✗ Validation failed (attempt {attempt}/{max_attempts})[/red]"
        )
        for error in errors[:5]:  # Limit to first 5 errors
            self._console.print(f"      [dim red]- {error}[/dim red]")
        if len(errors) > 5:
            self._console.print(f"      [dim red]... and {len(errors) - 5} more[/dim red]")

    def log_debug_llm_error(
        self,
        agent_id: str,
        attempt: int,
        max_attempts: int,
        error: str,
    ) -> None:
        """Log LLM errors during optimization (debug mode).

        Args:
            agent_id: Agent being optimized.
            attempt: Current attempt number (1-indexed).
            max_attempts: Maximum retry attempts.
            error: Error message.
        """
        if not self._config.debug:
            return

        self._console.print(
            f"    [red]✗ LLM error (attempt {attempt}/{max_attempts}): {error}[/red]"
        )

    def log_debug_validation_success(self, agent_id: str, attempt: int) -> None:
        """Log successful validation (debug mode).

        Args:
            agent_id: Agent being optimized.
            attempt: Current attempt number (1-indexed).
        """
        if not self._config.debug:
            return

        if attempt > 1:
            self._console.print(
                f"    [green]✓ Validation passed on attempt {attempt}[/green]"
            )
        else:
            self._console.print(f"    [dim green]✓ Validation passed[/dim green]")

    def log_debug_all_retries_exhausted(
        self,
        agent_id: str,
        max_attempts: int,
        final_errors: list[str],
    ) -> None:
        """Log when all retry attempts are exhausted (debug mode).

        Args:
            agent_id: Agent being optimized.
            max_attempts: Maximum retry attempts.
            final_errors: Final validation errors.
        """
        if not self._config.debug:
            return

        self._console.print(
            f"    [bold red]✗ All {max_attempts} attempts exhausted for {agent_id}[/bold red]"
        )
        if final_errors:
            self._console.print("    Final errors:")
            for error in final_errors[:3]:
                self._console.print(f"      [dim red]- {error}[/dim red]")

    def log_simulation_start(
        self,
        simulation_id: str,
        purpose: str,
        iteration: int | None = None,
        seed: int | None = None,
    ) -> None:
        """Log the start of a simulation with its ID.

        This method logs simulation IDs to the terminal for user visibility,
        enabling users to replay specific simulations later.

        Args:
            simulation_id: Unique simulation ID.
            purpose: Purpose of the simulation (e.g., "initial_bootstrap",
                    "policy_evaluation", "paired_comparison").
            iteration: Current iteration number (if applicable).
            seed: RNG seed used for this simulation (if applicable).
        """
        if not self._config.simulations:
            return

        # Format the purpose for display
        purpose_display = purpose.replace("_", " ").title()

        if iteration is not None:
            self._console.print(
                f"  [dim]Simulation:[/dim] {simulation_id} "
                f"[dim]({purpose_display}, iter {iteration})[/dim]"
            )
        else:
            self._console.print(
                f"  [dim]Simulation:[/dim] {simulation_id} "
                f"[dim]({purpose_display})[/dim]"
            )

        if seed is not None and self._config.debug:
            self._console.print(f"    [dim]Seed: 0x{seed:08x}[/dim]")
