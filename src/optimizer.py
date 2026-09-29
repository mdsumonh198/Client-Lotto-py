"""Orchestrator:  greedy warm start -> incremental CP-SAT constraint generation -> exact final verification.

Status meaning (never over-claimed):
  PROVED OPTIMAL : verified feasible set whose size == a mathematically valid lower bound.
  BEST FOUND     : verified feasible set, but no proof that fewer tickets are impossible.
  INFEASIBLE     : proved impossible (even using every possible ticket).
"""
import math
import os
import time

import numpy as np

from .core import Problem, _C, set_threads
from .heuristic import greedy_cover, improve_lns, prune
from .solver_cp_sat import HAS_ORTOOLS, IncrementalModel
from .verifier import verify_problem


def optimize_with_constraint_generation(
    number_from,
    number_to,
    ticket_size,
    result_size,
    targets,
    seed_constraint_count=40,
    batch_size=100,
    max_rounds=1000,
    time_limit_seconds=600,
    workers=None,
    threads=None,
    gap=0.0,
    use_cp_sat=True,
    seed=12345,
    max_exact_tickets=150_000,
    full_model_max_terms=25_000_000,
    log=None,
):
    t0 = time.time()
    log = log or (lambda *_: None)
    set_threads(threads)
    workers = int(workers or max(8, os.cpu_count() or 1))   # >=8 enables CP-SAT LNS portfolio
    rng = np.random.default_rng(seed)
    total_budget = float(time_limit_seconds) if time_limit_seconds else 10 ** 9
    deadline = t0 + total_budget

    p = Problem(number_from, number_to, ticket_size, result_size, targets)
    from . import core as _c
    log(f"Tickets: {p.n_tickets:,} | Results: {p.n_results:,} | CP-SAT workers: {workers} | NumPy threads: {_c.THREADS}")

    reason = p.infeasible_reason()
    if reason:
        return {"status": "INFEASIBLE", "reason": reason, "tickets": [], "objective": None, "rounds": 0,
                "lower_bound": None, "elapsed_seconds": time.time() - t0}

    if not p.targets:                                   # nothing to guarantee
        rep = verify_problem(p, [], {})
        return {"status": "PROVED OPTIMAL", "tickets": [], "objective": 0, "rounds": 0, "lower_bound": 0,
                "verification": rep, "elapsed_seconds": time.time() - t0}

    lb = p.counting_lower_bound()
    log(f"Counting lower bound: {lb}")

    log("Step 1: fast greedy warm start ...")
    best = prune(p, greedy_cover(p, rng=rng, log=log), rng)
    log(f"   greedy+prune -> {len(best)} tickets (verified feasible)")

    rounds = 0
    exact_possible = use_cp_sat and HAS_ORTOOLS and p.n_tickets <= max_exact_tickets
    terms_per_result = sum(_C(p.s, k) * _C(p.N - p.s, p.t - k) for k in p.ks)
    full_ok = (terms_per_result * p.n_results <= full_model_max_terms
               and p.n_results * p.n_tickets <= 300_000_000)

    if len(best) > lb and exact_possible and full_ok:
        # Small / medium game: put EVERY result in one exact model -> no rounds, solution is feasible by construction.
        log("Step 2: full exact CP-SAT model (all results as constraints) ...")
        inc = IncrementalModel(p)
        for r in range(p.n_results):
            inc.add_result(r)
        rounds = 1
        status, cand, bound = inc.solve(best, max(2.0, deadline - time.time()), workers, gap)
        if bound is not None:
            lb = max(lb, math.ceil(bound - 1e-6))
        log(f"   status={status} candidate={len(cand) if cand else None} lower_bound={lb} best={len(best)}")
        if cand is not None and len(cand) < len(best):
            if not (p.target_counts(p.tmasks[cand]) >= p.reqs[None, :]).all():
                raise RuntimeError("Internal error: full-model candidate failed verification.")
            best = cand
    elif len(best) > lb and exact_possible:
        log("Step 2: CP-SAT constraint generation ...")
        inc = IncrementalModel(p)
        for r in rng.choice(p.n_results, size=min(seed_constraint_count, p.n_results), replace=False):
            inc.add_result(r)
        round_cap = max(10.0, 0.2 * total_budget)
        while rounds < max_rounds and len(best) > lb:
            remaining = deadline - time.time()
            if remaining < 2:
                log("   time budget finished")
                break
            rounds += 1
            status, cand, bound = inc.solve(best, min(remaining, round_cap), workers, gap)
            if bound is not None:
                lb = max(lb, math.ceil(bound - 1e-6))
            log(f"   round {rounds}: status={status} candidate={len(cand) if cand else None} "
                f"lower_bound={lb} best={len(best)} constraints={len(inc.added)}")
            if cand is None:
                break
            deficit = np.maximum(p.reqs[None, :] - p.target_counts(p.tmasks[cand]), 0)
            tot = deficit.sum(axis=1)
            viol = np.flatnonzero(tot)
            if viol.size == 0:                          # candidate passes ALL results
                if len(cand) < len(best):
                    best = cand
                if status == "OPTIMAL":
                    break
                continue                                # only FEASIBLE: keep improving while budget remains
            fixed = prune(p, greedy_cover(p, start=cand, rng=rng), rng)   # cheap feasible repair -> better upper bound
            if len(fixed) < len(best):
                best = fixed
            if viol.size > batch_size:
                score = tot[viol] + rng.random(viol.size)
                viol = viol[np.argpartition(-score, batch_size - 1)[:batch_size]]
            if not sum(inc.add_result(r) for r in viol):
                break
    elif len(best) > lb:
        log("CP-SAT skipped (disabled / not installed / game too large for exact model) -> heuristic result only")

    # ---- use leftover time (only if not proved) to shrink the set further with LNS
    if len(best) > lb and time.time() < deadline - 3:
        log("Step 3: LNS improvement with remaining time ...")
        best = improve_lns(p, best, rng, deadline, log)

    # ---- final EXACT verification against every possible result
    report = verify_problem(p, p.tmasks[best])
    if not report["all_targets_pass"]:
        raise RuntimeError("Internal error: final verification failed.")
    proved = len(best) <= lb
    return {
        "status": "PROVED OPTIMAL" if proved else "BEST FOUND",
        "tickets": p.tickets_as_numbers(best),
        "objective": len(best),
        "lower_bound": int(lb),
        "rounds": rounds,
        "verification": report,
        "elapsed_seconds": time.time() - t0,
    }
