"""Fast greedy cover + redundancy pruning. Produces a feasible ticket set quickly (upper bound / warm start).
Feasibility is always confirmed by the exact verifier afterwards."""
import numpy as np

from .core import popcount, pmap
from . import core as _core

_CHUNK = 4_000_000


def _gain_all(p, tm, rm, needpos):
    T, S = len(tm), len(rm)
    step = max(1, min(_CHUNK // S, -(-T // (_core.THREADS * 2))))

    def work(s0):
        ov = popcount(tm[s0:s0 + step, None] & rm[None, :])
        g = np.zeros(ov.shape[0], dtype=np.int32)
        for j, k in enumerate(p.ks):
            g += ((ov == k) & needpos[:, j][None, :]).sum(axis=1, dtype=np.int32)
        return g

    return np.concatenate(pmap(work, range(0, T, step)))


def _gain_one(p, tmask, rm, needpos):
    ov = popcount(tmask & rm)
    g = 0
    for j, k in enumerate(p.ks):
        g += int(((ov == k) & needpos[:, j]).sum())
    return g


def greedy_cover(p, start=(), rng=None, sub_size=600, pass_ops=20_000_000, log=None):
    """Lazy-greedy multi-cover. Returns list of ticket indices satisfying ALL targets for ALL results.
    Each pass scores a random candidate subset (<= pass_ops/sub_size tickets) against the most deficient
    results, so cost per pass stays bounded even for huge games. Exactness is restored by the verifier."""
    rng = rng or np.random.default_rng(0)
    T, nk = p.n_tickets, len(p.ks)
    sel = list(start)
    is_sel = np.zeros(T, dtype=bool)
    if sel:
        is_sel[sel] = True
        deficit = np.maximum(p.reqs[None, :] - p.target_counts(p.tmasks[sel]), 0).astype(np.int32)
    else:
        deficit = np.broadcast_to(p.reqs[None, :], (p.n_results, nk)).astype(np.int32).copy()

    while True:
        tot = deficit.sum(axis=1)
        viol = np.flatnonzero(tot)
        if viol.size == 0:
            return sel
        if viol.size > sub_size:
            score = tot[viol] + rng.random(viol.size)
            sub = viol[np.argpartition(-score, sub_size - 1)[:sub_size]]
        else:
            sub = viol
        rm = p.rmasks[sub]
        need = deficit[sub].copy()
        needpos = need > 0
        cap = max(2000, pass_ops // len(sub))
        if cap >= T:
            cand = np.arange(T)
        else:
            cand = rng.choice(T, size=cap, replace=False)
        cand = cand[~is_sel[cand]]
        if cand.size == 0:
            cand = np.flatnonzero(~is_sel)
        ctm = p.tmasks[cand]
        gain = _gain_all(p, ctm, rm, needpos)
        stamp = np.zeros(len(cand), dtype=np.int32)
        picks, new = 0, []
        while True:
            ci = int(np.argmax(gain))
            if gain[ci] <= 0:
                break
            c = int(cand[ci])
            if stamp[ci] != picks:                      # lazy re-evaluation
                gain[ci] = _gain_one(p, p.tmasks[c], rm, needpos)
                stamp[ci] = picks
                continue
            ov = popcount(p.tmasks[c] & rm)
            for j, k in enumerate(p.ks):
                need[:, j] -= ((ov == k) & (need[:, j] > 0))
            needpos = need > 0
            gain[ci] = -1
            is_sel[c] = True
            sel.append(c)
            new.append(c)
            picks += 1
            if not needpos.any():
                break
        if not new:
            raise RuntimeError("Greedy stalled (should be impossible for a feasible game).")
        for c in new:                                  # update global deficits (sparse, no full scan)
            for j, k in enumerate(p.ks):
                idx = p.exact_overlap_results(p.tmasks[c], k)
                d = deficit[idx, j]
                deficit[idx, j] = d - (d > 0)
        if log:
            log(f"   greedy: {len(sel)} tickets, {int((deficit.sum(axis=1) > 0).sum()):,} results still short")


def prune(p, sel, rng=None):
    """Drop redundant tickets while keeping every target satisfied for every result (sparse: touches only the
    results each ticket actually affects)."""
    rng = rng or np.random.default_rng(1)
    sel = list(sel)
    if not sel:
        return sel
    cnt = p.target_counts(p.tmasks[sel]).astype(np.int32)
    keep = np.ones(len(sel), dtype=bool)
    for pos in rng.permutation(len(sel)):
        tm = p.tmasks[sel[pos]]
        idxs, ok = [], True
        for j, k in enumerate(p.ks):
            idx = p.exact_overlap_results(tm, k)
            if (cnt[idx, j] - 1 < p.reqs[j]).any():
                ok = False
                break
            idxs.append(idx)
        if ok:
            for j, idx in enumerate(idxs):
                cnt[idx, j] -= 1
            keep[pos] = False
    return [s for s, kp in zip(sel, keep) if kp]


def improve_lns(p, sel, rng, deadline, log=None, destroy_frac=0.08, patience=4):
    """Large-neighbourhood search: drop a random slice of tickets, greedily repair, prune, keep if not worse.
    Stops after `patience` consecutive non-improving rounds or at the deadline. Result is always feasible."""
    import time
    best, fails, it = list(sel), 0, 0
    while time.time() < deadline and fails < patience and len(best) > 1:
        it += 1
        k = max(1, int(len(best) * destroy_frac))
        keep = [best[i] for i in rng.permutation(len(best))[k:]]
        cand = prune(p, greedy_cover(p, start=keep, rng=rng), rng)
        if len(cand) < len(best):
            best, fails = cand, 0
            if log:
                log(f"   LNS round {it}: improved -> {len(best)} tickets")
        else:
            fails += 1
    return best
