"""Exact verification against EVERY possible result (NumPy-vectorised, no sampling)."""
import numpy as np

from .core import combo_masks, overlap_counts, to_mask, validate_game


def _report_from_counts(cnt, results_numbers, n_tickets, targets):
    """cnt: [R, k1] = number of tickets with exact-k overlap for each result."""
    k1 = cnt.shape[1]
    stats = {}
    for k in range(k1):
        col = cnt[:, k]
        i_min, i_max = int(col.argmin()), int(col.argmax())
        stats[k] = {
            "min": int(col[i_min]),
            "max": int(col[i_max]),
            "avg": float(col.mean()),
            "worst_result": results_numbers(i_min),
            "best_result": results_numbers(i_max),
        }
    target_status = {}
    for k, required in (targets or {}).items():
        actual = stats.get(int(k), {"min": 0})["min"]
        target_status[int(k)] = {"required": int(required), "worst_case": actual, "pass": actual >= int(required)}
    return {
        "total_tickets": int(n_tickets),
        "total_results_checked": int(cnt.shape[0]),
        "stats": stats,
        "targets": target_status,
        "all_targets_pass": all(x["pass"] for x in target_status.values()) if target_status else True,
    }


def verify_problem(problem, ticket_masks, targets=None):
    """Verify a ticket set (uint64 masks) on a Problem instance."""
    targets = problem.targets if targets is None else targets
    cnt = overlap_counts(problem.rmasks, np.asarray(ticket_masks, dtype=np.uint64), problem.k1)
    return _report_from_counts(cnt, lambda i: problem.numbers(problem.rmasks[i]), len(ticket_masks), targets)


def verify_ticket_set(number_from, number_to, result_size, tickets, targets=None):
    """Backward-compatible API: tickets given as tuples of real numbers."""
    n = number_to - number_from + 1
    validate_game(number_from, number_to, 1, result_size)
    tm = np.array([to_mask(t) >> number_from for t in tickets], dtype=np.uint64)
    rm = combo_masks(n, result_size)
    cnt = overlap_counts(rm, tm, result_size + 1)
    from .core import mask_to_numbers
    return _report_from_counts(cnt, lambda i: mask_to_numbers(rm[i], number_from), len(tickets), targets or {})
