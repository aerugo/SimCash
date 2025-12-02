# Estimating Policy Functions in Payment Systems Using Reinforcement Learning

**Authors:**
Pablo Castro (Brain Team, Google Research, Montreal, Canada)
Ajit Desai (Banking and Payments Research, Bank of Canada, Ottawa, Canada)
Han Du (Bank of Canada, Ottawa, Canada)
Rodney Garratt (University of California, Santa Barbara, United States)
Francisco Rivadeneyra (Bank of Canada, Ottawa, Canada)

*The opinions here are those of the authors and do not necessarily reflect those of the Bank of Canada or Google. Author order is alphabetical.* 

---

## Abstract

This article uses reinforcement learning (RL) to approximate the policy rules of banks participating in a high-value payment system (HVPS). The objective of the RL agents is to learn a policy function for the choice of amount of liquidity provided to the system at the beginning of the day and the rate at which to pay intraday payments. Individual choices have complex strategic effects precluding a closed-form solution of the optimal policy, except in simple cases.

We show that, in a stylized two-agent setting, RL agents learn the optimal policy that minimizes the cost of processing their individual payments—without complete knowledge of the environment. We further demonstrate that, in more complex settings, both agents learn to reduce the cost of processing their payments and effectively respond to the liquidity–delay tradeoff. Our results show the potential of RL to solve liquidity management problems in HVPS and provide new tools to assist policymakers in their mandates of ensuring safety and improving the efficiency of payment systems.

---

### CCS Concepts

* **Computing methodologies → Multi-agent reinforcement learning**

### Additional Key Words and Phrases

Artificial intelligence, reinforcement learning, high-value payment systems

### ACM Reference Format

