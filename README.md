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
5. Leftover time: LNS (drop tickets, repair, prune). Games with > 150k candidate tickets skip CP-SAT.
6. CP-SAT uses max(8, CPU cores) workers.

## VPS usage
```bash
./run_vps.sh --from 1 --to 25 --ticket 6 --result 6 --targets 4:10,3:25 --time 900
tail -f run.log          # progress; results in ./output/ (tickets.csv, verification.csv, .xlsx, report.txt, result.json)
```
Or directly: `pip install -r requirements.txt && python app.py --help`.
Options: `--time` total seconds, `--workers`, `--gap 0.05` (stop early, no proof), `--no-exact` (heuristic only, fastest), `--exact-limit`.

Solver settings for the Streamlit UI are fixed in `config.py` (users only see them). Streamlit (short jobs): `streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port 8501`

## Limits
Enumeration limit is 6,000,000 tickets/results. Exact final verification costs (results x tickets) popcounts,
so very large games take long even for the heuristic path.
