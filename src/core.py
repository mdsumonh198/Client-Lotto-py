"""Core utilities: bit-mask combinations, vectorised popcount, Problem definition."""
import os
from concurrent.futures import ThreadPoolExecutor
from itertools import combinations
from math import comb

import numpy as np

THREADS = os.cpu_count() or 1      # NumPy releases the GIL on big array ops, so threads scale


def set_threads(n):
    global THREADS
    THREADS = max(1, int(n or (os.cpu_count() or 1)))


def pmap(fn, items):
    """Ordered parallel map over items using THREADS threads."""
    items = list(items)
    if THREADS <= 1 or len(items) <= 1:
        return [fn(x) for x in items]
    with ThreadPoolExecutor(THREADS) as ex:
        return list(ex.map(fn, items))


# ----------------------------------------------------------------------------
# Backward-compatible helpers
# ----------------------------------------------------------------------------
def validate_game(number_from: int, number_to: int, ticket_size: int, result_size: int):
    if number_from < 0 or number_to > 40 or number_from > number_to:
        raise ValueError("Number range must satisfy 0 <= from <= to <= 40")
    pool_size = number_to - number_from + 1
    if not (1 <= ticket_size <= pool_size):
        raise ValueError("Invalid ticket size")
    if not (1 <= result_size <= pool_size):
        raise ValueError("Invalid result size")
    return pool_size


def all_combinations(number_from: int, number_to: int, k: int):
    return list(combinations(range(number_from, number_to + 1), k))


def to_mask(nums):
    mask = 0
    for n in nums:
        mask |= 1 << n
    return mask


def exact_match_count(mask_a: int, mask_b: int) -> int:
    return (mask_a & mask_b).bit_count()


def combination_count(number_from: int, number_to: int, k: int) -> int:
    n = number_to - number_from + 1
    return comb(n, k)


def _C(n: int, k: int) -> int:
    return comb(n, k) if 0 <= k <= n else 0


# ----------------------------------------------------------------------------
# Fast NumPy primitives
# ----------------------------------------------------------------------------
if hasattr(np, "bitwise_count"):          # NumPy >= 2.0 (hardware popcount)
    def popcount(a):
        return np.bitwise_count(a)
else:                                       # fallback for old NumPy
    _T16 = np.array([bin(i).count("1") for i in range(1 << 16)], dtype=np.uint8)

    def popcount(a):
        a = np.asarray(a, dtype=np.uint64)
        m = np.uint64(0xFFFF)
        return (
            _T16[(a & m).astype(np.intp)]
            + _T16[((a >> np.uint64(16)) & m).astype(np.intp)]
            + _T16[((a >> np.uint64(32)) & m).astype(np.intp)]
            + _T16[((a >> np.uint64(48)) & m).astype(np.intp)]
        )


def combo_masks(n: int, k: int) -> np.ndarray:
    """All C(n,k) bit-masks (uint64) with exactly k bits set among bits 0..n-1. Fully vectorised."""
    if k == 0:
        return np.zeros(1, dtype=np.uint64)
    if k > n:
        return np.empty(0, dtype=np.uint64)
    dp = [np.zeros(1, dtype=np.uint64)] + [np.empty(0, dtype=np.uint64) for _ in range(k)]
    for j in range(n):
        bit = np.uint64(1) << np.uint64(j)
        for i in range(min(j + 1, k), 0, -1):
            dp[i] = np.concatenate([dp[i], dp[i - 1] | bit])
    return dp[k]


def mask_to_numbers(mask, offset: int = 0):
    mask = int(mask)
    out, i = [], 0
    while mask:
        if mask & 1:
            out.append(offset + i)
        mask >>= 1
        i += 1
    return tuple(out)


