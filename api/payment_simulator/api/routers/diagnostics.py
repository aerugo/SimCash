"""Router for diagnostic endpoints.

Handles costs, metrics, events, agent details, and state inspection.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from payment_simulator.api.dependencies import (
    get_db_manager,
    get_simulation_service,
    get_transaction_service,
)
from payment_simulator.api.models import (
    AgentCostBreakdown,
    AgentListResponse,
    AgentQueuesResponse,
    AgentStateSnapshot,
    AgentSummary,
    AgentTimelineResponse,
    CollateralEvent,
    CostResponse,
    CostTimelineResponse,
    DailyAgentMetric,
    EventListResponse,
    EventRecord,
    MetricsResponse,
    QueueContents,
    QueueTransaction,
    RelatedTransaction,
    SimulationMetadataResponse,
    SimulationSummary,
    SystemMetrics,
    SystemStateSnapshot,
    TickCostDataPoint,
    TickStateResponse,
    TransactionDetail,
    TransactionEvent,
    TransactionLifecycleResponse,
)
from payment_simulator.api.services import (
    SimulationNotFoundError,
    SimulationService,
    TransactionService,
)

router = APIRouter(tags=["diagnostics"])


# ============================================================================
# Cost & Metrics Endpoints
# ============================================================================


@router.get("/simulations/{sim_id}/costs", response_model=CostResponse)
def get_simulation_costs(
    sim_id: str,
    service: SimulationService = Depends(get_simulation_service),
    db_manager: Any = Depends(get_db_manager),
) -> CostResponse:
    """Get accumulated costs for all agents in a simulation.

    Returns per-agent cost breakdown and total system cost.
    All costs are in cents (i64).
    """
    try:
        # Try to get from active simulation first
        orchestrator = service.get_simulation(sim_id)

        # Get costs for all agents
        agent_costs = {}
        total_system_cost = 0

        # Get agent list from config
        config = service.get_config(sim_id).get("original", {})
        agent_configs = config.get("agents", [])

        for agent_config in agent_configs:
            agent_id = agent_config["id"]

            # Get costs from FFI
            costs_dict = orchestrator.get_agent_accumulated_costs(agent_id)

            # Convert to Pydantic model
            breakdown = AgentCostBreakdown(**costs_dict)
            agent_costs[agent_id] = breakdown
            total_system_cost += breakdown.total_cost

        # Get current tick and day
        current_tick = orchestrator.current_tick()
        current_day = orchestrator.current_day()

        return CostResponse(
            simulation_id=sim_id,
            tick=current_tick,
            day=current_day,
            agents=agent_costs,
            total_system_cost=total_system_cost,
        )

    except SimulationNotFoundError:
        # Not an active simulation - try database
        if not db_manager:
            raise HTTPException(
                status_code=404,
                detail=f"Simulation not found: {sim_id}",
            ) from None

        from payment_simulator.persistence.queries import (
            get_cost_breakdown_by_agent,
            get_simulation_summary,
        )

        conn = db_manager.get_connection()

        # Check if simulation exists in database
        summary = get_simulation_summary(conn, sim_id)
        if not summary:
            raise HTTPException(
                status_code=404,
                detail=f"Simulation not found: {sim_id}",
            ) from None

        # Get cost breakdown from database
        df = get_cost_breakdown_by_agent(conn, sim_id)

        if df.is_empty():
            raise HTTPException(
                status_code=404,
                detail=f"No cost data available for simulation: {sim_id}",
            ) from None

        # Convert Polars DataFrame to dict
        agent_costs = {}
        total_system_cost = 0

        for row in df.iter_rows(named=True):
            breakdown = AgentCostBreakdown(
                liquidity_cost=row["liquidity_cost"],
                collateral_cost=row["collateral_cost"],
                delay_cost=row["delay_cost"],
                split_friction_cost=row["split_friction_cost"],
                deadline_penalty=row["deadline_penalty_cost"],
                total_cost=row["total_cost"],
            )
            agent_costs[row["agent_id"]] = breakdown
            total_system_cost += breakdown.total_cost

        # Get final tick/day from summary
        final_tick = summary["ticks_per_day"] * summary["num_days"]
        final_day = summary["num_days"]

        return CostResponse(
            simulation_id=sim_id,
            tick=final_tick,
            day=final_day,
            agents=agent_costs,
            total_system_cost=total_system_cost,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}") from e


@router.get(
    "/simulations/{sim_id}/costs/timeline",
    response_model=CostTimelineResponse,
)
def get_cost_timeline(
    sim_id: str,
    service: SimulationService = Depends(get_simulation_service),
    db_manager: Any = Depends(get_db_manager),
) -> CostTimelineResponse:
    """Get cost timeline data for chart visualization.

    Returns accumulated costs per agent per tick.
    Only supports database-persisted simulations.
    """
    try:
        if not db_manager:
            raise HTTPException(
                status_code=404,
                detail=f"Simulation not found: {sim_id}. Cost timeline only available for persisted simulations.",
            )

        from payment_simulator.persistence.queries import get_simulation_summary

        conn = db_manager.get_connection()

        # Check if simulation exists in database
        summary = get_simulation_summary(conn, sim_id)
        if not summary:
            raise HTTPException(
                status_code=404, detail=f"Simulation not found: {sim_id}"
            )

        # Get ticks_per_day from simulation config
        ticks_per_day = summary["ticks_per_day"]

        # Get all agents from the simulation
        agents_query = """
            SELECT DISTINCT agent_id
            FROM daily_agent_metrics
            WHERE simulation_id = ?
            ORDER BY agent_id
        """
        agent_results = conn.execute(agents_query, [sim_id]).fetchall()
        agent_ids = sorted([row[0] for row in agent_results])

        if not agent_ids:
            raise HTTPException(
                status_code=404,
                detail=f"No cost timeline data available for simulation: {sim_id}",
            )

        # Query actual tick-level cost events
        cost_accrual_query = """
            SELECT
                tick,
                agent_id,
                CAST(json_extract(details, '$.costs.total') AS INTEGER) as tick_cost
            FROM simulation_events
            WHERE simulation_id = ?
              AND event_type = 'CostAccrual'
            ORDER BY tick
        """

        deadline_penalty_query = """
            SELECT
                tick,
                json_extract(details, '$.sender_id') as agent_id,
                CAST(json_extract(details, '$.deadline_penalty_cost') AS INTEGER) as penalty_cost
            FROM simulation_events
            WHERE simulation_id = ?
              AND event_type = 'TransactionWentOverdue'
            ORDER BY tick
        """

        # Aggregate costs by tick and agent
        tick_agent_costs: defaultdict[int, defaultdict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )

        # Add continuous costs from CostAccrual events
        for row in conn.execute(cost_accrual_query, [sim_id]).fetchall():
            tick, agent_id, cost = row
            tick_agent_costs[tick][agent_id] += cost

        # Add deadline penalties from TransactionWentOverdue events
        for row in conn.execute(deadline_penalty_query, [sim_id]).fetchall():
            tick, agent_id, penalty = row
            tick_agent_costs[tick][agent_id] += penalty

        # Add EOD penalties from daily_agent_metrics
        eod_penalty_query = """
            SELECT
                day,
                agent_id,
                deadline_penalty_cost
            FROM daily_agent_metrics
            WHERE simulation_id = ?
            ORDER BY day, agent_id
        """

        for row in conn.execute(eod_penalty_query, [sim_id]).fetchall():
            day, agent_id, deadline_pen = row

            # Calculate costs already captured from events for this agent this day
            event_costs_this_day = 0
            for tick in range(day * ticks_per_day, (day + 1) * ticks_per_day):
                event_costs_this_day += tick_agent_costs[tick].get(agent_id, 0)

            # EOD penalty is the difference
            eod_penalty = deadline_pen - event_costs_this_day

            if eod_penalty > 0:
                # Apply EOD penalty at the LAST tick of the day
                eod_tick = (day + 1) * ticks_per_day - 1
                tick_agent_costs[eod_tick][agent_id] += eod_penalty

        # Get max tick from simulation
        max_tick = summary.get("ticks_executed", ticks_per_day * 3) - 1

        # Build accumulated costs for all ticks
        tick_costs = []
        accumulated = dict.fromkeys(agent_ids, 0)

        for tick in range(max_tick + 1):
            # Add costs that occurred at this tick
            for agent_id in agent_ids:
                accumulated[agent_id] += tick_agent_costs[tick].get(agent_id, 0)

            # Store accumulated costs (in cents)
            tick_costs.append(
                TickCostDataPoint(
                    tick=tick,
                    agent_costs={
                        agent_id: int(accumulated[agent_id]) for agent_id in agent_ids
                    },
                )
            )

        return CostTimelineResponse(
            simulation_id=sim_id,
            agent_ids=agent_ids,
            tick_costs=tick_costs,
            ticks_per_day=ticks_per_day,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}") from e


@router.get("/simulations/{sim_id}/metrics", response_model=MetricsResponse)
def get_simulation_metrics(
    sim_id: str,
    service: SimulationService = Depends(get_simulation_service),
) -> MetricsResponse:
    """Get comprehensive system-wide metrics for a simulation.

    Returns settlement rates, delays, queue statistics, and liquidity usage.
    """
    try:
        orchestrator = service.get_simulation(sim_id)

        # Get metrics from FFI
        metrics_dict = orchestrator.get_system_metrics()

        # Convert to Pydantic model
        metrics = SystemMetrics(**metrics_dict)

        # Get current tick and day
        current_tick = orchestrator.current_tick()
        current_day = orchestrator.current_day()

        return MetricsResponse(
            simulation_id=sim_id, tick=current_tick, day=current_day, metrics=metrics
        )

    except SimulationNotFoundError:
        raise HTTPException(
            status_code=404, detail=f"Simulation not found: {sim_id}"
        ) from None
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}") from e


# ============================================================================
# Simulation Metadata & Agents
# ============================================================================


@router.get("/simulations/{sim_id}", response_model=SimulationMetadataResponse)
def get_simulation_metadata(
    sim_id: str,
    service: SimulationService = Depends(get_simulation_service),
    tx_service: TransactionService = Depends(get_transaction_service),
    db_manager: Any = Depends(get_db_manager),
) -> SimulationMetadataResponse:
    """Get complete simulation metadata including config and summary statistics."""
    try:
        # Check if simulation exists in manager
        if service.has_simulation(sim_id):
            # Active simulation - get from service
            config = service.get_config(sim_id)["original"]
            orch = service.get_simulation(sim_id)

            # Normalize config structure
            if "simulation" in config:
                normalized_config = {
                    "ticks_per_day": config["simulation"].get("ticks_per_day"),
                    "num_days": config["simulation"].get("num_days"),
                    "rng_seed": config["simulation"].get("rng_seed"),
                    "agents": config.get("agents", []),
                }
                if "lsm" in config:
                    normalized_config["lsm_config"] = config["lsm"]
            else:
                normalized_config = config

            # Calculate summary from current state
            transactions = tx_service.list_transactions(sim_id)
            settled = sum(1 for tx in transactions if tx["status"] == "settled")
            total_tx = len(transactions)
            settlement_rate = settled / total_tx if total_tx > 0 else 0.0

            return SimulationMetadataResponse(
                simulation_id=sim_id,
                created_at=datetime.now().isoformat(),
                config=normalized_config,
                summary=SimulationSummary(
                    total_ticks=orch.current_tick(),
                    total_transactions=total_tx,
                    settlement_rate=settlement_rate,
                    total_cost_cents=0,
                    duration_seconds=None,
                    ticks_per_second=None,
                ),
            )

        # Check database if available
        if not db_manager:
            raise HTTPException(
                status_code=404, detail=f"Simulation not found: {sim_id}"
            )

        conn = db_manager.get_connection()

        # Query simulation metadata
        sim_query = """
            SELECT
                simulation_id,
                config_file,
                config_hash,
                rng_seed,
                ticks_per_day,
                num_days,
                num_agents,
                config_json,
                status,
                started_at,
                completed_at,
                total_arrivals,
                total_settlements,
                total_cost_cents,
                duration_seconds,
                ticks_per_second
            FROM simulations
            WHERE simulation_id = ?
        """
        sim_result = conn.execute(sim_query, [sim_id]).fetchone()

        if not sim_result:
            raise HTTPException(
                status_code=404, detail=f"Simulation not found: {sim_id}"
            )

        # Unpack result
        (
            sim_id_result,
            config_file,
            config_hash,
            rng_seed,
            ticks_per_day,
            num_days,
            num_agents,
            config_json_str,
            status,
            started_at,
            completed_at,
            total_arrivals,
            total_settlements,
            total_cost_cents,
            duration_seconds,
            ticks_per_second,
        ) = sim_result

        # Parse config_json if available
        if config_json_str:
            config_dict = json.loads(config_json_str)
        else:
            config_dict = {
                "config_file": config_file,
                "config_hash": config_hash,
                "rng_seed": rng_seed,
                "ticks_per_day": ticks_per_day,
                "num_days": num_days,
                "num_agents": num_agents,
                "agents": [],
            }

        # Recalculate settlement rate correctly
        recalc_query = """
            WITH parent_transactions AS (
                SELECT tx_id, status, amount, amount_settled, parent_tx_id
                FROM transactions
                WHERE simulation_id = ? AND parent_tx_id IS NULL
            ),
            child_status AS (
                SELECT
                    parent_tx_id,
                    COUNT(*) as child_count,
                    SUM(CASE WHEN status = 'settled' AND amount_settled = amount THEN 1 ELSE 0 END) as settled_child_count
                FROM transactions
                WHERE simulation_id = ? AND parent_tx_id IS NOT NULL
                GROUP BY parent_tx_id
            )
            SELECT
                COUNT(DISTINCT pt.tx_id) as total_arrivals,
                SUM(CASE
                    WHEN cs.child_count IS NULL THEN
                        CASE WHEN pt.status = 'settled' AND pt.amount_settled = pt.amount THEN 1 ELSE 0 END
                    ELSE
                        CASE WHEN cs.settled_child_count = cs.child_count THEN 1 ELSE 0 END
                END) as effective_settlements
            FROM parent_transactions pt
            LEFT JOIN child_status cs ON pt.tx_id = cs.parent_tx_id
        """

        recalc_result = conn.execute(recalc_query, [sim_id, sim_id]).fetchone()

        if recalc_result and recalc_result[0] > 0:
            total_arrivals = recalc_result[0]
            total_settlements = recalc_result[1] if recalc_result[1] else 0

        settlement_rate = (
            total_settlements / total_arrivals
            if total_arrivals and total_arrivals > 0
            else 0.0
        )

        total_ticks = ticks_per_day * num_days if ticks_per_day and num_days else 0

        return SimulationMetadataResponse(
            simulation_id=sim_id_result,
            created_at=(
                started_at.isoformat() if started_at else datetime.now().isoformat()
            ),
            config=config_dict,
            summary=SimulationSummary(
                total_ticks=total_ticks,
                total_transactions=total_arrivals or 0,
                settlement_rate=settlement_rate,
                total_cost_cents=total_cost_cents or 0,
                duration_seconds=duration_seconds,
                ticks_per_second=ticks_per_second,
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}") from e


@router.get("/simulations/{sim_id}/agents", response_model=AgentListResponse)
def get_agent_list(
    sim_id: str,
    service: SimulationService = Depends(get_simulation_service),
    db_manager: Any = Depends(get_db_manager),
) -> AgentListResponse:
    """Get list of all agents with summary statistics."""
    try:
        # Check if simulation exists in memory
        if service.has_simulation(sim_id):
            orch = service.get_simulation(sim_id)
            config = service.get_config(sim_id)["original"]
            agent_list = config.get("agents") or config.get("agent_configs", [])

            agents = []
            for agent_id in orch.get_agent_ids():
                agent_config = next(
                    (a for a in agent_list if a["id"] == agent_id), None
                )
                unsecured_cap = (
                    agent_config.get("unsecured_cap", 0) if agent_config else 0
                )

                agents.append(
                    AgentSummary(
                        agent_id=agent_id,
                        total_sent=0,
                        total_received=0,
                        total_settled=0,
                        total_dropped=0,
                        total_cost_cents=0,
                        avg_balance_cents=orch.get_agent_balance(agent_id) or 0,
                        peak_overdraft_cents=0,
                        unsecured_cap_cents=unsecured_cap,
                    )
                )

            return AgentListResponse(agents=agents)

        # Not in memory, try database
        if not db_manager:
            raise HTTPException(
                status_code=404, detail=f"Simulation not found: {sim_id}"
            )

        conn = db_manager.get_connection()

        query = """
            SELECT
                dam.agent_id,
                COALESCE(SUM(dam.num_sent), 0) as total_sent,
                COALESCE(SUM(dam.num_received), 0) as total_received,
                COALESCE(SUM(dam.num_settled), 0) as total_settled,
                COALESCE(SUM(dam.num_dropped), 0) as total_dropped,
                COALESCE(SUM(dam.total_cost), 0) as total_cost_cents,
                COALESCE(AVG(dam.closing_balance), 0) as avg_balance_cents,
                COALESCE(MIN(dam.min_balance), 0) as peak_overdraft_cents,
                0 as unsecured_cap_cents
            FROM daily_agent_metrics dam
            WHERE dam.simulation_id = ?
            GROUP BY dam.agent_id
            ORDER BY dam.agent_id
        """

        results = conn.execute(query, [sim_id]).fetchall()

        if not results:
            raise HTTPException(
                status_code=404, detail=f"Simulation not found: {sim_id}"
            )

        agents = [
            AgentSummary(
                agent_id=row[0],
                total_sent=int(row[1]),
                total_received=int(row[2]),
                total_settled=int(row[3]),
                total_dropped=int(row[4]),
                total_cost_cents=int(row[5]),
                avg_balance_cents=int(row[6]),
                peak_overdraft_cents=int(row[7]),
                unsecured_cap_cents=int(row[8]),
            )
            for row in results
        ]

        return AgentListResponse(agents=agents)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}") from e


@router.get(
    "/simulations/{sim_id}/agents/{agent_id}/timeline",
    response_model=AgentTimelineResponse,
)
def get_agent_timeline(
    sim_id: str,
    agent_id: str,
    service: SimulationService = Depends(get_simulation_service),
    db_manager: Any = Depends(get_db_manager),
) -> AgentTimelineResponse:
    """Get complete timeline for a specific agent."""
    try:
        # Check if simulation exists in memory
        if service.has_simulation(sim_id):
            orch = service.get_simulation(sim_id)

            # Verify agent exists
            if agent_id not in orch.get_agent_ids():
                raise HTTPException(
                    status_code=404, detail=f"Agent {agent_id} not found"
                )

            # For in-memory simulations, provide current state as single metric
            current_balance = orch.get_agent_balance(agent_id) or 0
            current_day = orch.current_day()

            daily_metrics = [
                DailyAgentMetric(
                    day=current_day,
                    opening_balance=current_balance,
                    closing_balance=current_balance,
                    min_balance=current_balance,
                    max_balance=current_balance,
                    transactions_sent=0,
                    transactions_received=0,
                    total_cost_cents=0,
                )
            ]

            return AgentTimelineResponse(
                agent_id=agent_id, daily_metrics=daily_metrics, collateral_events=[]
            )

        # Not in memory, try database
        if not db_manager:
            raise HTTPException(
                status_code=404, detail=f"Simulation not found: {sim_id}"
            )

        conn = db_manager.get_connection()

        # Get daily metrics
        metrics_query = """
            SELECT
                day,
                opening_balance,
                closing_balance,
                min_balance,
                max_balance,
                num_sent,
                num_received,
                total_cost
            FROM daily_agent_metrics
            WHERE simulation_id = ? AND agent_id = ?
            ORDER BY day
        """

        metrics_results = conn.execute(metrics_query, [sim_id, agent_id]).fetchall()

        if not metrics_results:
            raise HTTPException(
                status_code=404,
                detail=f"Agent {agent_id} not found in simulation {sim_id}",
            )

        daily_metrics = [
            DailyAgentMetric(
                day=int(row[0]),
                opening_balance=int(row[1]),
                closing_balance=int(row[2]),
                min_balance=int(row[3]),
                max_balance=int(row[4]),
                transactions_sent=int(row[5]),
                transactions_received=int(row[6]),
                total_cost_cents=int(row[7]),
            )
            for row in metrics_results
        ]

        # Get collateral events
        collateral_query = """
            SELECT
                tick,
                day,
                action,
                amount,
                reason,
                balance_before
            FROM collateral_events
            WHERE simulation_id = ? AND agent_id = ?
            ORDER BY tick
        """

        collateral_results = conn.execute(
            collateral_query, [sim_id, agent_id]
        ).fetchall()

        collateral_events = [
            CollateralEvent(
                tick=int(row[0]),
                day=int(row[1]),
                action=str(row[2]),
                amount=int(row[3]),
                reason=str(row[4]),
                balance_before=int(row[5]),
            )
            for row in collateral_results
        ]

        return AgentTimelineResponse(
            agent_id=agent_id,
            daily_metrics=daily_metrics,
            collateral_events=collateral_events,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}") from e


@router.get(
    "/simulations/{sim_id}/agents/{agent_id}/queues",
    response_model=AgentQueuesResponse,
)
def get_agent_queues(
    sim_id: str,
    agent_id: str,
    service: SimulationService = Depends(get_simulation_service),
) -> AgentQueuesResponse:
    """Get queue contents for a specific agent."""
    try:
        orch = service.get_simulation(sim_id)

        # Verify agent exists
        if agent_id not in orch.get_agent_ids():
            raise HTTPException(
                status_code=404,
                detail=f"Agent {agent_id} not found in simulation {sim_id}",
            )

        # Get current tick and day
        current_tick = orch.current_tick()
        current_day = orch.current_day()

        # Get Queue 1 contents
        queue1_tx_ids = orch.get_agent_queue1_contents(agent_id)
        queue1_transactions = []
        queue1_total_value = 0

        for tx_id in queue1_tx_ids:
            tx = orch.get_transaction_details(tx_id)
            if tx:
                queue1_transactions.append(
                    QueueTransaction(
                        tx_id=tx["id"],
                        receiver_id=tx["receiver_id"],
                        amount=tx["amount"],
                        priority=tx["priority"],
                        deadline_tick=tx["deadline_tick"],
                    )
                )
                queue1_total_value += tx["amount"]

        # Get Queue 2 contents filtered to this agent
        rtgs_tx_ids = orch.get_rtgs_queue_contents()
        queue2_transactions = []
        queue2_total_value = 0

        for tx_id in rtgs_tx_ids:
            tx = orch.get_transaction_details(tx_id)
            if tx and tx["sender_id"] == agent_id:
                queue2_transactions.append(
                    QueueTransaction(
                        tx_id=tx["id"],
                        receiver_id=tx["receiver_id"],
                        amount=tx["amount"],
                        priority=tx["priority"],
                        deadline_tick=tx["deadline_tick"],
                    )
                )
                queue2_total_value += tx["amount"]

        return AgentQueuesResponse(
            agent_id=agent_id,
            simulation_id=sim_id,
            tick=current_tick,
            day=current_day,
            queue1=QueueContents(
                size=len(queue1_transactions),
                transactions=queue1_transactions,
                total_value=queue1_total_value,
            ),
            queue2_filtered=QueueContents(
                size=len(queue2_transactions),
                transactions=queue2_transactions,
                total_value=queue2_total_value,
            ),
        )

    except SimulationNotFoundError:
        raise HTTPException(
            status_code=404, detail=f"Simulation not found: {sim_id}"
        ) from None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}") from e


# ============================================================================
# Events
# ============================================================================


@router.get("/simulations/{sim_id}/events", response_model=EventListResponse)
def get_events(
    sim_id: str,
    tick: int | None = Query(None, description="Exact tick filter"),
    tick_min: int | None = Query(None, description="Minimum tick (inclusive)"),
    tick_max: int | None = Query(None, description="Maximum tick (inclusive)"),
    day: int | None = Query(None, description="Filter by specific day"),
    agent_id: str | None = Query(None, description="Filter by agent ID"),
    tx_id: str | None = Query(None, description="Filter by transaction ID"),
    event_type: str | None = Query(
        None, description="Filter by event type (comma-separated for multiple)"
    ),
    limit: int = Query(100, ge=1, le=1000, description="Number of events per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    sort: str = Query(
        "tick_asc", pattern="^(tick_asc|tick_desc)$", description="Sort order"
    ),
    service: SimulationService = Depends(get_simulation_service),
    db_manager: Any = Depends(get_db_manager),
) -> EventListResponse:
    """Get paginated list of events with comprehensive filtering."""
    try:
        # Validate tick_min/tick_max consistency
        if tick_min is not None and tick_max is not None and tick_min > tick_max:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid parameters: tick_min ({tick_min}) cannot be greater than tick_max ({tick_max})",
            )

        # Check if simulation exists (in-memory or database)
        if service.has_simulation(sim_id):
            # In-memory simulation - events are not persisted
            return EventListResponse(
                events=[],
                total=0,
                limit=limit,
                offset=offset,
                filters={
                    "tick": tick,
                    "tick_min": tick_min,
                    "tick_max": tick_max,
                    "day": day,
                    "agent_id": agent_id,
                    "tx_id": tx_id,
                    "event_type": event_type,
                    "sort": sort,
                },
            )

        # Check database connection
        if not db_manager:
            raise HTTPException(
                status_code=404, detail=f"Simulation not found: {sim_id}"
            )

        conn = db_manager.get_connection()

        # Check if simulation exists in database
        exists_result = conn.execute(
            "SELECT COUNT(*) FROM simulation_events WHERE simulation_id = ?", [sim_id]
        ).fetchone()
        exists_check = exists_result[0] if exists_result else 0

        if exists_check == 0:
            # Verify simulation exists in simulations table
            sim_result = conn.execute(
                "SELECT COUNT(*) FROM simulations WHERE simulation_id = ?", [sim_id]
            ).fetchone()
            sim_check = sim_result[0] if sim_result else 0

            if sim_check == 0:
                raise HTTPException(
                    status_code=404, detail=f"Simulation not found: {sim_id}"
                )

            # Simulation exists but has no events yet
            return EventListResponse(
                events=[],
                total=0,
                limit=limit,
                offset=offset,
                filters={
                    "tick": tick,
                    "tick_min": tick_min,
                    "tick_max": tick_max,
                    "day": day,
                    "agent_id": agent_id,
                    "tx_id": tx_id,
                    "event_type": event_type,
                    "sort": sort,
                },
            )

        # Use the query function
        from payment_simulator.persistence.event_queries import get_simulation_events

        result = get_simulation_events(
            conn=conn,
            simulation_id=sim_id,
            tick=tick,
            tick_min=tick_min,
            tick_max=tick_max,
            day=day,
            agent_id=agent_id,
            tx_id=tx_id,
            event_type=event_type,
            limit=limit,
            offset=offset,
            sort=sort,
        )

        # Convert to response format
        events = [EventRecord(**event) for event in result["events"]]

        return EventListResponse(
            events=events,
            total=result["total"],
            limit=result["limit"],
            offset=result["offset"],
            filters=result["filters"],
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}") from e


# ============================================================================
# Transaction Lifecycle & Tick State
# ============================================================================


@router.get(
    "/simulations/{sim_id}/transactions/{tx_id}/lifecycle",
    response_model=TransactionLifecycleResponse,
)
def get_transaction_lifecycle(
    sim_id: str,
    tx_id: str,
    tx_service: TransactionService = Depends(get_transaction_service),
    db_manager: Any = Depends(get_db_manager),
) -> TransactionLifecycleResponse:
    """Get complete lifecycle of a transaction."""
    try:
        if not db_manager:
            # Fall back to service if no database
            try:
                tx = tx_service.get_transaction(sim_id, tx_id)
            except Exception:
                raise HTTPException(
                    status_code=404, detail=f"Transaction {tx_id} not found"
                ) from None

            return TransactionLifecycleResponse(
                transaction=TransactionDetail(
                    tx_id=tx_id,
                    sender_id=tx["sender"],
                    receiver_id=tx["receiver"],
                    amount=tx["amount"],
                    priority=tx["priority"],
                    arrival_tick=tx.get("submitted_at_tick", 0),
                    deadline_tick=tx["deadline_tick"],
                    settlement_tick=None,
                    status=tx["status"],
                    delay_cost=0,
                    amount_settled=0,
                ),
                events=[
                    TransactionEvent(
                        tick=tx.get("submitted_at_tick", 0),
                        event_type="Arrival",
                        details={},
                    )
                ],
                related_transactions=[],
            )

        conn = db_manager.get_connection()

        # Get transaction details
        tx_query = """
            SELECT
                tx_id,
                sender_id,
                receiver_id,
                amount,
                priority,
                arrival_tick,
                deadline_tick,
                settlement_tick,
                status,
                delay_cost,
                COALESCE(amount_settled, amount) as amount_settled
            FROM transactions
            WHERE simulation_id = ? AND tx_id = ?
        """

        tx_result = conn.execute(tx_query, [sim_id, tx_id]).fetchone()

        if not tx_result:
            raise HTTPException(
                status_code=404, detail=f"Transaction {tx_id} not found"
            )

        transaction = TransactionDetail(
            tx_id=str(tx_result[0]),
            sender_id=str(tx_result[1]),
            receiver_id=str(tx_result[2]),
            amount=int(tx_result[3]),
            priority=int(tx_result[4]),
            arrival_tick=int(tx_result[5]),
            deadline_tick=int(tx_result[6]),
            settlement_tick=int(tx_result[7]) if tx_result[7] is not None else None,
            status=str(tx_result[8]),
            delay_cost=int(tx_result[9]) if tx_result[9] else 0,
            amount_settled=int(tx_result[10]) if tx_result[10] else 0,
        )

        # Build events from transaction lifecycle
        events = [
            TransactionEvent(
                tick=transaction.arrival_tick, event_type="Arrival", details={}
            )
        ]

        if transaction.settlement_tick is not None:
            events.append(
                TransactionEvent(
                    tick=transaction.settlement_tick,
                    event_type="Settlement",
                    details={"method": "rtgs"},
                )
            )

        # Get related transactions (splits)
        related_query = """
            SELECT tx_id, parent_tx_id, split_index
            FROM transactions
            WHERE simulation_id = ? AND (parent_tx_id = ? OR tx_id IN (
                SELECT parent_tx_id FROM transactions WHERE simulation_id = ? AND tx_id = ?
            ))
            AND tx_id != ?
        """

        related_results = conn.execute(
            related_query, [sim_id, tx_id, sim_id, tx_id, tx_id]
        ).fetchall()

        related_transactions = [
            RelatedTransaction(
                tx_id=str(row[0]),
                relationship="split_from" if row[1] == tx_id else "split_to",
                split_index=int(row[2]) if row[2] is not None else None,
            )
            for row in related_results
        ]

        return TransactionLifecycleResponse(
            transaction=transaction,
            events=events,
            related_transactions=related_transactions,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}") from e


@router.get(
    "/simulations/{sim_id}/ticks/{tick}/state",
    response_model=TickStateResponse,
)
def get_tick_state(
    sim_id: str,
    tick: int,
    service: SimulationService = Depends(get_simulation_service),
) -> TickStateResponse:
    """Get complete state snapshot at a specific tick."""
    try:
        # Validate tick
        if tick < 0:
            raise HTTPException(
                status_code=400, detail=f"Invalid tick: {tick} (must be >= 0)"
            )

        orch = service.get_simulation(sim_id)
        current_tick = orch.current_tick()

        if tick > current_tick:
            raise HTTPException(
                status_code=400,
                detail=f"Tick {tick} is in the future (current tick: {current_tick})",
            )

        # For live simulations, only current tick is fully supported
        if tick != current_tick:
            raise HTTPException(
                status_code=400,
                detail=f"Historical tick state only available for database simulations. Current tick: {current_tick}",
            )

        current_day = orch.current_day()

        # Build agent states
        config = service.get_config(sim_id)["original"]
        agent_list = config.get("agents") or config.get("agent_configs", [])

        agents = {}
        queue1_total = 0
        queue2_total = 0
        total_system_cost = 0

        for agent_config in agent_list:
            agent_id = agent_config["id"]

            balance = orch.get_agent_balance(agent_id) or 0
            unsecured_cap = agent_config.get("unsecured_cap", 0)
            queue1_size = orch.get_queue1_size(agent_id)

            liquidity = balance + unsecured_cap
            headroom = unsecured_cap - max(0, -balance)

            costs_dict = orch.get_agent_accumulated_costs(agent_id)
            costs = AgentCostBreakdown(**costs_dict)

            # Get queue2 size for this agent
            rtgs_tx_ids = orch.get_rtgs_queue_contents()
            queue2_size = 0
            for tx_id in rtgs_tx_ids:
                tx_details = orch.get_transaction_details(tx_id)
                if tx_details and tx_details["sender_id"] == agent_id:
                    queue2_size += 1

            agents[agent_id] = AgentStateSnapshot(
                balance=balance,
                unsecured_cap=unsecured_cap,
                liquidity=liquidity,
                headroom=headroom,
                queue1_size=queue1_size,
                queue2_size=queue2_size,
                costs=costs,
            )

            queue1_total += queue1_size
            queue2_total += queue2_size
            total_system_cost += costs.total_cost

        # Build system metrics
        metrics_dict = orch.get_system_metrics()
        system = SystemStateSnapshot(
            total_arrivals=metrics_dict["total_arrivals"],
            total_settlements=metrics_dict["total_settlements"],
            settlement_rate=metrics_dict["settlement_rate"],
            queue1_total_size=queue1_total,
            queue2_total_size=queue2_total,
            total_system_cost=total_system_cost,
        )

        return TickStateResponse(
            simulation_id=sim_id,
            tick=current_tick,
            day=current_day,
            agents=agents,
            system=system,
        )

    except SimulationNotFoundError:
        raise HTTPException(
            status_code=404, detail=f"Simulation not found: {sim_id}"
        ) from None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}") from e
