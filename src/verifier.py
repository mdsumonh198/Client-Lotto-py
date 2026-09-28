import numpy as np
from collections import defaultdict
from statistics import mean
from .core import all_combinations, to_mask


def _popcount_64(x):
    """NumPy সি-লেভেল ফাস্ট ৬৪-বিট Popcount (এক নিমেষে লাখ লাখ বিট গুনে ফেলে)"""
    m1 = np.uint64(0x5555555555555555)
    m2 = np.uint64(0x3333333333333333)
    m4 = np.uint64(0x0F0F0F0F0F0F0F0F)
    x -= (x >> np.uint64(1)) & m1
    x = (x & m2) + ((x >> np.uint64(2)) & m2)
    x = (x + (x >> np.uint64(4))) & m4
    x += x >> np.uint64(8)
    x += x >> np.uint64(16)
    x += x >> np.uint64(32)
    return (x & np.uint64(0x7F)).astype(np.int32)


def verify_ticket_set(number_from, number_to, result_size, tickets, targets=None):
    targets = targets or {}
    results = all_combinations(number_from, number_to, result_size)
    if not results or not tickets:
        return {"total_tickets": len(tickets), "total_results_checked": 0, "all_targets_pass": False}

    t_masks = np.array([to_mask(t) for t in tickets], dtype=np.uint64)
    r_masks = np.array([to_mask(r) for r in results], dtype=np.uint64)

    num_results = len(results)
    num_tickets = len(tickets)
    
    # প্রতি exact match level-এর কাউন্টার
    match_matrix_counts = {k: np.zeros(num_results, dtype=np.int32) for k in range(result_size + 1)}

    # মেমোরি রক্ষা করতে ব্যাচ অনুযায়ী NumPy হিসাব (সুপার ফাস্ট)
    batch_size = 5000
    for b_start in range(0, num_results, batch_size):
        b_end = min(b_start + batch_size, num_results)
        batch_r = r_masks[b_start:b_end, None]  # Shape: (batch, 1)

        # Vectorized Bitwise AND: (batch, num_tickets)
        intersections = batch_r & t_masks[None, :]
        matches = _popcount_64(intersections)

        for k in range(result_size + 1):
            match_matrix_counts[k][b_start:b_end] = np.sum(matches == k, axis=1)

    stats = {}
    for k in range(result_size + 1):
        vals = match_matrix_counts[k]
        min_idx = int(np.argmin(vals))
        max_idx = int(np.argmax(vals))
        stats[k] = {
            "min": int(vals[min_idx]),
            "max": int(vals[max_idx]),
            "avg": float(np.mean(vals)),
            "worst_result": results[min_idx],
            "best_result": results[max_idx],
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
        "total_tickets": num_tickets,
        "total_results_checked": num_results,
        "stats": stats,
        "targets": target_status,
        "all_targets_pass": all(x["pass"] for x in target_status.values()) if target_status else True,
    }


def find_violating_results(number_from, number_to, result_size, tickets, targets):
    """NumPy দিয়ে দ্রুততম সময়ে ফেইল হওয়া ড্র গুলো খুঁজে বের করা"""
    if not targets:
        return []

    results = all_combinations(number_from, number_to, result_size)
    t_masks = np.array([to_mask(t) for t in tickets], dtype=np.uint64)
    r_masks = np.array([to_mask(r) for r in results], dtype=np.uint64)

    num_results = len(results)
    batch_size = 10000
    violations = []

    for b_start in range(0, num_results, batch_size):
        b_end = min(b_start + batch_size, num_results)
        batch_r = r_masks[b_start:b_end, None]

        intersections = batch_r & t_masks[None, :]
        matches = _popcount_64(intersections)

        for i, r_idx in enumerate(range(b_start, b_end)):
            row_matches = matches[i]
            failed = {}
            for k, req in targets.items():
                cnt = int(np.count_nonzero(row_matches == k))
                if cnt < req:
                    failed[k] = (cnt, req)
            if failed:
                violations.append((results[r_idx], failed))

    return violations
