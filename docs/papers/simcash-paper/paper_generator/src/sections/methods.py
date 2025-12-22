"""Methods section generator."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.data_provider import DataProvider


def generate_methods(provider: DataProvider) -> str:
    """Generate the methods/framework section.

    Args:
        provider: DataProvider instance for accessing experiment data

    Returns:
        LaTeX string for the methods section
    """
    # Provider not used for static methods text
    _ = provider

    return r"""
\section{The SimCash Framework}
\label{sec:methods}

\subsection{Simulation Engine}

SimCash uses a discrete-time simulation where:
\begin{itemize}
    \item Time proceeds in \textbf{ticks} (atomic time units)
    \item Banks hold \textbf{balances} in settlement accounts
    \item \textbf{Transactions} arrive with amounts, counterparties, and deadlines
    \item Settlement follows RTGS (Real-Time Gross Settlement) rules
\end{itemize}

\subsection{Cost Function}

Agent costs comprise:
\begin{itemize}
    \item \textbf{Liquidity opportunity cost}: Proportional to allocated reserves
    \item \textbf{Delay penalty}: Accumulated per tick for pending transactions
    \item \textbf{Deadline penalty}: Incurred when transactions become overdue (not used in this paper's experiments)
    \item \textbf{End-of-day penalty}: Large cost for unsettled transactions at day end
    \item \textbf{Overdraft cost}: Fee for negative balance (not used in this paper's experiments; agents operate under hard liquidity constraints)
\end{itemize}

\subsection{LLM Policy Optimization}

The key innovation is using LLMs to propose policy parameters. At each iteration:

\begin{enumerate}
    \item \textbf{Context Construction}: Agent receives its own policy, filtered simulation trace, and cost history (see Section~\ref{sec:prompt_anatomy})
    \item \textbf{LLM Proposal}: Agent proposes new \texttt{initial\_liquidity\_fraction} parameter
    \item \textbf{Evaluation}: Run simulation(s) with proposed policy
    \item \textbf{Update}: Apply mode-specific acceptance rule (see below)
    \item \textbf{Convergence Check}: Stable \texttt{initial\_liquidity\_fraction} (temporal) or multi-criteria cost stability (bootstrap) over 5 iterations
\end{enumerate}

\subsection{Optimization Prompt Anatomy}
\label{sec:prompt_anatomy}

A critical aspect of our framework is the \textbf{strict information isolation} between agents.
Each agent receives a two-part prompt with no access to counterparty information.
Full prompt examples are provided in Appendix~\ref{app:system_prompt}.

\subsubsection{System Prompt (Shared)}

The system prompt is identical for all agents and provides domain context:
\begin{itemize}
    \item RTGS mechanics and queuing behavior
    \item Cost structure: overdraft, delay, deadline, and EOD penalties
    \item Policy tree architecture: JSON schema for valid policies
    \item Optimization guidance: e.g., ``lower liquidity reduces holding costs but increases delay risk; find the balance that minimizes total cost''
\end{itemize}

\subsubsection{User Prompt (Agent-Specific)}

The user prompt is constructed individually for each agent and contains \textbf{only} information
about that agent's own experience:

\begin{enumerate}
    \item \textbf{Performance metrics from past iterations}: Agent's own mean cost, standard deviation, settlement rate
    \item \textbf{Current policy}: Agent's own \texttt{initial\_liquidity\_fraction} parameter
    \item \textbf{Cost breakdown}: Agent's own costs by type (delay, overdraft, penalties)
    \item \textbf{Simulation trace}: Filtered event log showing \textbf{only}:
    \begin{itemize}
        \item Outgoing transactions FROM this agent
        \item Incoming payments TO this agent
        \item Agent's own policy decisions (Submit, Hold, etc.)
        \item Agent's own balance changes (for settlements it initiated)
    \end{itemize}
    \item \textbf{Iteration history}: Agent's own cost trajectory across iterations
\end{enumerate}

\subsubsection{Information Isolation}

The prompt explicitly excludes all counterparty information:
\begin{itemize}
    \item \textbf{No counterparty balances}: Agents cannot observe opponent's reserves
    \item \textbf{No counterparty policies}: Agents cannot see opponent's liquidity fraction
    \item \textbf{No counterparty costs}: Agents cannot observe opponent's cost breakdown
    \item \textbf{No third-party events}: Transactions not involving this agent are filtered
\end{itemize}

This isolation is enforced programmatically by the \texttt{filter\_events\_for\_agent()} function.
The only ``signal'' about counterparty behavior comes from \textit{incoming payments}---a realistic
level of transparency in actual RTGS systems where participants observe settlement messages but not
others' internal liquidity positions.

Crucially, agents receive \textbf{transaction events from the current iteration} alongside
\textbf{performance metrics from past iterations}, but are never informed that the environment
is stationary. The agent is not told that all iterations use identical transaction schedules
(Experiments 1 and 3) or identical stochastic parameters (Experiment 2). From the agent's
perspective, each iteration could involve a different payment environment---any regularity
must be inferred from observed patterns rather than assumed from explicit knowledge of the
experimental design.

\subsection{Evaluation Modes}

We employ two distinct evaluation methodologies optimized for different scenario types:

\subsubsection{Deterministic-Temporal Mode (Experiments 1 \& 3)}

For scenarios with fixed payment schedules, we use \textbf{temporal policy stability} to identify stable policy profiles:

\begin{itemize}
    \item \textbf{Single simulation} per iteration with deterministic arrivals
    \item \textbf{Unconditional acceptance}: All LLM-proposed policies are accepted immediately, regardless of cost impact
    \item \textbf{Rationale}: Cost-based rejection would cause oscillation in multi-agent settings where counterparty policies also change each iteration
    \item \textbf{Convergence criterion}: Both agents' \texttt{initial\_liquidity\_fraction} stable (relative change $\leq$ 5\%) for 5 consecutive iterations, indicating policy stability
\end{itemize}

\textbf{Important limitation}: This mode identifies \textit{stable policy profiles}---points where agents stop adjusting their parameters---not optimal outcomes or game-theoretic equilibria. Unconditional acceptance means agents can ``converge'' to profiles with higher costs than baseline if early myopic improvements lead them into coordination traps. The resulting profiles reflect the dynamics of independent, non-communicating agents optimizing greedily, which may produce coordination failures rather than Pareto-efficient outcomes.

\subsubsection{Bootstrap Mode (Experiment 2)}

For stochastic scenarios, we use \textbf{per-iteration bootstrap resampling} with pre-generated seeds
for deterministic reproducibility.

\paragraph{Seed Hierarchy.}
Seeds are generated deterministically from a single master seed:
\begin{enumerate}
    \item \textbf{Master seed}: Fixed per experiment for reproducibility
    \item \textbf{Iteration seeds}: 50 seeds derived from master (one per iteration per agent)
    \item \textbf{Bootstrap seeds}: 50 seeds derived from each iteration seed (one per sample)
\end{enumerate}
This produces $50 \times 50 = 2{,}500$ unique seeds per agent, ensuring full stochastic exploration
while maintaining paired comparison integrity within iterations.

\paragraph{Per-Iteration Evaluation.}
Each iteration proceeds as follows:
\begin{enumerate}
    \item \textbf{Context simulation}: Run full simulation with the iteration-specific seed,
    generating a unique transaction history for this iteration (different stochastic arrivals
    than other iterations)
    \item \textbf{Bootstrap sampling}: Generate 50 transaction schedules by resampling with
    replacement from this iteration's history. Each resampled transaction includes both
    \textit{payment instruction fields} (arrival tick, amount, deadline, counterparty) and
    a \texttt{settlement\_offset} field recording when the transaction settled relative to arrival
    \item \textbf{Paired comparison}: Evaluate both old and new policy on the \textit{same} 50 samples,
    computing $\delta_i = \text{cost}_{\text{old},i} - \text{cost}_{\text{new},i}$
    \item \textbf{Acceptance}: Apply risk-adjusted criteria (see below)
\end{enumerate}

The paired comparison on identical samples eliminates sample-to-sample variance, enabling detection
of smaller policy improvements than unpaired comparison would allow.

\paragraph{Sandbox Evaluation and Settlement Timing.}
Each bootstrap sample is evaluated in a \textbf{3-agent sandbox} (SOURCE$\rightarrow$AGENT$\rightarrow$SINK)
rather than a full multi-agent simulation. The resampled transactions include a \texttt{settlement\_offset}
field---the time between transaction arrival and settlement observed in the context simulation. This
offset encodes the liquidity environment's ``market response'' to the agent's transactions.

The sandbox replays this historical timing: SOURCE provides incoming liquidity at the originally-observed
settlement times, treating settlement timing as an \textbf{exogenous sufficient statistic} for the
liquidity environment. This design choice has two implications:
\begin{itemize}
    \item \textit{Advantage}: Eliminates confounding from counterparty policy changes and LSM cycle
    dynamics, enabling clean policy comparison.
    \item \textit{Limitation}: Evaluates policies under \textbf{historical timing}, not the timing
    that would result from policy-induced changes in system liquidity. Specifically, \textbf{bilateral
    feedback loops are frozen}: if AGENT pays counterparty B earlier under a new policy, this does
    not cause B to return liquidity earlier---SOURCE sends incoming payments at fixed historical times
    regardless of AGENT's actions. The bootstrap answers ``how would this policy perform given the
    observed market response?'' rather than ``how would this policy perform in the equilibrium it induces?''
\end{itemize}

This fixed-environment assumption is most restrictive in simplified 2-agent scenarios like our
experiments, where each agent constitutes 50\% of system volume. In realistic RTGS systems with
dozens of participants and diverse transaction flows, an individual agent's policy changes have
smaller marginal effects on system-wide settlement timing, making the exogeneity assumption
more defensible. The 2-agent experiments here are designed to demonstrate specific strategic
behaviors under controlled conditions, not to provide practically-applicable bootstrap evaluation
for production systems.

\paragraph{Risk-Adjusted Acceptance Criteria.}
Policy acceptance requires three criteria to prevent accepting inferior or unstable policies:

\begin{enumerate}
    \item \textbf{Mean improvement}: The new policy must have lower mean cost than the current
    policy ($\mu_{\text{new}} < \mu_{\text{old}}$), computed via paired comparison on the same
    50 bootstrap samples.

    \item \textbf{Statistical significance}: The improvement must be statistically significant.
    Specifically, the 95\% confidence interval for the paired cost delta
    ($\delta_i = \text{cost}_{\text{old},i} - \text{cost}_{\text{new},i}$) must not cross zero.
    This prevents accepting policies whose improvement could be due to random chance.

    \item \textbf{Variance guard}: The new policy's coefficient of variation
    (CV = $\sigma_{\text{new}} / \mu_{\text{new}}$), computed over costs across the 50
    bootstrap samples, must be below 0.5. This prevents accepting policies with lower
    mean cost but unacceptably high variance, which would result in unpredictable performance
    under adverse market conditions.
\end{enumerate}

All three criteria are configurable per experiment. This approach draws from mean-variance
optimization principles and ensures that accepted policies are both effective \textit{and} stable.

\paragraph{Bootstrap Variance Limitations.}
The variance guard uses bootstrap variance as a heuristic filter for sensitivity to timing
perturbations, but this measure has known limitations. Transaction-level resampling with
\texttt{settlement\_offset} can create duplicate extreme transactions and non-physical
correlations between arrivals and settlement timing, potentially amplifying tail events beyond
what the original generative process and endogenous timing would produce. In our experiments,
final policies showed CV $\approx$ 2.0 under bootstrap evaluation despite stable policy
parameters, suggesting the bootstrap CV measures sensitivity to resampled timing rather than
true cross-day performance variance.

For applications to real RTGS data---which exhibits substantial intra-day variability in
payment volumes and timing---more sophisticated resampling methods would be necessary.
\textbf{Block bootstrap} (resampling contiguous time windows) or \textbf{day-level bootstrap}
(resampling entire business days) would better preserve temporal dependencies. Alternatively,
\textbf{held-out seed evaluation}---testing final policies on previously-unseen stochastic
seeds---would measure true cross-day variance rather than resampling sensitivity.

\paragraph{Convergence Criterion.}
Three criteria must ALL be satisfied over a 5-iteration window:
\begin{enumerate}
    \item Coefficient of variation below 3\% (cost stability across iteration means)
    \item Mann-Kendall test $p > 0.05$ (no significant trend---with only 5 iterations, this is a heuristic)
    \item Regret below 10\% (current cost within 10\% of best observed)
\end{enumerate}

\textit{Note: CV is computed over iteration means, not individual bootstrap samples.}

\subsection{Experimental Setup}

We implement three canonical scenarios from Castro et al.\ (2025):

\textbf{Experiment 1: 2-Period Deterministic} (Deterministic-Temporal Mode)
\begin{itemize}
    \item 2 ticks per day
    \item Asymmetric payment demands: $P^A = [0, 0.15]$, $P^B = [0.15, 0.05]$
    \item Bank A sends 0.15$B$ at tick 1; Bank B sends 0.15$B$ at tick 0, 0.05$B$ at tick 1
    \item Expected equilibrium: Asymmetric (A=0\%, B=20\%)
\end{itemize}

\textbf{Experiment 2: 12-Period Stochastic} (Bootstrap Mode)
\begin{itemize}
    \item 12 ticks per day
    \item Poisson arrivals ($\lambda=2.0$/tick), LogNormal amounts ($\mu$=10k, $\sigma$=5k)
    \item Expected equilibrium: Both agents in 10--30\% range
\end{itemize}

\textbf{Experiment 3: 3-Period Symmetric} (Deterministic-Temporal Mode)
\begin{itemize}
    \item 3 ticks per day
    \item Symmetric payment demands: $P^A = P^B = [0.2, 0.2, 0]$
    \item Expected equilibrium: Symmetric ($\sim$20\%)
\end{itemize}

\subsection{Comparison with Castro et al.\ (2025)}

Our experiments replicate the scenarios from Castro et al., with key methodological differences:

\begin{itemize}
    \item \textbf{Optimization method}: Castro et al.\ use REINFORCE (policy gradient with neural networks trained over 50--100 episodes); we use LLM-based policy optimization with natural language reasoning
    \item \textbf{Action representation}: Castro et al.\ discretize $x_0 \in \{0, 0.05, \ldots, 1\}$ (21 values); our LLM proposes continuous values in $[0,1]$
    \item \textbf{Convergence}: Castro et al.\ monitor training loss curves; we use explicit policy stability (temporal) or multi-criteria statistical convergence (bootstrap) detection
    \item \textbf{Multi-agent dynamics}: Castro et al.\ train two neural networks simultaneously with gradient updates; we optimize agents sequentially within each iteration, checking for mutual best-response stability
\end{itemize}

\subsection{LLM Configuration}

\begin{itemize}
    \item Model: \texttt{openai:gpt-5.2}
    \item Reasoning effort: \texttt{high}
    \item Temperature: 0.5
    \item Max iterations: 50 per pass
\end{itemize}

Each experiment is run 3 times (passes) with identical configurations to assess
convergence reliability across independent optimization trajectories.
"""