def overlap_counts(rmasks: np.ndarray, tmasks: np.ndarray, k1: int, chunk_elems: int = 2_000_000) -> np.ndarray:
    """
    For every result, count how many tickets share EXACTLY k numbers, for k = 0..k1-1.
    Returns int32 array of shape [len(rmasks), k1].  Exact - no sampling. Multi-threaded over result chunks.
    """
    R, T = len(rmasks), len(tmasks)
    out = np.zeros((R, k1), dtype=np.int32)
    if T == 0 or R == 0:
        return out
    step = max(1, min(chunk_elems // T, -(-R // (THREADS * 2))))

    def work(s0):
        rm = rmasks[s0:s0 + step]
        ov = popcount(rm[:, None] & tmasks[None, :]).astype(np.int64)
        ov += (np.arange(len(rm), dtype=np.int64) * k1)[:, None]
        out[s0:s0 + step] = np.bincount(ov.ravel(), minlength=len(rm) * k1).reshape(len(rm), k1)

    pmap(work, range(0, R, step))
    return out


# ----------------------------------------------------------------------------
# Problem definition
# ----------------------------------------------------------------------------
class Problem:
    """Holds every candidate ticket and every possible result as uint64 masks (bit i == number_from + i)."""

    def __init__(self, number_from, number_to, ticket_size, result_size, targets, max_enumeration=6_000_000):
        self.number_from = int(number_from)
        self.number_to = int(number_to)
        self.N = validate_game(self.number_from, self.number_to, int(ticket_size), int(result_size))
        self.t = int(ticket_size)
        self.s = int(result_size)
        self.k1 = self.s + 1
        clean = {}
        for k, v in (targets or {}).items():
            k, v = int(k), int(v)
            if k < 0 or k > self.s:
                raise ValueError(f"Exact-match level {k} is outside 0..{self.s}")
            if v > 0:
                clean[k] = v
        self.targets = clean
        self.ks = sorted(clean)
        self.reqs = np.array([clean[k] for k in self.ks], dtype=np.int32)

        n_t, n_r = _C(self.N, self.t), _C(self.N, self.s)
        if max(n_t, n_r) > max_enumeration:
            raise ValueError(
                f"Game too large to enumerate ({n_t:,} tickets / {n_r:,} results). "
                f"Limit is {max_enumeration:,}. Use a smaller range or size."
            )
        self.tmasks = combo_masks(self.N, self.t)
        self.rmasks = self.tmasks if self.t == self.s else combo_masks(self.N, self.s)
        self._rorder = np.argsort(self.rmasks, kind="stable")
        self._rsorted = self.rmasks[self._rorder]
        self._ci_cache = {}
        self._bitvals = [np.uint64(1) << np.uint64(i) for i in range(self.N)]
        self.terms_per_ticket = sum(_C(self.t, k) * _C(self.N - self.t, self.s - k) for k in self.ks)

    # -- sizes
    @property
    def n_tickets(self):
        return len(self.tmasks)

    @property
    def n_results(self):
        return len(self.rmasks)

    # -- conversions
    def numbers(self, mask):
        return mask_to_numbers(mask, self.number_from)

    def tickets_as_numbers(self, idx):
        return sorted(self.numbers(self.tmasks[i]) for i in idx)

    # -- sparse lookup: indices of results sharing EXACTLY k numbers with a ticket (no scan of all results)
    def _ci(self, n, k):
        key = (n, k)
        if key not in self._ci_cache:
            if k == 0:
                self._ci_cache[key] = np.zeros((1, 0), dtype=np.intp)
            else:
                self._ci_cache[key] = np.array(list(combinations(range(n), k)), dtype=np.intp).reshape(-1, k)
        return self._ci_cache[key]

    def exact_overlap_results(self, tmask, k):
        tmask = int(tmask)
        if _C(self.t, k) * _C(self.N - self.t, self.s - k) > self.n_results // 8:   # dense is cheaper
            return np.flatnonzero(popcount(self.rmasks & np.uint64(tmask)) == k)
        inside = np.array([self._bitvals[i] for i in range(self.N) if (tmask >> i) & 1], dtype=np.uint64)
        outside = np.array([self._bitvals[i] for i in range(self.N) if not (tmask >> i) & 1], dtype=np.uint64)
        a = inside[self._ci(len(inside), k)].sum(axis=1, dtype=np.uint64)
        b = outside[self._ci(len(outside), self.s - k)].sum(axis=1, dtype=np.uint64)
        masks = (a[:, None] | b[None, :]).ravel()
        return self._rorder[np.searchsorted(self._rsorted, masks)]

    # -- counts of exact-k matches restricted to the target levels: [R, len(ks)]
    def target_counts(self, ticket_masks):
        ticket_masks = np.asarray(ticket_masks, dtype=np.uint64)
        if self.terms_per_ticket <= self.n_results // 4:
            cnt = np.zeros((self.n_results, len(self.ks)), dtype=np.int32)
            for tm in ticket_masks:
                for j, k in enumerate(self.ks):
                    cnt[self.exact_overlap_results(tm, k), j] += 1
            return cnt
        return overlap_counts(self.rmasks, ticket_masks, self.k1)[:, self.ks]

    # -- math facts (valid for every game by symmetry)
    def infeasible_reason(self):
        """A result has C(s,k)*C(N-s,t-k) tickets with exactly-k overlap. If that is < minimum -> impossible."""
        for k, m in self.targets.items():
            avail = _C(self.s, k) * _C(self.N - self.s, self.t - k)
            if avail < m:
                return (f"Exact-{k} >= {m} is impossible: only {avail} distinct tickets can "
                        f"match a result in exactly {k} numbers.")
        return None

    def counting_lower_bound(self):
        """Double-counting bound:  |S| * C(t,k)*C(N-t,s-k)  >=  m * C(N,s).  Mathematically valid lower bound."""
        R = _C(self.N, self.s)
        best = 0
        for k, m in self.targets.items():
            per_ticket = _C(self.t, k) * _C(self.N - self.t, self.s - k)
            if per_ticket > 0:
                best = max(best, -(-m * R // per_ticket))
            best = max(best, m)
        return best
