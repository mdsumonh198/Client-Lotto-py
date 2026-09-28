from collections import defaultdict
from statistics import mean
from .core import all_combinations, to_mask


def verify_ticket_set(number_from, number_to, result_size, tickets, targets=None):
    targets = targets or {}
    ticket_masks = [to_mask(t) for t in tickets]
    results = all_combinations(number_from, number_to, result_size)

    by_k_values = defaultdict(list)
    worst_result_for_k = {}
    best_result_for_k = {}

    per_result = []
    for result in results:
        rmask = to_mask(result)
        counts = defaultdict(int)
        for tmask in ticket_masks:
            k = (tmask & rmask).bit_count()
            counts[k] += 1
        per_result.append((result, dict(counts)))
        for k in range(0, result_size + 1):
            by_k_values[k].append(counts.get(k, 0))

    stats = {}
    for k, values in by_k_values.items():
        min_v = min(values)
        max_v = max(values)
        min_i = values.index(min_v)
        max_i = values.index(max_v)
        stats[k] = {
            "min": min_v,
            "max": max_v,
            "avg": mean(values),
            "worst_result": results[min_i],
            "best_result": results[max_i],
        }

    target_status = {}
    for k, required in targets.items():
        actual = stats.get(k, {"min": 0})["min"]
        target_status[k] = {
            "required": required,
            "worst_case": actual,
            "pass": actual >= required,
        }

    return {
        "total_tickets": len(tickets),
        "total_results_checked": len(results),
        "stats": stats,
        "targets": target_status,
        "all_targets_pass": all(x["pass"] for x in target_status.values()) if target_status else True,
    }


def find_violating_results(number_from, number_to, result_size, tickets, targets):
    """Return all result combinations that violate at least one exact-match target."""
    ticket_masks = [to_mask(t) for t in tickets]
    violations = []
    for result in all_combinations(number_from, number_to, result_size):
        rmask = to_mask(result)
        counts = defaultdict(int)
        for tmask in ticket_masks:
            counts[(tmask & rmask).bit_count()] += 1
        failed = {k: (counts.get(k, 0), req) for k, req in targets.items() if counts.get(k, 0) < req}
        if failed:
            violations.append((result, failed))
    return violations
