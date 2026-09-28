import random
from .core import all_combinations
from .solver_cp_sat import solve_min_tickets
from .verifier import find_violating_results, verify_ticket_set


def optimize_with_constraint_generation(
    number_from,
    number_to,
    ticket_size,
    result_size,
    targets,
    seed_constraint_count=50,
    max_rounds=150,
    time_limit_seconds=60,
    max_constraints_per_round=100,
    progress_callback=None,  # স্ক্রিনে লাইভ আপডেট পাঠানোর জন্য
):
    all_results = all_combinations(number_from, number_to, result_size)
    if not all_results:
        raise ValueError("No possible results")

    step = max(1, len(all_results) // seed_constraint_count)
    constrained = [all_results[i] for i in range(0, len(all_results), step)][:seed_constraint_count]
    seen = set(constrained)
    last = None

    for round_no in range(1, max_rounds + 1):
        if progress_callback:
            progress_callback(
                round_no=round_no,
                max_rounds=max_rounds,
                tickets_count=len(last["tickets"]) if last and "tickets" in last else 0,
                pending_violations="Calculating...",
                message=f"Solving MIP Round {round_no} with {len(constrained)} constraints..."
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
        
        if last["status"] in ("INFEASIBLE", "MODEL INVALID", "UNKNOWN"):
            return {"rounds": round_no, **last}

        violations = find_violating_results(
            number_from, number_to, result_size, last["tickets"], targets
        )
        
        current_tickets = len(last["tickets"])

        if progress_callback:
            progress_callback(
                round_no=round_no,
                max_rounds=max_rounds,
                tickets_count=current_tickets,
                pending_violations=len(violations),
                message=f"Round {round_no} Finished. Selected Tickets: {current_tickets} | Uncovered Violations: {len(violations):,}"
            )

        if not violations:
            verification = verify_ticket_set(
                number_from, number_to, result_size, last["tickets"], targets
            )
            return {
                "rounds": round_no,
                **last,
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
    return {
        "rounds": max_rounds,
        **(last or {}),
        "verification": verification,
        "status": "PROVED OPTIMAL" if verification["all_targets_pass"] else "BEST FOUND",
    }
