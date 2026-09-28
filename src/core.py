from itertools import combinations
from math import comb


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
