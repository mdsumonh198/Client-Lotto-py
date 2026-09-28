"""Incremental exact CP-SAT model (constraint generation). The model object persists across rounds,
new result-constraints are appended (no rebuild), and the best known solution is passed as a hint."""
try:
    from ortools.sat.python import cp_model
    HAS_ORTOOLS = True
except ImportError:            # pragma: no cover
    cp_model = None
    HAS_ORTOOLS = False

import numpy as np

from .core import popcount

_INF = 2 ** 62


class IncrementalModel:
    def __init__(self, problem):
        self.p = problem
        T = problem.n_tickets
        self.model = cp_model.CpModel()
        self.x = [self.model.NewBoolVar("") for _ in range(T)]
        obj = self.model.Proto().objective            # minimise number of tickets
        obj.vars.extend(range(T))
        obj.coeffs.extend([1] * T)
        self.added = set()

    def add_result(self, ridx):
        ridx = int(ridx)
        if ridx in self.added:
            return False
        self.added.add(ridx)
        p = self.p
        ov = popcount(p.tmasks & p.rmasks[ridx])
        for j, k in enumerate(p.ks):
            idx = np.flatnonzero(ov == k)
            ct = self.model.Proto().constraints.add()
            ct.linear.vars.extend(idx.tolist())
            ct.linear.coeffs.extend([1] * len(idx))
            ct.linear.domain.extend([int(p.reqs[j]), _INF])
        return True

    def solve(self, hint_sel, time_limit, workers, gap=0.0, verbose=False):
        T = self.p.n_tickets
        self.model.ClearHints()
        vals = [0] * T
        for i in hint_sel:
            vals[i] = 1
        self.model.Proto().solution_hint.vars.extend(range(T))
        self.model.Proto().solution_hint.values.extend(vals)

        solver = cp_model.CpSolver()
        prm = solver.parameters
        prm.max_time_in_seconds = max(1.0, float(time_limit))
        prm.num_workers = int(workers)
        prm.log_search_progress = bool(verbose)
        if gap and gap > 0:
            prm.relative_gap_limit = float(gap)
        code = solver.Solve(self.model)
        names = {cp_model.OPTIMAL: "OPTIMAL", cp_model.FEASIBLE: "FEASIBLE", cp_model.INFEASIBLE: "INFEASIBLE",
                 cp_model.MODEL_INVALID: "MODEL_INVALID", cp_model.UNKNOWN: "UNKNOWN"}
        status = names.get(code, str(code))
        cand, bound = None, None
        if code in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            cand = [i for i in range(T) if solver.BooleanValue(self.x[i])]
            bound = solver.BestObjectiveBound()
        return status, cand, bound
