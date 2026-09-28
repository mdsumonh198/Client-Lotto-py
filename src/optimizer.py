import random
import time
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
    progress_callback=None,
):
    all_results = all_combinations(number_from, number_to, result_size)
    if not all_results:
        raise ValueError("No possible results")

    total_draws = len(all_results)

    # ইনিশিয়াল ডাইভার্স কনস্ট্রেইন্ট
    step = max(1, total_draws // seed_constraint_count)
    constrained = [all_results[i] for i in range(0, total_draws, step)][:seed_constraint_count]
    seen = set(constrained)
    last = None

    for round_no in range(1, max_rounds + 1):
        if progress_callback:
            progress_callback(
                round_no=round_no,
                max_rounds=max_rounds,
                tickets_count=len(last["tickets"]) if last and "tickets" in last else 0,
                total_draws=total_draws,
                covered_draws="Calculating...",
                pending_violations="Calculating...",
                coverage_pct=0,
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

        # দ্রুত ভেরিফাই করে ফেইলিউর খোঁজা
        violations = find_violating_results(
            number_from, number_to, result_size, last["tickets"], targets
        )
        
        current_tickets = len(last["tickets"])
        pending_count = len(violations)
        covered_count = total_draws - pending_count
        coverage_pct = round((covered_count / total_draws) * 100, 2)

        if progress_callback:
            progress_callback(
                round_no=round_no,
                max_rounds=max_rounds,
                tickets_count=current_tickets,
                total_draws=total_draws,
                covered_draws=covered_count,
                pending_violations=pending_count,
                coverage_pct=coverage_pct,
                message=f"Round {round_no} Completed | Coverage: {coverage_pct}% | Tickets: {current_tickets}"
            )

        # সব ড্র কভার হয়ে গেলে সমাপ্ত
        if not violations:
            verification = verify_ticket_set(
                number_from, number_to, result_size, last["tickets"], targets
            )
            return {
                "rounds": round_no,
                **last,
                "verification": verification,
            }

        # স্মার্ট ডাইভার্স কনস্ট্রেইন্ট যোগ করা
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

    # ফাইনাল ভেরিফিকেশন
    verification = verify_ticket_set(
        number_from, number_to, result_size, last["tickets"], targets
    )
    return {
        "rounds": max_rounds,
        **(last or {}),
        "verification": verification,
        "status": "PROVED OPTIMAL" if verification["all_targets_pass"] else "BEST FOUND",
    }
