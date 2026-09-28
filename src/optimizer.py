from .core import all_combinations
from .solver_cp_sat import solve_min_tickets
from .verifier import find_violating_results, verify_ticket_set


def optimize_with_constraint_generation(
    number_from,
    number_to,
    ticket_size,
    result_size,
    targets,
    seed_constraint_count=20,
    max_rounds=100,
    time_limit_seconds=None,
):
    all_results = all_combinations(number_from, number_to, result_size)
    if not all_results:
        raise ValueError("No possible results")

    constrained = list(all_results[: min(seed_constraint_count, len(all_results))])
    seen = set(constrained)
    last = None

    for round_no in range(1, max_rounds + 1):
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
        if not violations:
            verification = verify_ticket_set(
                number_from, number_to, result_size, last["tickets"], targets
            )
            # Important: CP-SAT optimality here only proves optimality for the current
            # accumulated exact constraints. Because every omitted constraint has now
            # been verified as satisfied, an OPTIMAL status is a valid global proof
            # for this exact formulation.
            return {
                "rounds": round_no,
                **last,
                "verification": verification,
            }

        added = 0
        for result, _failed in violations:
            if result not in seen:
                constrained.append(result)
                seen.add(result)
                added += 1
        if added == 0:
            break

    return {
        "rounds": max_rounds,
        **(last or {}),
        "status": "BEST FOUND / NOT FULLY VERIFIED",
    }
