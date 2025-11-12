"""
Investigate the 21 split parent transactions that are "effectively settled"
but not fully settled themselves.
"""

import json
import yaml
from pathlib import Path
from payment_simulator._core import Orchestrator


def test_split_parent_investigation():
    """Investigate split parent transaction settlement behavior."""

    # Load the problematic scenario configuration
    config_path = Path(__file__).parent.parent.parent.parent / "examples" / "configs" / "5_agent_lsm_collateral_scenario.yaml"
    if not config_path.exists():
        pytest.skip(f"Config file not found: {config_path}. This test requires example config files.")

    root_dir = Path(__file__).parent.parent.parent.parent

    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Convert to orchestrator config format
    orchestrator_config = {
        "ticks_per_day": config["simulation"]["ticks_per_day"],
        "num_days": config["simulation"]["num_days"],
        "rng_seed": config["simulation"]["rng_seed"],
        "agent_configs": [],
    }

    # Convert agent configs
    for agent in config["agents"]:
        agent_config = {
            "id": agent["id"],
            "opening_balance": agent["opening_balance"],
            "credit_limit": agent.get("credit_limit", 0),
        }

        # Handle policy - load JSON if FromJson type
        policy = agent["policy"]
        if policy.get("type") == "FromJson" and "json_path" in policy:
            # Read the policy JSON file (path is relative to project root)
            policy_file = root_dir / policy["json_path"]
            with open(policy_file) as f:
                policy_json = f.read()
            # Pass as json string instead of path
            agent_config["policy"] = {
                "type": "FromJson",
                "json": policy_json,
            }
        else:
            agent_config["policy"] = policy

        # Add arrival config if present
        if "arrival_config" in agent:
            agent_config["arrival_config"] = agent["arrival_config"]

        # Add collateral config if present
        if "collateral_pool_capacity" in agent:
            agent_config["collateral_pool_capacity"] = agent["collateral_pool_capacity"]

        orchestrator_config["agent_configs"].append(agent_config)

    # Create orchestrator
    print("Creating orchestrator and running simulation...")
    orch = Orchestrator.new(orchestrator_config)

    # Run full simulation
    total_ticks = config["simulation"]["ticks_per_day"] * config["simulation"]["num_days"]
    for _ in range(total_ticks):
        orch.tick()

    print("\n" + "="*80)
    print("INVESTIGATING SPLIT PARENT TRANSACTIONS")
    print("="*80 + "\n")

    # Get all transactions by examining all events
    all_events = orch.get_all_events()

    # Build transaction database from events
    transactions = {}
    parent_to_children = {}

    for event in all_events:
        if event['event_type'] == 'Arrival':
            tx_id = event['tx_id']
            transactions[tx_id] = {
                'id': tx_id,
                'sender': event['sender_id'],
                'receiver': event['receiver_id'],
                'amount': event['amount'],
                'deadline': event['deadline'],
                'parent_id': None,  # Arrivals have no parent
                'children': [],
                'settled_amount': 0,
            }

        elif event['event_type'] == 'PolicySplit':
            # A transaction was split
            parent_id = event['tx_id']
            child_ids = event['child_ids']

            if parent_id in transactions:
                transactions[parent_id]['children'] = child_ids
                parent_to_children[parent_id] = child_ids

            # Create child transaction records
            for child_id in child_ids:
                transactions[child_id] = {
                    'id': child_id,
                    'parent_id': parent_id,
                    'settled_amount': 0,
                }

        elif event['event_type'] == 'Settlement':
            # A transaction was settled
            tx_id = event['tx_id']
            amount = event['amount']

            if tx_id in transactions:
                transactions[tx_id]['settled_amount'] += amount

    # Now analyze split parents
    print(f"Total transactions tracked: {len(transactions)}")
    print(f"Total split parents: {len(parent_to_children)}")

    # Find split parents that have all children settled but aren't fully settled themselves
    problematic_parents = []

    for parent_id, child_ids in parent_to_children.items():
        parent = transactions.get(parent_id)
        if not parent:
            continue

        # Check if all children are settled
        all_children_settled = True
        total_child_settled_amount = 0
        for child_id in child_ids:
            child = transactions.get(child_id)
            if child:
                if child['settled_amount'] == 0:
                    all_children_settled = False
                total_child_settled_amount += child['settled_amount']

        # Check if parent itself is fully settled
        parent_fully_settled = (parent['settled_amount'] == parent['amount'])

        # Find cases where all children settled but parent isn't
        if all_children_settled and not parent_fully_settled:
            problematic_parents.append({
                'parent_id': parent_id,
                'parent_amount': parent['amount'],
                'parent_settled': parent['settled_amount'],
                'num_children': len(child_ids),
                'total_child_settled': total_child_settled_amount,
            })

    print(f"\n📊 Found {len(problematic_parents)} problematic split parents:")
    print(f"   (all children settled, but parent not fully settled)\n")

    for i, p in enumerate(problematic_parents[:10], 1):  # Show first 10
        print(f"{i}. Parent: {p['parent_id']}")
        print(f"   Amount: ${p['parent_amount'] / 100:,.2f}")
        print(f"   Parent settled: ${p['parent_settled'] / 100:,.2f}")
        print(f"   Children: {p['num_children']}")
        print(f"   Total child settled: ${p['total_child_settled'] / 100:,.2f}")
        print(f"   Discrepancy: ${(p['parent_amount'] - p['parent_settled']) / 100:,.2f}")
        print()

    if len(problematic_parents) > 10:
        print(f"   ... and {len(problematic_parents) - 10} more\n")

    # Summary statistics
    if problematic_parents:
        total_parent_amounts = sum(p['parent_amount'] for p in problematic_parents)
        total_parent_settled = sum(p['parent_settled'] for p in problematic_parents)
        total_child_settled = sum(p['total_child_settled'] for p in problematic_parents)

        print("-"*80)
        print(f"\n📈 Summary Statistics:")
        print(f"   Total parent amounts:        ${total_parent_amounts / 100:,.2f}")
        print(f"   Total parent settled:        ${total_parent_settled / 100:,.2f}")
        print(f"   Total children settled:      ${total_child_settled / 100:,.2f}")
        print(f"   Parent settlement shortfall: ${(total_parent_amounts - total_parent_settled) / 100:,.2f}")

        print(f"\n🔍 Analysis:")
        if total_child_settled > 0:
            print(f"   Children settled {total_child_settled / 100:,.2f} cents worth")
            print(f"   But parents only show {total_parent_settled / 100:,.2f} cents settled")
            print(f"   This suggests children settlements aren't being reflected in parent settled_amount")
        else:
            print(f"   Children show 0 settled amount - tracking issue")

    print("\n" + "="*80)
    print("\n💡 HYPOTHESIS:")
    print("   When a transaction is split, children settle independently.")
    print("   The parent's settled_amount should accumulate from child settlements,")
    print("   but it appears this isn't happening correctly.")
    print("\n   This causes is_effectively_settled() to return TRUE (children all settled)")
    print("   while is_fully_settled() returns FALSE (parent settled_amount < amount).")
    print("\n   Fix: When a child settles, update the parent's settled_amount as well.")
    print("="*80)


if __name__ == "__main__":
    test_split_parent_investigation()
