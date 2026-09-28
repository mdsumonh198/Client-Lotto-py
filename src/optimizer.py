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
    max_constraints_per_round=100,  # সলভার হালকা রাখতে প্রতি রাউন্ডে সর্বোচ্চ ১০০টি স্মার্ট ড্র যোগ হবে
):
    all_results = all_combinations(number_from, number_to, result_size)
    if not all_results:
        raise ValueError("No possible results")

    # ডাইভার্স ইনিশিয়াল সীড ড্র
    step = max(1, len(all_results) // seed_constraint_count)
    constrained = [all_results[i] for i in range(0, len(all_results), step)][:seed_constraint_count]
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

        # দ্রুত ভেরিফাই করে ফেইলিউর খোঁজা
        violations = find_violating_results(
            number_from, number_to, result_size, last["tickets"], targets
        )
        
        # কোনো রেজাল্ট ফেইল না করলে ১০০% কমপ্লিট!
        if not violations:
            verification = verify_ticket_set(
                number_from, number_to, result_size, last["tickets"], targets
            )
            return {
                "rounds": round_no,
                **last,
                "verification": verification,
            }

        # স্মার্ট স্যাম্পলিং: একসাথে ৫০,০০০ ড্র না দিয়ে সেরা ১০০টি ড্র সলভারে পুশ করা
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
