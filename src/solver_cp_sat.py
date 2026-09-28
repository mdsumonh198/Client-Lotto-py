from itertools import combinations
from ortools.sat.python import cp_model
from .core import all_combinations, to_mask


def build_candidates(number_from, number_to, ticket_size):
    return all_combinations(number_from, number_to, ticket_size)


def solve_min_tickets(
    number_from,
    number_to,
    ticket_size,
    result_size,
    targets,
    constrained_results=None,
    time_limit_seconds=60,
):
    tickets = build_candidates(number_from, number_to, ticket_size)
    ticket_masks = [to_mask(t) for t in tickets]

    if constrained_results is None:
        constrained_results = all_combinations(number_from, number_to, result_size)

    model = cp_model.CpModel()
    x = [model.NewBoolVar(f"x_{i}") for i in range(len(tickets))]

    for ridx, result in enumerate(constrained_results):
        rmask = to_mask(result)
        for k, minimum in targets.items():
            matching_indices = [i for i, tm in enumerate(ticket_masks) if (tm & rmask).bit_count() == k]
            if minimum > 0:
                if len(matching_indices) < minimum:
                    return {
                        "status": "INFEASIBLE",
                        "tickets": [],
                        "objective": None,
                        "reason": f"Result {result} cannot reach exact-{k} >= {minimum}",
                    }
                model.Add(sum(x[i] for i in matching_indices) >= minimum)

    # দ্রুত ইনিশিয়াল সমাধান দিয়ে ওয়ার্ম স্টার্ট
    hint_indices = []
    for r_idx in range(len(constrained_results)):
        rmask = to_mask(constrained_results[r_idx])
        for i, tm in enumerate(ticket_masks):
            if (tm & rmask).bit_count() in targets:
                hint_indices.append(i)
                break
    for h_idx in set(hint_indices):
        model.AddHint(x[h_idx], 1)

    model.Minimize(sum(x))
    solver = cp_model.CpSolver()
    
    # মেমোরি গার্ড: ২.৫ জিবির বেশি র‍্যাম কখনোই খরচ করবে না (ক্র্যাশ সম্পূর্ণ বন্ধ)
    solver.parameters.max_memory_in_mb = 2500
    solver.parameters.num_search_workers = 1  # ১টি ওয়ার্কার মেমোরি অনেক কম টানে
    
    if time_limit_seconds:
        solver.parameters.max_time_in_seconds = float(time_limit_seconds)

    status_code = solver.Solve(model)
    status_map = {
        cp_model.OPTIMAL: "PROVED OPTIMAL",
        cp_model.FEASIBLE: "BEST FOUND",
        cp_model.INFEASIBLE: "INFEASIBLE",
        cp_model.MODEL_INVALID: "MODEL INVALID",
        cp_model.UNKNOWN: "BEST FOUND (TIMEOUT)",
    }
    status = status_map.get(status_code, "BEST FOUND")

    selected = []
    for i in range(len(tickets)):
        try:
            if solver.Value(x[i]) == 1:
                selected.append(tickets[i])
        except Exception:
            pass

    if not selected and hint_indices:
        selected = [tickets[i] for i in set(hint_indices)]
        status = "BEST FOUND"

    return {
        "status": status,
        "tickets": selected,
        "objective": len(selected) if selected else None,
        "best_bound": solver.BestObjectiveBound() if status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None,
    }
