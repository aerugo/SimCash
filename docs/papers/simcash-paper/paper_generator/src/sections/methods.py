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
    \item \textbf{Deadline penalty}: Incurred when transactions become overdue
    \item \textbf{End-of-day penalty}: Large cost for unsettled transactions at day end
    \item \textbf{Overdraft cost}: Fee for negative balance (basis points per day)
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
    replacement from this iteration's history, preserving settlement offset distributions
    \item \textbf{Paired comparison}: Evaluate both old and new policy on the \textit{same} 50 samples,
    computing $\delta_i = \text{cost}_{\text{old},i} - \text{cost}_{\text{new},i}$
    \item \textbf{Acceptance}: Apply risk-adjusted criteria (see below)
\end{enumerate}

The paired comparison on identical samples eliminates sample-to-sample variance, enabling detection
of smaller policy improvements than unpaired comparison would allow.

\paragraph{Risk-Adjusted Acceptance Criteria.}
Policy acceptance uses a two-stage evaluation to prevent accepting unstable policies:

\begin{enumerate}
    \item \textbf{Statistical significance}: The improvement must be statistically significant.
    Specifically, the 95\% confidence interval for the cost delta must not cross zero
    ($\sum_i \delta_i > 0$ is necessary but not sufficient). This prevents accepting policies
    whose improvement could be due to random chance.

    \item \textbf{Variance guard}: The new policy's coefficient of variation
    (CV = $\sigma / \mu$) must be below 0.5. This prevents accepting policies with lower
    mean cost but unacceptably high variance, which would result in unpredictable performance
    under adverse market conditions.
\end{enumerate}

Both criteria are configurable per experiment. This approach draws from mean-variance
optimization principles and ensures that accepted policies are both effective \textit{and} stable.

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
