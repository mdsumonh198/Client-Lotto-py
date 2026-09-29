# Universal Lottery / Combination Optimizer (fast edition)

For any game (number range 0..40, ticket size, result size, exact-match targets) this finds a small ticket set
that meets every target for **every possible result**, verified exactly (no sampling).

## Status meaning
- **PROVED OPTIMAL**: verified feasible set whose size equals a mathematically valid lower bound.
- **BEST FOUND**: verified feasible, but fewer tickets are not ruled out.
- **INFEASIBLE**: impossible even using every possible ticket.

## How it is fast
1. NumPy uint64 bit-masks + vectorised popcount for all match counting.
2. Greedy warm start + pruning gives a verified feasible set in seconds (upper bound).
3. Small/medium games: one full exact CP-SAT model. Large: incremental constraint generation (model kept, hint reused).
4. Lower bounds: double-counting bound + CP-SAT bound. Equal to best found -> PROVED OPTIMAL.
5. Leftover time: LNS (drop tickets, repair, prune). It never gives up on its own — if stuck, it widens the perturbation and keeps trying until the deadline (or you stop the job). Games with > 150k candidate tickets (config.max_exact_tickets, a safety limit for this RAM size) skip the exact CP-SAT proof step entirely and rely on greedy+LNS only, so for those games the result is never "Proven" — a mathematical proof at that scale is generally impractical on a small VPS.
6. CP-SAT uses max(8, CPU cores) workers.
7. Greedy/prune/LNS/verification use NumPy multi-threading (config.THREADS, default = CPU cores). Threads help these; CP-SAT workers help the exact solver. Both matter separately.

## VPS usage
```bash
./run_vps.sh --from 1 --to 25 --ticket 6 --result 6 --targets 4:10,3:25 --time 900
tail -f run.log          # progress; results in ./output/ (tickets.csv, verification.csv, .xlsx, report.txt, result.json)
```
Or directly: `pip install -r requirements.txt && python app.py --help`.
Options: `--time` total seconds, `--workers`, `--gap 0.05` (stop early, no proof), `--no-exact` (heuristic only, fastest), `--exact-limit`.

Solver settings for the Streamlit UI are fixed in `config.py` (users only see them). Streamlit: `streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port 8501`
Jobs started from the Streamlit page run as detached background OS processes (see `src/jobs.py`),
independent of the browser session and the Streamlit process itself. Closing the tab, losing the
connection, or reloading the page does NOT stop a running job — reopening the page reconnects to
it and shows live progress from `jobs/<job_id>/run.log`. Job state lives under `jobs/`.

## No timeout, no round cap
There is no fixed number of rounds and no timeout anywhere in the pipeline (greedy, CP-SAT
constraint generation, LNS). The ONLY things that can end a search before the deadline are:
- CP-SAT itself proving the answer optimal or infeasible (a real mathematical conclusion, not an
  artificial limit),
- you manually clicking "stop job",
- or the tiny/degenerate case where the greedy step already covers everything with 0 leftover work.
Otherwise it keeps working — LNS specifically never "gives up": when stuck it widens its search
instead of stopping. This means a run can legitimately take a very long time on hard instances.

## No timeout by default
`config.TIME_LIMIT_SECONDS = 0` means the solver runs until it finds a proven-optimal or best
ticket set, with no cap. The Streamlit page shows a live elapsed timer while a job runs, and a
"বন্ধ করুন" (stop) button to end it manually at any time.
Caution: for small/medium games (<=150,000 candidate tickets) the optimizer tries to *prove*
optimality with one exact CP-SAT model, which for a hard instance can run for a very long time
with no cap — there is no reliable way to estimate this in advance. Large games skip that exact
step automatically and are bounded by the greedy+prune+LNS stages, which stop on their own.

## Limits
Enumeration limit is 6,000,000 tickets/results. Exact final verification costs (results x tickets) popcounts,
so very large games take long even for the heuristic path.
