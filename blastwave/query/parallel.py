"""
Helper for running many BOOM queries in parallel, rather than one at a time.

The design follows the penquins package: queries are IO-bound, so a pool of
threads is enough to overlap the requests, and threads (rather than processes)
let every query share the client session and its HTTP connection pool.
"""

import logging
from multiprocessing.pool import ThreadPool
from typing import Callable, Iterator, Sequence, TypeVar

from tqdm.auto import tqdm

logger = logging.getLogger(__name__)

DEFAULT_N_THREADS = 8

R = TypeVar("R")


def run_parallel(
    funcs: Sequence[Callable[[], R]],
    n_threads: int = DEFAULT_N_THREADS,
    progress: bool = False,
    desc: str | None = None,
) -> list[R]:
    """
    Call a set of zero-argument functions in parallel, using a pool of threads.

    Each function is usually a functools.partial of a client method, so that
    every call can have its own arguments. Results are returned in the order of
    the functions, regardless of the order in which they finish. If a function
    raises, the error propagates and the remaining functions are abandoned.

    :param funcs: Zero-argument functions to call
    :param n_threads: Maximum number of threads to use
    :param progress: Whether to show a progress bar
    :param desc: Description for the progress bar
    :return: List of results, in the order of the functions
    """
    if n_threads < 1:
        raise ValueError(f"n_threads must be at least one, got {n_threads}")

    if len(funcs) == 0:
        return []

    # No point having more threads than functions to call
    n_threads = min(len(funcs), n_threads)

    logger.debug(f"Calling {len(funcs)} functions on {n_threads} threads")

    with ThreadPool(processes=n_threads) as pool:
        results: Iterator[R] = pool.imap(lambda func: func(), funcs)
        if progress:
            results = tqdm(results, total=len(funcs), desc=desc)
        return list(results)
