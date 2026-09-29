"""CLI runner (VPS friendly).

Examples
  python app.py --from 1 --to 25 --ticket 6 --result 6 --targets 4:10,3:25 --time 600 --out output
  python app.py            # interactive prompts
"""
import argparse
import os
import sys
import time

from src.core import combination_count, validate_game
from src.export import save_outputs
from src.optimizer import optimize_with_constraint_generation


def parse_targets(raw):
    targets = {}
    if raw:
        for part in raw.split(","):
            k, v = part.split(":")
            targets[int(k.strip())] = int(v.strip())
    return targets


def main():
    ap = argparse.ArgumentParser(description="Universal Lottery / Combination Optimizer")
    ap.add_argument("--from", dest="nfrom", type=int)
    ap.add_argument("--to", dest="nto", type=int)
    ap.add_argument("--ticket", type=int)
    ap.add_argument("--result", type=int)
    ap.add_argument("--targets", type=str, help="e.g. 5:1,4:10,3:25")
    ap.add_argument("--time", type=float, default=0, help="TOTAL time budget in seconds. 0 (default) = NO TIMEOUT, runs until proven/best minimum is found or interrupted")
    ap.add_argument("--workers", type=int, default=None, help="CP-SAT workers (default: max(8, cpu cores))")
    ap.add_argument("--threads", type=int, default=None, help="NumPy threads for greedy/prune/verify (default: cpu cores)")
    ap.add_argument("--gap", type=float, default=0.0, help="stop CP-SAT at this relative gap, e.g. 0.05 (faster, no proof)")
    ap.add_argument("--no-exact", action="store_true", help="skip CP-SAT, heuristic + exact verification only (fastest)")
    ap.add_argument("--exact-limit", type=int, default=150_000, help="max candidate tickets for CP-SAT model")
    ap.add_argument("--seed", type=int, default=12345)
    ap.add_argument("--out", type=str, default="output")
    a = ap.parse_args()

    if a.nfrom is None:                                   # interactive mode
        a.nfrom = int(input("Number From: "))
        a.nto = int(input("Number To: "))
        a.ticket = int(input("Ticket Size: "))
        a.result = int(input("Result Size: "))
        a.targets = input("Targets (example 4:10,5:1): ").strip()
    validate_game(a.nfrom, a.nto, a.ticket, a.result)
    targets = parse_targets(a.targets)

    print("Possible tickets:", f"{combination_count(a.nfrom, a.nto, a.ticket):,}")
    print("Possible results:", f"{combination_count(a.nfrom, a.nto, a.result):,}")
    print(f"CPU cores: {os.cpu_count()} | time budget: {a.time:.0f}s\n", flush=True)

    t0 = time.time()
    out = optimize_with_constraint_generation(
        a.nfrom, a.nto, a.ticket, a.result, targets,
        time_limit_seconds=a.time, workers=a.workers, threads=a.threads, gap=a.gap, use_cp_sat=not a.no_exact,
        max_exact_tickets=a.exact_limit, seed=a.seed,
        log=lambda m: print(f"[{time.time() - t0:7.1f}s] {m}", flush=True),
    )

    print("\n================ RESULT ================")
    print("Status        :", out["status"])
    if out["status"] == "INFEASIBLE":
        print("Reason        :", out.get("reason"))
        return
    print("Total tickets :", out["objective"])
    print("Lower bound   :", out["lower_bound"], "(PROVED OPTIMAL only when equal to total tickets)")
    ver = out["verification"]
    print("Results checked (ALL, exact):", f"{ver['total_results_checked']:,}")
    for k, st in sorted(ver["stats"].items()):
        print(f"  Exact {k}: min={st['min']} max={st['max']} avg={st['avg']:.3f}")
    for k, t in sorted(ver["targets"].items()):
        print(f"  Target exact-{k} >= {t['required']}: worst-case={t['worst_case']} -> {'PASS' if t['pass'] else 'FAIL'}")
    print("All targets pass:", ver["all_targets_pass"])
    cfg = {"from": a.nfrom, "to": a.nto, "ticket": a.ticket, "result": a.result, "targets": targets}
    files = save_outputs(out, a.out, cfg)
    print(f"\nSaved to '{a.out}/': {', '.join(files)}")
    print(f"Total elapsed: {time.time() - t0:.1f}s")


if __name__ == "__main__":
    sys.exit(main())