Pablo Castro, Ajit Desai, Han Du, Rodney Garratt, and Francisco Rivadeneyra. 2025. *Estimating Policy Functions in Payment Systems Using Reinforcement Learning*. ACM Trans. Econ. Comput. 13, 1, Article 1 (February 2025), 31 pages. [https://doi.org/10.1145/3691326](https://doi.org/10.1145/3691326)

> This work is licensed under a Creative Commons Attribution-NoDerivs International 4.0 License.

---

## 1. Introduction

High-value payment systems (HVPSs) settle transactions between large financial institutions, usually banks, and are considered part of the core national financial infrastructure. The Canadian HVPS, for example, processes payment values equivalent to annual GDP every five days.

HVPSs are real-time systems where transactions settle using liquidity provided by the central bank in exchange for collateral. Collateral has an opportunity cost, and incoming payments can provide liquidity for outgoing payments. As a result, banks face a liquidity management game in which they have an incentive to delay outgoing payments instead of acquiring more central-bank liquidity.

Central banks, which operate these systems and have mandates to ensure safety and efficiency, are interested in understanding banks’ behavior. In this article, we show how reinforcement learning (RL) can be used to estimate the optimal policy for both banks’ initial liquidity allocation and the rate at which intraday payments are made, both independently and concurrently.

The initial liquidity decision is complex. In a system with multiple banks and multiple periods with arriving payment requests, researchers have been unable to solve for the equilibrium initial liquidity profile. This raises two questions:

1. If equilibrium strategies are difficult to determine, what do banks actually do?
2. Can advanced machine learning techniques find equilibrium solutions and potentially guide practitioners and infrastructure providers?

There is a growing economics literature on agent-based modeling of actors in payment systems that addresses the first question. This article focuses largely on the second: as an initial investigation into the potential application of ML to payment systems, we examine whether these techniques can deliver solutions.

Estimating policy functions in payment systems matters for at least two more reasons:

1. **Regulatory perspective.** If system participants eventually adopt such algorithms, knowledge of these policy functions could help regulators assess the liquidity and risk implications, aiding their safety and efficiency mandates.
2. **System design.** Understanding equilibrium behavior through these policy functions can inform the design of new payment systems, especially given ongoing modernization efforts worldwide.

Reinforcement learning is a computational approach to sequential decision-making that emphasizes trial-and-error learning. An agent interacts with an environment, associates actions with states, and seeks to maximize cumulative rewards. RL accommodates stochastic environments, large state spaces, and multiple agents learning simultaneously, making it particularly suitable for estimating policy functions in payment systems, where the agent learns to process payments at minimum cost.

We begin with a 2-period model of an HVPS with known customer payment requests to illustrate the liquidity management problem. We then consider a 12-period model in which payment requests are drawn from payment profiles observed in Canadian LVTS (Large Value Transfer System) data. In both cases, the RL agent does **not** know whether payment demand is constant, drawn from a distribution, or whether that distribution changes over time. The agent learns about the environment by experimenting with liquidity choices to minimize its payment processing cost.

For the 2-period fixed-payment model, we can solve the game analytically. We derive each bank’s best-response function and compute the Nash equilibrium. This gives a ground-truth solution against which we can evaluate the RL estimates. For the more realistic 12-period model with actual payment requests, we cannot solve analytically but can compute the solution via brute-force search, again providing a target outcome.

In both the 2-period and 12-period analyses, banks can choose a *divisible* quantity of payments to process in each period, even though HVPS payments are typically indivisible (banks cannot split legally binding payments). This is reasonable because banks process many payments of different sizes and can effectively choose subsets of small payments to approximate a divisible choice.

Still, some banks may face binding constraints from large indivisible payments. To capture this, we consider a 3-period scenario: the bank receives a large indivisible payment in period 2 and no additional small payments. The bank may then strategically delay small payments from period 1 to avoid the high cost of delaying the large payment in period 2, adding an inter-period tradeoff to the Liquidity–Delay tradeoff and complicating the learning problem.

Our results show that RL can replicate equilibrium behavior and learn complex initial liquidity decisions without full knowledge of the environment. We use the model to study the liquidity–delay tradeoff and quantify the importance of the relative sizes of initial liquidity and delay costs. Because delay costs are unobservable to researchers and policymakers, estimating sensitivity of best responses to delay costs is helpful. Our special-case results indicate that RL agents effectively adapt and learn to manage intraday tradeoffs and liquidity–delay dynamics.

We proceed as follows:

* Section 2 discusses related literature.
* Section 3 describes the stylized payment system environment.
* Section 4 derives the game-theoretical equilibrium for a simplified environment.
* Section 5 discusses the RL algorithm and multi-agent setup.
* Section 6 trains the initial liquidity policy.
* Section 7 trains agents to learn initial liquidity and intraday payments jointly.
* Section 8 concludes.
* Appendices provide technical details, robustness checks, and additional results.

---

## 2. Related Literature

On analytical studies of the liquidity–delay tradeoff in payment systems, this work is related to empirical work that examines initial liquidity choice and simulates agent-based versions of the game, and to models that study interbank liquidity flows and systemic risk propagation under stress.

Agent-based models help build intuition about behavior but typically require strong assumptions on objective functions. In contrast, our RL approach only assumes that agents seek to minimize payment processing costs.

From the applied game theory perspective, this article builds on earlier work that models intraday liquidity games theoretically. In prior models, banks that receive customer payment requests choose whether to provide liquidity in the morning or delay to the afternoon, hoping to fund payments with incoming liquidity but incurring customer dissatisfaction costs from delays. Our initial liquidity decision is closely related to those models but differs in that agents decide **before** observing requests and face a more complex demand environment.

More broadly, this article contributes to a growing literature at the intersection of economics and machine learning. For example:

* RL agents have been used to study algorithmic pricing and the possibility of tacit collusion without direct coordination, raising policy concerns.
* Other work compares structural estimation in econometrics with dynamic programming and RL in two-player perfect-information games (chess, Go).
* Multi-agent RL has been used to analyze pricing strategies and learning behavior in electronic marketplaces.

Our setting is more challenging because it involves complex strategic interactions among more than one learning agent in a game of imperfect information that may yield cooperative or non-cooperative solutions.

More generally, this work connects to game theory literature on learning in games—how equilibria emerge through RL or other learning mechanisms. Our convergence results in special cases are consistent with conditions for convergence to a unique equilibrium in stochastic adaptive learning models.

Recent work has also used RL to learn dynamic tax policies, showing the potential of AI-based methods for economic policy design. In another related paper, researchers explore how quantum computing and payment reordering could reduce liquidity usage in HVPS.

---

## 3. The Payment System Environment

We model a **real-time gross settlement (RTGS)** payment system:

* Transactions settle in real time without netting (offsetting bilateral positions cannot cancel even if simultaneous).
* Banks receive exogenous, random payment demands from clients throughout the day.
* Liquidity is obtained via collateral posted at the central bank (costly due to an opportunity cost) or via incoming payments (cheaper).

This creates an incentive to delay payments to await incoming funds. Delays are costly because banks must meet clients’ timing expectations.

Banks must choose a policy that balances **initial liquidity costs** and **delay costs**, taking into account other banks’ policies. At the end of the day, banks must settle all payment demands. If liquidity is insufficient, banks can borrow from the central bank at a rate higher than the morning collateral cost.

Time is discrete. Each day is an episode ( e ), subdivided into intraday periods ( t = 0,1,2,\dots,T ).

* At ( t = 0 ) (start of the day) the agent chooses what share ( x_0 \in [0,1] ) of collateral ( B ) to allocate as initial liquidity:
  [
  \ell_0 = x_0 \cdot B.
  ]
* At each period ( t = 1,\dots,T-1 ), the agent:

  * Receives payment demands ( P_t ).
  * Chooses a share ( x_t \in [0,1] ) of requested payments to send.

The choice is constrained by available liquidity ( \ell_{t-1} ) in that period:

[
P_t x_t \le \ell_{t-1}.
]

At the end of each period, the agent receives incoming payments ( R_t ) from other agents. Liquidity evolves as:

[
\ell_t = \ell_{t-1} - P_t x_t + R_t.
]

The cost structure is:

* Cost of initial liquidity: ( r_c \cdot \ell_0 ).
* Cost of delay in period ( t ): ( r_d \cdot P_t(1 - x_t) ).
* If at ( T-1 ) liquidity is insufficient to cover remaining demands, the agent borrows from the central bank an amount ( c_b ) at rate ( r_b ), with ( r_b > r_c ).

**Table 1 (page 6). Timeline, decisions, and constraints**

| Stage                        | Variable(s)                           | Description                                            |
| ---------------------------- | ------------------------------------- | ------------------------------------------------------ |
| **Beginning of day (t=0)**   | Collateral (B)                        | Available collateral                                   |
|                              | (x_0 \in [0,1])                       | Initial liquidity decision (fraction of (B))           |
|                              | (\ell_0 = x_0 \cdot B)                | Initial liquidity allocation                           |
|                              | Cost (r_c \ell_0)                     | Cost of initial liquidity                              |
| **Intraday (t=1,\dots,T-1)** | (P_t)                                 | Payment demand                                         |
|                              | (x_t \in [0,1])                       | Share of demand sent in period (t)                     |
|                              | Constraint (P_t x_t \le \ell_{t-1})   | Liquidity constraint                                   |
|                              | (R_t)                                 | Incoming payments from others                          |
|                              | (\ell_t = \ell_{t-1} - P_t x_t + R_t) | Liquidity evolution                                    |
|                              | Cost (r_d P_t(1 - x_t))               | Per-period delay cost                                  |
| **End of day (t = T)**       | Borrowing (c_b)                       | Borrowing from central bank to meet remaining payments |
|                              | Cost (r_b c_b)                        | End-of-day borrowing cost                              |

(*summarizing the structured table on page 6*)

RL is well-suited for this environment. Agents learn state–action mappings that minimize cumulative cost by repeated interaction with the environment.

Our model abstracts from two real-world features:

1. **Indivisible payments.** In practice, payments cannot be split; they must settle in full or not at all. We assume continuous payment demands and allow fractional settlement ( x_t \in [0,1] ). This is a reasonable approximation when many small payments aggregate to a continuous quantity.
2. **Interbank liquidity markets.** Banks can typically borrow liquidity from other banks intraday; we omit this, focusing only on central-bank liquidity and incoming payments. Extending the model to include interbank markets is left for future work.

---

## 4. The Initial Liquidity Game

We define a one-shot **initial liquidity game** with two agents ( i \in {A,B} ) who simultaneously choose initial liquidity ( \ell_0^i ) to minimize total processing costs over the day. We analyze the case with known payments and two intraday periods ( T=2 ); the empirical analysis later uses the richer 12-period case.

Total payment demand for agent ( i ) is:

[
P^i = P^i_1 + P^i_2.
]

Agents are assumed to behave optimally intraday given their liquidity: whenever they have liquidity, they send as many payments as possible, i.e. ( x_t = 1 ) whenever feasible. The remaining value of payments to be sent at period ( t ) is then:

[
\max(P_t - \ell_{t-1}, 0), \quad t = 1,2.
]

Total cost as a function of initial liquidity ( \ell_0 ) is:

[
R(\ell_0) = r_c \ell_0 + \max(P_1 - \ell_0, 0), r_d + \max(P_2 + P_1 - R_1 - \ell_0, 0), r_b,
]

where ( r_c < r_d < r_b ) are the per-unit costs of initial liquidity, delay, and end-of-day borrowing, respectively, and ( R_1 ) is payments received in period 1 (available in period 2).

We consider four cases depending on:

* Whether ( \ell_0 ) exceeds period-1 demand ( P_1 ), and
* Whether ( \ell_0 ) exceeds net total demand ( P - R_1 ).

Let ( P = P_1 + P_2 ). Then:

1. **Case 1:** ( \ell_0 > P_1 ) and ( \ell_0 > P - R_1 )
   Initial liquidity covers all payments in both periods; total cost:
   [
   R = r_c \ell_0.
   ]

2. **Case 2:** ( \ell_0 > P_1 ) and ( \ell_0 < P - R_1 )
   Liquidity covers period 1, but not total net demand. End-of-day borrowing is required:
   [
   R = (r_c - r_b)\ell_0 + (P - R_1), r_b.
   ]

3. **Case 3:** ( \ell_0 < P_1 ) and ( \ell_0 > P - R_1 )
   Liquidity is insufficient in period 1 but sufficient overall given a large enough ( R_1 ). Cost includes delay in period 1:
   [
   R = (r_c - r_d)\ell_0 + P_1 r_d.
   ]

4. **Case 4:** ( \ell_0 < P_1 ) and ( \ell_0 < P - R_1 )
   Liquidity is insufficient in both periods; cost includes delay and borrowing:
   [
   R = (r_c - r_d - r_b)\ell_0 + P_1 r_d + (P - R_1) r_b.
   ]

**Assumptions:**

* Agents are risk-neutral and choose ( \ell_0 ) to minimize ( R(\ell_0) ).
* The payment profile is common knowledge.
* ( r_c < r_b ), so end-of-day borrowing is more expensive than morning liquidity and there is no compensation for positive end-of-day balances (e.g., if ( R_1 > P )).

**Definition 1 (Nash equilibrium).**
A pure-strategy Nash equilibrium of the initial liquidity game is a pair ( (\ell_0^A, \ell_0^B) ) such that, for each ( i \in {A,B} ),
[
\ell_0^i = \arg\min_{\ell_0} R^i(\ell_0).
]

The best-response function for agent ( i ) is:

[
\ell_0^i = P^i_1 + \max\big( P^i_2 - \min(\ell_0^{-i}, P_1^{-i}), 0 \big),
]
where ( -i ) denotes the other agent.

Intuition:

* The agent must at least cover its period-1 demand, since outgoing payments are not returned as liquidity until period 2. Deviating from this would add delay costs, which are more expensive than initial liquidity.
* The second term is net liquidity needed for period 2, after accounting for expected incoming payments from the other agent. Under optimal intraday policies, the received payment is the minimum of the other agent’s initial liquidity and its own period-1 demand.

Given ( r_c < r_d < r_b ), the cost function has a unique minimum. There is a unique Nash equilibrium. Even if the other agent deviates (e.g., choosing zero liquidity), the best response remains to cover both periods’ demands ( P_1^i + P_2^i ) when required by the formula above.

### Figure 1 (page 8): Cost function and equilibrium

**Figure 1** plots cost as a function of initial liquidity and shows the Nash equilibrium for a special case with ( P_1^A > 0 ), ( P_1^B = 0 ), and ( P_2^B > P_1^A ).

| Panel | Description                                                                                                    |
| ----- | -------------------------------------------------------------------------------------------------------------- |
| Left  | Cost curves ( R^A(\ell_0) ) and ( R^B(\ell_0) ) as functions of initial liquidity, showing unique minima.      |
| Right | Best-response functions for A and B, with intersection representing the unique pure-strategy Nash equilibrium. |

This equilibrium provides a benchmark for the RL training in Section 6. Note that standard game-theoretic solutions presume complete knowledge of payoffs and state space; in contrast, our RL agents do not know the payment profiles, the presence or behavior of the other agent, or the game structure.

---

## 5. HVPS as a Multi-Agent Reinforcement Learning Problem

Reinforcement learning methods optimize an agent’s behavior in an uncertain environment through interaction. At each time step ( t ), while in state ( s_t \in S ), the agent chooses an action ( a_t \in A ), receives a cost ( r_t ), and transitions to state ( s_{t+1} ). The goal is to learn a policy ( \pi: S \to A ) that minimizes cumulative cost.

In this article, we train **two agents concurrently** in the same environment, which yields complex learning dynamics.

### Learning setup (high level)

* Two agents (representing banks) interact with a shared environment (the payment system).
* Each agent has its own policy network (a neural net) mapping states to action probabilities.
* States include current period, current liquidity, and payment demands.
* The environment returns individual costs (liquidity, delay, and borrowing) and new states.
* Agents update policies using the observed costs.

**Figure 2 (page 9). Multi-agent RL in a payment system**

| Element | Description                                                                        |
| ------- | ---------------------------------------------------------------------------------- |
| Agents  | Two separate policy networks (grey) for agents A and B.                            |
| Inputs  | Current state features (blue): period, liquidity, payment demands, etc.            |
| Actions | Chosen liquidity and payment fractions (red).                                      |
| Costs   | Components (green): initial liquidity cost, delay cost, end-of-day borrowing cost. |

The same learning algorithm is used for both agents, but they learn independently and maintain separate policies.

Because the environment is complex, we **decouple** learning tasks:

1. **Initial liquidity decision:** Train agents’ initial liquidity policy while fixing intraday policy to always send payments (no strategic delay).
2. **Intraday policy:** Separately, verify that agents can learn to send as much as possible each period when given sufficient free liquidity (Appendix A).
3. **Joint learning:** Later, allow simultaneous learning of initial liquidity and intraday payment decisions.

This decomposition allows us to validate the RL algorithm against known solutions.

The learning task is **episodic**: one episode is one settlement day, divided into hourly intraday periods. At the last period, agents must satisfy all payment demands; any shortfall triggers automatic borrowing from the central bank at fixed cost. The central bank is non-strategic and always lends the required amount.

For tractability, we restrict to **two agents**, with exogenous payment demands between them. This is still informative if in practice banks apply a single policy function across counterparties and do not condition on the identity of the payer/receiver. A more realistic system with multiple counterparties and counterparty-specific policies is a natural extension but significantly harder to train.

Critically, agents’ states **do not reveal** whether they interact with one or many counterparties. This partial observability makes learning harder: decisions of one agent affect the other’s liquidity and costs, and cannot be directly inferred from the state.

---

## 6. Initial Liquidity Policy Estimation

### 6.1 Learning Setup

We consider two scenarios:

* A **2-period** case (( T = 2 )), where an analytical solution exists.
* A **12-period** case (( T = 12 )), closer to real-world operation.

In both, two agents A and B are trained simultaneously.

**Key elements:**

* **Payment demand:** Drawn from LVTS data (see Section 6.2 and Figure 3).
* **Intraday policy:** Fixed to “send all possible payments,” i.e. no strategic delay. Specifically:

  * If ( P_t < \ell_{t-1} ) then ( x_t = 1 ).
  * Otherwise, send all liquidity: ( x_t = \ell_{t-1}/P_t ).
* **State:** The agent observes the full vector of intraday payment demands for that episode.
* **Action:** The initial liquidity fraction ( x_0 \in [0,1] ), discretized into 21 evenly spaced values ({0, 0.05, 0.10, \ldots, 1}). Intraday decisions ( x_t ) are fixed.
* **Cost:** Total cost per episode:
  [
  R = r_c \ell_0 + \sum_{t=1}^{T-1} P_t(1 - x_t) r_d + r_b c_b,
  ]
  where ( r_c ) is initial liquidity cost, ( r_d ) delay cost, and ( r_b ) end-of-day borrowing cost. The last two terms depend on whether initial liquidity covered all payments.

### 6.2 Data and Parameters

Payment demands are constructed from actual transactions between two participants in the Canadian LVTS over 380 business days (Jan 2, 2018 – Aug 30, 2019). For each day:

* The day runs roughly from 6 a.m. to 6 p.m.
* We create 12 hourly periods.
* For each hour, we sum bilateral payments between the two chosen participants.
* Values are standardized as a percentage of that day’s collateral pledged by each participant.

The sample is randomly split:

* 90% for training
* 10% for testing

**Figure 3 (page 11). Payment data**

| Panel | Description                                                                                                                                                             |
| ----- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Left  | Bar chart of hourly average payment demands and standard deviations between the two banks. Agent B has higher average demands and wider dispersion, with earlier peaks. |
| Right | Cumulative payment value over the day, showing smoother aggregate profiles for both agents.                                                                             |

Baseline cost parameters:

* Initial liquidity cost: ( r_c = 0.1 )
* Per-period delay cost: ( r_d = 0.2 )
* End-of-day borrowing cost: ( r_b = 0.4 )

These costs reflect the institutional reality:

* Borrowing from the central bank is deliberately expensive (e.g. 25 bps above the policy rate).
* Banks post substantial collateral but not enough to cover all payments individually, indicating non-negligible liquidity costs (including collateral management and reallocation frictions).

Delay costs, tied to contractual obligations and potential penalties, are unobserved. Theoretical work allows both high and low delay costs relative to liquidity costs. As a baseline, we set ( r_c < r_d < r_b ) and later vary ( r_d ) in robustness checks (Section 6.4).

**Algorithm and architecture**

* Algorithm: REINFORCE (policy gradient method).
* Implementation: Python + TensorFlow.
* Policy: Feed-forward neural network mapping state to action probabilities.
* For each episode, multiple trajectories are generated using current policies. Policy parameters are updated at episode end using gradient estimates.
* Multiple independent training runs provide confidence intervals over policies and costs.

### 6.3 Results: Two-Period Case ((T = 2))

To illustrate, we use dummy symmetric payment demands with the same support as the action grid:

* Agent A: ( P^A = [0, 0.15] )
* Agent B: ( P^B = [0.15, 0.05] )

Each vector entry is demand in one period. The cost simplifies to:

[
R = r_c \ell_0 + P_1(1 - x_1) r_d + r_b c_b
]
for both agents.

Agent B receives no first-period incoming payment and must allocate liquidity equal to total demand to avoid delay and borrowing (given ( r_c < r_d < r_b )). If B does so, it sends ( 0.2 ) in payments, which A receives in period 2. Agent A can then cover its own second-period demand using the incoming payment and optimally sets ( \ell_0^A = 0 ). This yields optimal costs ( R_A = 0 ), ( R_B = 0.02 ) (since ( 0.2 \times 0.1 = 0.02 )).

Agents are trained via 50 independent runs of 50 episodes each.

**Figure 4 (page 13). Training costs and liquidity choices (2-period case)**

| Panel | Description                                                                                                                                                                                      |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Left  | Average training cost over episodes for both agents. Costs converge to theoretical optima (R_A = 0), (R_B = 0.02).                                                                               |
| Right | Average initial liquidity decisions over episodes. Agents converge to optimal liquidity levels (0 for A, 0.2 for B), shown as red lines. Shaded bands show 99% confidence intervals across runs. |

Agents quickly learn near-optimal actions, with B converging to higher cost due to higher payment demand and lack of incoming flow.

### 6.4 Results: Twelve-Period Case ((T = 12))

We now use LVTS demands (Figure 3) and train both agents simultaneously for 100 episodes.

**Figure 5 (page 13). Training and testing costs (12-period case)**

| Panel | Description                                                                                               |
| ----- | --------------------------------------------------------------------------------------------------------- |
| Left  | Agent A’s average training and testing costs over episodes. Costs flatten near minimum around episode 60. |
| Right | Agent B’s costs; similar pattern with higher levels and somewhat wider variance.                          |

We perform 50 independent training runs. Confidence intervals show that while costs converge, agents do **not** converge to a single deterministic liquidity level, likely due to:

* The non-stationary environment (each agent’s actions affect the other).
* Randomness in payment realizations and exploration.

**Figure 6 (page 14). Evolution of initial liquidity ( x_0 )**

* Both agents start by allocating around 50% of collateral.
* Over training, both reduce liquidity; agent A (lower demand) reduces more.
* Agent B converges to a higher liquidity share than A, consistent with higher demand.
* Neither agent collapses to a single deterministic action; choices fluctuate within a band.

Learning is slower and more variable than in the 2-period case, reflecting higher complexity (more periods, real data, strategic interactions).

Since no analytical solution exists for (T=12), we later compute a **brute-force planner benchmark** (Appendix C) to gauge efficiency.

### Sensitivity to Delay Cost

Because delay cost ( r_d ) is unobservable, we study its impact by varying ( r_d ) from 0.01 to 0.3, keeping ( r_c = 0.1 ) and ( r_b = 0.4 ).

**Figure 7 (page 15). Boxplots of final costs vs. delay cost**

* When ( r_d > r_c ), both agents allocate more liquidity, raising total cost to avoid delays. Sensitivity is modest.
* When ( r_d < r_c ), agent A’s cost becomes highly sensitive. As the lower-demand bank, A finds it optimal to **wait for incoming payments** when delay is cheap, reducing initial liquidity and total cost.

Interestingly, for ( r_d \le r_c ), the best-response functions differ from Section 4, even in the 2-period case: agents may allocate less liquidity and rely more on incoming payments when delay is cheap.

Robustness checks (Appendix E.5) show that when agents have similar payment profiles, variation in ( r_d ) has limited effect, but when profiles differ substantially, delay cost matters significantly.

---

## 7. Initial Liquidity **and** Intraday Payments: Joint Policy Estimation

We next allow agents to **jointly learn** initial liquidity and intraday payment policies, in a more stylized 3-period environment.

### 7.1 Joint Action Learning Setup

* **Periods:** (T = 3).

* **Agents:** A and B, trained simultaneously.

* **Payment demand scenarios:**

  1. All payments **divisible** in all three periods.
  2. Payments in period 2 **indivisible** for one agent (lumpy, must be paid in full or not at all), others divisible.

* **Action space:**

  * Initial liquidity ( x_0 \in {0, 0.05, \dots, 1} ).
  * Intraday payment fraction ( x_t ):

    * Divisible periods: 21-point grid in ([0,1]).
    * Indivisible periods: binary ( {0,1} ) (send nothing or the entire request).

* **State:**
  For intraday decisions, at each ( t ) the state is:
  [
  s_t = (t, p_t, P_t, \ell_t),
  ]
  where:

  * ( p_t ): new payment demand in period ( t )
  * ( P_t ): accumulated demand including previously delayed payments
  * ( \ell_t ): current liquidity

* **Cost:** Same as before:
  [
  R = r_c \ell_0 + \sum_{t=1}^{T-1} P_t(1 - x_t) r_d + r_b c_b.
  ]

Agents can incur both delay and borrowing costs due to interaction of initial and intraday choices.

### 7.2 Results: Three-Period Dummy Example

We use symmetric dummy demands:

[
P^A = P^B = [0.2, 0.2, 0].
]

Agents are trained for 200 episodes.

#### Scenario 1: All Payments Divisible

Here, agents do **not** need to strategically delay payments intraday; they can adjust continuously. But there is still a liquidity–delay tradeoff.

We consider two sub-cases:

1. **Liquidity cheaper than delay** (( r_c < r_d ))

   **Figure 8 (page 17). Liquidity and period-1 payments under ( r_c < r_d )**

   * Agents allocate more initial liquidity (≈25% of collateral on average).
   * They delay relatively few payments (up to about 10% delayed in expectation).

2. **Delay cheaper than liquidity** (( r_d < r_c ))

   **Figure 9 (page 17). Liquidity and period-1 payments under ( r_d < r_c )**

   * Agents allocate less initial liquidity (≈20% of collateral).
   * They delay more payments (up to about 25% delayed).

These outcomes demonstrate that agents correctly internalize the liquidity–delay tradeoff: when delay is expensive, they front-load liquidity; when liquidity is expensive, they tolerate more delay.

#### Scenario 2: Indivisible Payment in Period 2

Agent B faces an indivisible payment in period 2, while all other payments (B in other periods and A in all periods) are divisible. Agent B may strategically delay payments from period 1 to save liquidity for the indivisible payment.

**Figure 10 (page 17). Liquidity and period-1 payments with indivisible payment**

* On average, agent B:

  * Allocates slightly **less** initial liquidity than agent A.
  * Delays **more** payments in period 1.

* Agent A, unaffected by indivisibility, settles more of its period-1 payments earlier.

These results suggest that both agents learn to manage:

1. The **inter-period tradeoff** created by the indivisible payment (especially for B), and
2. The underlying liquidity–delay tradeoff.

---

## 8. Conclusion

This article uses reinforcement learning to estimate policy rules for banks participating in a high-value payment system. In simplified settings where analytical solutions exist, RL policies converge to optimal initial liquidity choices. Building on this, we consider more realistic environments where agents learn:

* initial liquidity policies under real LVTS payment data, and
* both initial liquidity and intraday payment policies jointly.

We show that agents learn to choose liquidity levels that minimize payment processing costs, and, in special cases, learn to respond efficiently to both liquidity–delay tradeoffs and indivisible payment shocks.

Extensive robustness checks (payment profiles, cost parameters, network architectures, learning rates, batch sizes) confirm that RL can approximate best responses in strategically rich, real-world-like games.

The initial liquidity decision is complex even when agents know the environment and opponents’ strategies. Our RL agents have **no such knowledge**, yet find near-optimal behavior through interaction. This suggests that:

* RL-trained policies could help regulators assess how banks might behave under algorithmic liquidity management, informing safety and efficiency analyses.
* Hardware and software advances may soon make such algorithms practical tools for both market participants and policymakers.

Future directions include:

* Jointly learning initial liquidity and intraday payments in more realistic, higher-dimensional environments.
* Extending to more than two agents and richer payment networks.
* Incorporating interbank liquidity markets and additional system features (e.g., queueing, priority rules).
* Exploring new RL algorithms and architectures tailored to payment system features.

---

## Appendices

### Appendix A. Intraday Payments Policy

Here we study whether agents can learn the **intraday payment policy** alone, assuming:

* Sufficient initial liquidity ( \ell_0 ) at **zero cost** (no initial liquidity tradeoff).
* Same LVTS payment profiles over 12 intraday periods as in Section 6.
* Goal: minimize cumulative delay costs.

#### A.1 Setup

* Agents: A and B, trained simultaneously over 50 episodes.
* Periods: (T = 12).
* Payments: LVTS data; in each episode, the agent sees a daily profile drawn from data but does **not** know future demands in advance.

  * ( p_t ): new demand in period ( t ).
  * ( P_t ): accumulated demand (including delayed amounts).
* Initial liquidity: ( \ell_0 ) large enough that ( \ell_0 > \sum_t P_t ).
* Initial liquidity cost: ( r_c = 0 ).
* State at period ( t ): ( s_t = (t, p_t, P_t, \ell_t) ).
* Action: fraction ( x_t \in {0, 0.05, \dots, 1} ) of accumulated demand ( P_t ) to send.
* Cost:
  [
  R = \sum_{t=1}^{T-1} P_t(1 - x_t) r_d,
  ]
  with ( r_d = 0.2 ). No end-of-day borrowing (always enough liquidity).

Given free liquidity, the unique optimum is ( x_t = 1 ) for all ( t ): never delay any payments.

#### A.2 Results

**Figure 11 (page 20). Training/testing costs for intraday payment policy**

* Both agents quickly reduce average cost over episodes.
* Agent B starts with higher cost due to larger payment demands.
* After about 20–25 episodes, costs are near zero (close to optimal).

**Figure 12 (page 20). Evolution of payment fractions ( x_t )**

* We show learning for periods ( t = 1,2,3,4 ); later periods (( t \ge 5 )) show similar patterns.
* At early episodes, agents send roughly half the payments on average (due to random parameter initialization).
* Over training, both agents converge to sending nearly all payments ( (x_t \to 1) ).
* Convergence is faster in later periods, likely because accumulated delay raises the marginal cost signal.

The RL agents thus successfully discover the optimal intraday policy: always send all payments, given ample and free initial liquidity.

---

### Appendix B. Reinforcement Learning Details

We briefly outline the RL framework and the REINFORCE algorithm used.

#### B.1 Markov Decision Process (MDP)

We model the environment as an MDP ( \langle S, A, T, R, H \rangle ):

* ( S ): state space
* ( A ): action space
* ( T(s,a)(s') ): transition probabilities
* ( R(s,a) \in [R_{\min}, R_{\max}] ): bounded cost (negative reward)
* ( H ): horizon length (number of steps in an episode)

A policy ( \pi: S \to \Delta(A) ) maps states to action distributions. The value of policy ( \pi ) from state ( s_0 ) is:

[
V^\pi(s_0) = \mathbb{E}\left[ \sum_{t=0}^{H} R(s_t, a_t) \right].
]

Value functions satisfy Bellman equations:

[
V^\pi_0(s) = 0, \quad
V^\pi_H(s) = \mathbb{E}*{a \sim \pi(s)} \left[ R(s,a) + \gamma \mathbb{E}*{s' \sim T(s,a)} V^\pi_{H-1}(s') \right],
]
with discount factor ( \gamma \in (0,1] ).

The optimal value function ( V^* ) satisfies:

[
V^**H(s) = \max*{a \in A} \left[ R(s,a) + \gamma \mathbb{E}_{s' \sim T(s,a)} V^*_{H-1}(s') \right].
]

The associated action-value (Q-function) is:

[
Q^\pi(s,a) = R(s,a) + \gamma \mathbb{E}_{s' \sim T(s,a)} V^\pi(s').
]

When dynamics ( T,R ) are known, dynamic programming can solve these equations; in RL we instead estimate from experience.

#### B.2 Policy Gradients and REINFORCE

We parametrize policies ( \pi_\theta ) by weights ( \theta ) (e.g., neural network parameters) and define performance from initial state ( s_0 ):

[
J(\theta) = V^{\pi_\theta}(s_0).
]

The **policy gradient theorem** states:

[
\nabla J(\theta) \propto \sum_{s} \mu_\theta(s) \sum_{a} Q^{\pi_\theta}(s,a) \nabla \pi_\theta(s)(a),
]
where ( \mu_\theta ) is the on-policy state distribution.

We estimate gradients via Monte Carlo rollouts. Let ( G_k ) be the total return from time ( k ) onward:

[
G_k = \sum_{t=k}^{H} R(s_t, a_t).
]

The REINFORCE update after observing trajectory ( (s_t, a_t, R_t) ) is:

[
\theta_{t+1} = \theta_t + \alpha G_t \frac{\nabla \pi_\theta(s_t)(a_t)}{\pi_\theta(s_t)(a_t)},
]
with learning rate ( \alpha ).

Policies are implemented with softmax over neural network outputs ( \hat{Q}_\theta(s,a) ):

[
\pi_\theta(s)(a) = \frac{e^{\hat{Q}*\theta(s,a)}}{\sum_b e^{\hat{Q}*\theta(s,b)}}.
]

#### B.3 Multi-Agent RL

Standard multi-agent RL models a single global state ( s \in S ), joint actions ( (a^1,\dots,a^n) \in A^1 \times \dots \times A^n ), and shared transitions ( T(s,(a^1,\dots,a^n)) ).

Our setting instead has:

* **Decentralized observations:** each agent ( i ) sees only its own state ( s^i \in S^i ).
* **Joint dynamics:** transitions and costs depend on the *joint* state and action:
  [
  T((s^1,\dots,s^n),(a^1,\dots,a^n)),\quad
  R((s^1,\dots,s^n),(a^1,\dots,a^n)).
  ]

Agents cannot observe each others’ states or policies. This yields a partially observable multi-agent MDP, where each agent must cope with non-stationarity induced by others’ learning.

---

### Appendix C. Brute-Force Benchmark for Initial Liquidity

For (T = 12), analytical solutions are intractable, but we can compute an **empirical benchmark** using brute-force search over a discretized action set.

Let:

* ( \mathcal{L} ): set of possible initial liquidity choices for each agent (corresponding to discrete ( x_0 ) grid).
* ( \mathcal{P} ): set of observed daily payment profiles (380 LVTS days).
* ( R^i(\ell^i_0, \ell^{-i}_0, P_j) ): total cost of agent ( i ) given liquidity pair ( (\ell^i_0, \ell^{-i}_0) ) and payment profile ( P_j ).

For each profile ( P_j ):

[
R^*(P_j) = \min_{(\ell^A_0,\ell^B_0) \in \mathcal{L} \times \mathcal{L}}
\left[ R^A(\ell^A_0,\ell^B_0,P_j) + R^B(\ell^B_0,\ell^A_0,P_j) \right].
]

We define:

* **Average minimum cost:**
  [
  \bar{R}^* = \frac{1}{|\mathcal{P}|} \sum_{P_j \in \mathcal{P}} R^*(P_j)
  ]
* **Min and max across profiles:**
  [
  \min_j R^*(P_j), \quad \max_j R^*(P_j).
  ]

**Figure 13 (page 24). System-wide costs vs. empirical benchmark**

* Plots show the sum ( R^A + R^B ) over training episodes for RL agents, with training and testing curves.
* A horizontal red line indicates ( \bar{R}^* ) (average planner cost).
* Dashed red lines show the min and max planner costs across profiles.

RL trajectories converge near the planner’s average cost, but because agents learn **independently** (non-cooperative), they do not necessarily achieve the cooperative minimum for each profile.

---

### Appendix D. Training Hyperparameters

**Table 2 (page 25). Environment and agent parameters**

| Parameter                 | Intraday payments problem | Initial liquidity problem |
| ------------------------- | ------------------------- | ------------------------- |
| Algorithm                 | REINFORCE                 | REINFORCE                 |
| Number of agents          | 2                         | 2                         |
| Number of episodes        | 50                        | 100                       |
| Periods per episode       | 12                        | 12                        |
| Batch size                | 10                        | 10                        |
| State dimension           | 4                         | 12                        |
| Action space size         | 21                        | 21                        |
| Initial liquidity cost    | 0                         | 0.1                       |
| Per-period delay cost     | 0.2                       | 0.2                       |
| End-of-day borrowing cost | ∞                         | 0.4                       |
| Learning rate             | 0.1                       | 0.1                       |
| Activation function       | tanh                      | tanh                      |
| Optimizer                 | –                         | Adam                      |
| Network type              | Feed-forward              | Feed-forward              |
| Hidden layers             | –                         | 1                         |
| Hidden units              | –                         | 21                        |
| Initial liquidity         | Unrestricted, free        | Learned parameter         |
| Intraday payments         | Learned                   | Fixed: send max possible  |

---

### Appendix E. Robustness Exercises

We test sensitivity to neural net size, learning rate, batch size, cost parameters, and payment profiles.

#### E.1 Network Size

Increasing network size generally speeds learning.

* **Intraday payments** (Figure 14, page 26):
  Even a linear policy network is sufficient to learn the optimal “send everything” policy. Additional hidden layers do not cause overfitting and may slightly accelerate convergence.

* **Initial liquidity** (Figure 15, page 26):
  A purely linear network has more difficulty (slower convergence and higher variance). Introducing one hidden layer dramatically improves convergence; further increases yield diminishing returns.

#### E.2 Learning Rate

* **Intraday payments** (Figure 16, page 27):
  Larger learning rates (( \alpha = 0.1, 1 )) speed convergence and narrow confidence bands, given the simplicity of the optimal policy.

* **Initial liquidity** (Figure 17, page 27):
  Higher learning rates slow convergence and increase variance. With ( \alpha = 1 ), policies quickly lock in, but may converge to suboptimal liquidity choices (insufficient exploration).

#### E.3 Batch Size

* **Intraday payments** (Figure 18, page 27):
  Larger batch sizes reduce variance and speed convergence. Small batch sizes (1) sometimes fail to converge to the optimal policy.

* **Initial liquidity** (Figure 19, page 28):
  Similar pattern: higher batch sizes yield more stable learning with lower variance.

#### E.4 Cost Ordering (r_c) vs. (r_b)

We reverse the relationship between initial liquidity and borrowing costs:

* Original: ( r_c = 0.1 < r_b = 0.4 ).
* Alternative: ( r_c = 0.4 > r_b = 0.1 ).

**Figure 20 (page 28). Effect of cost ordering**

* When borrowing is cheaper, agents allocate less initial liquidity and rely more on borrowing.
* When borrowing is expensive, they allocate more initial liquidity.
* Since delay remains costly, agents still allocate some liquidity even when borrowing is cheap, given that intraday payments must be sent as much as possible.

#### E.5 Alternative Payment Profiles

We test two additional bank pairs:

* Pair C and D: flows diverge later in the day.
* Pair E and F: flows are more homogeneous and similar.

**Figure 21 (page 29). Payment profiles for C–D and E–F**

* Shows hourly and cumulative payments, with averages and 99% confidence intervals.

**Figure 22 (page 29). Learning with alternative profiles**

* For C–D, total costs of D converge higher than those of C (D has larger demand).
* For E–F, costs converge to similar magnitudes (similar payment profiles).

We also vary delay cost ( r_d ) (Figures 23–24):

* For E–F (similar profiles), changing ( r_d ) has modest impact on costs.
* For C–D, the effect is substantial, particularly for the higher-demand bank. Sensitivity is large when ( r_d < r_c ), echoing earlier findings.

---

## References

*(Formatted in simple markdown; numbering as in the original)*

1. Morten L. Bech and Rod Garratt. 2003. The intraday liquidity management game. *Journal of Economic Theory* 109(2), 198–219.
2. Richard S. Sutton and Andrew G. Barto. 2018. *Reinforcement Learning: An Introduction*. MIT Press.
3. Emilio Calvano, Giacomo Calzolari, Vincenzo Denicolò, and Sergio Pastorello. 2020. Artificial intelligence, algorithmic pricing, and collusion. *American Economic Review* 110(10), 3267–3297.
4. Francisco Rivadeneyra and Nellie Zhang. 2020. *Liquidity Usage and Payment Delay Estimates of the New Canadian High Value Payments System*. Bank of Canada Discussion Paper 2020–9.
5. Ajit Desai, Zhentong Lu, Hiru Rodrigo, Jacob Sharples, Phoebe Tian, and Nellie Zhang. 2023. From LVTS to Lynx: Quantitative assessment of payment system transition in Canada. *Journal of Payments Strategy & Systems* 17(3), 291–314.
6. Marco Galbiati and Kimmo Soramäki. 2011. An agent-based model of payment systems. *Journal of Economic Dynamics and Control* 35(6), 859–875.
7. Luca Arciero, Claudia Biancotti, Leandro d’Aurizio, and Claudio Impenna. 2008. *Exploring Agent-based Methods for the Analysis of Payment Systems: A Crisis Model for StarLogo TNG*. Banca d’Italia Working Paper 686.
8. Mitsuru Igami. 2024. Artificial intelligence as structural estimation: Deep Blue, Bonanza, and AlphaGo. *The Econometrics Journal* 23(3), S1–S24.
9. Erich Kutschinski, Thomas Uthmann, and Daniel Polani. 2003. Learning competitive pricing strategies by multi-agent reinforcement learning. *Journal of Economic Dynamics and Control* 27(11–12), 2207–2218.
10. Alvin E. Roth and Ido Erev. 1995. Learning in extensive-form games: Experimental data and simple dynamic models in the intermediate term. *Games and Economic Behavior* 8(1), 164–212.
11. Drew Fudenberg and David K. Levine. 2016. Whither game theory? Towards a theory of learning in games. *Journal of Economic Perspectives* 30(4), 151–170.
12. Martin Bichler, Maximilian Fichtl, Stefan Heidekrüger, Nils Kohring, and Paul Sutterer. 2021. Learning equilibria in symmetric auction games using artificial neural networks. *Nature Machine Intelligence* 3(8), 687–695.
13. Carlos Martin and Tuomas Sandholm. 2022. Finding mixed-strategy equilibria of continuous-action games without gradients using randomized policy networks. arXiv:2211.15936.
14. Naoki Funai. 2019. Convergence results on stochastic adaptive learning. *Economic Theory* 68(4), 907–934.
15. Stephan Zheng, Alexander Trott, Sunil Srinivasa, David C. Parkes, and Richard Socher. 2022. The AI Economist: Taxation policy design via two-level deep multiagent reinforcement learning. *Science Advances* 8(18), eabk2607.
16. Christopher McMahon et al. 2022. Improving the efficiency of payments systems using quantum computing. arXiv:2209.15392.
17. Narayan Bulusu and Pierre Guérin. 2019. What drives interbank loans? Evidence from Canada. *Journal of Banking & Finance* 106, 427–444.
18. Ronald J. Williams. 1992. Simple statistical gradient-following algorithms for connectionist reinforcement learning. *Machine Learning* 8(3–4), 229–256.
19. Martín Abadi et al. 2016. TensorFlow: A system for large-scale machine learning. In *Proceedings of the 12th USENIX Symposium on Operating Systems Design and Implementation (OSDI’16)*, 265–283.
20. Michael Bowling. 2003. *Multiagent Learning in the Presence of Agents with Limitations*. PhD thesis, Carnegie Mellon University.
21. Jakob Foerster, Ioannis Alexandros Assael, Nando de Freitas, and Shimon Whiteson. 2016. Learning to communicate with deep multi-agent reinforcement learning. In *Advances in Neural Information Processing Systems 29*, 2137–2145.
22. Rodney J. Garratt. 2022. An application of Shapley value cost allocation to liquidity savings mechanisms. *Journal of Money, Credit and Banking* 54(6), 1875–1888.
