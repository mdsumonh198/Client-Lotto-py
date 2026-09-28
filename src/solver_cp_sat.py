import random
import os
import pandas as pd
from .core import all_combinations
from .solver_cp_sat import solve_min_tickets
from .verifier import find_violating_results, verify_ticket_set


CHECKPOINT_FILE = "latest_checkpoint_tickets.csv"


def optimize_with_constraint_generation(
    number_from,
    number_to,
    ticket_size,
    result_size,
    targets,
    seed_constraint_count=100,
    max_rounds=150,
    time_limit_seconds=60,
    max_constraints_per_round=300,
    progress_callback=None,
):
    all_results = all_combinations(number_from, number_to, result_size)
    if not all_results:
        raise ValueError("No possible results")

    total_draws = len(all_results)
    step = max(1, total_draws // seed_constraint_count)
    constrained = [all_results[i] for i in range(0, total_draws, step)][:seed_constraint_count]
    seen = set(constrained)
    last = None

    last_covered = 0
    last_pending = total_draws
    last_pct = 0.0

    for round_no in range(1, max_rounds + 1):
        if progress_callback:
            progress_callback(
                round_no=round_no,
                max_rounds=max_rounds,
                tickets_count=len(last["tickets"]) if last and "tickets" in last else 0,
                total_draws=total_draws,
                covered_draws=last_covered,
                pending_violations=last_pending,
                coverage_pct=last_pct,
                message=f"MIP Round {round_no}: Solving with {len(constrained)} constraints..."
            )

        last = solve_min_tickets(
            number_from,
            number_to,
            ticket_size,
            result_size,
            targets,
            constrained_results=constrained,
            time_limit_seconds=time_limit_seconds,
        )
        
        # প্রতি রাউন্ডের পাওয়া টিকেট সাথে সাথে ডিস্কে সেভ করা (যাতে কখনই ডেটা না হারায়)
        if last and last.get("tickets"):
            try:
                cols = [f"N{i+1}" for i in range(len(last["tickets"][0]))]
                pd.DataFrame(last["tickets"], columns=cols).to_csv(CHECKPOINT_FILE, index=False)
            except Exception:
                pass

        if last["status"] in ("INFEASIBLE", "MODEL INVALID"):
            return {"rounds": round_no, **last}

        violations = find_violating_results(
            number_from, number_to, result_size, last["tickets"], targets
        )
        
        current_tickets = len(last["tickets"])
        pending_count = len(violations)
        covered_count = total_draws - pending_count
        coverage_pct = round((covered_count / total_draws) * 100, 2)

        last_covered = covered_count
        last_pending = pending_count
        last_pct = coverage_pct

        if progress_callback:
            progress_callback(
                round_no=round_no,
                max_rounds=max_rounds,
                tickets_count=current_tickets,
                total_draws=total_draws,
                covered_draws=covered_count,
                pending_violations=pending_count,
                coverage_pct=coverage_pct,
                message=f"Round {round_no} Done • Progress: {coverage_pct}% • Tickets: {current_tickets}"
            )

        if not violations:
            verification = verify_ticket_set(
                number_from, number_to, result_size, last["tickets"], targets
            )
            tagged_tickets = _tag_budget_steps(last["tickets"])
            return {
                "rounds": round_no,
                **last,
                "tickets": tagged_tickets,
                "verification": verification,
            }

        random.shuffle(violations)
        added = 0
        for result, _failed in violations:
            if result not in seen:
                constrained.append(result)
                seen.add(result)
                added += 1
                if added >= max_constraints_per_round:
                    break

        if added == 0:
            break

    verification = verify_ticket_set(
        number_from, number_to, result_size, last["tickets"], targets
    )
    tagged_tickets = _tag_budget_steps(last.get("tickets", []))
    return {
        "rounds": max_rounds,
        **(last or {}),
        "tickets": tagged_tickets,
        "verification": verification,
        "status": "PROVED OPTIMAL" if verification["all_targets_pass"] else "BEST FOUND",
    }


def _tag_budget_steps(tickets):
    total = len(tickets)
    if total == 0:
        return []
    tagged = []
    step1_cutoff = max(1, int(total * 0.25))
    step2_cutoff = max(1, int(total * 0.50))
    for i, t in enumerate(tickets, 1):
        if i <= step1_cutoff:
            tier = "Step 1 (Starter - 25% Budget)"
        elif i <= step2_cutoff:
            tier = "Step 2 (Growth - 50% Budget)"
        else:
            tier = "Step 3 (Guaranteed - 100% Budget)"
        tagged.append((*t, tier))
    return tagged
