"""
Helpers for running many BOOM queries in parallel, rather than one at a time.

The design follows the penquins package: queries are IO-bound, so a pool of
threads is enough to overlap the requests, and threads (rather than processes)
let every query share the client session and its HTTP connection pool.
"""

import logging
from functools import wraps
from multiprocessing.pool import ThreadPool
from typing import Callable, Iterable, Iterator, Sequence, TypeVar

from tqdm.auto import tqdm

logger = logging.getLogger(__name__)

DEFAULT_N_THREADS = 8

T = TypeVar("T")
R = TypeVar("R")


def _call(func: Callable[[], R]) -> R:
    """
    Call a zero-argument function.

    :param func: Function to call
    :return: Result of the function
    """
    return func()


def tolerate_errors(
    func: Callable[..., R],
    errors: type[Exception] | tuple[type[Exception], ...],
) -> Callable[..., R | None]:
    """
    Wrap a function so that the given errors are logged rather than raised,
    with None returned in place of a result.

    This lets the remaining tasks in a batch finish even if one task fails.
    Any error not listed is raised as usual, since it is a sign that the batch
    as a whole is wrong, rather than one task in it.

    :param func: Function to wrap
    :param errors: Error types to tolerate
    :return: Wrapped function, returning None for any call raising those errors
    """

    @wraps(func)
    def wrapper(*args, **kwargs) -> R | None:
        try:
            return func(*args, **kwargs)
        except errors as exc:
            logger.error(f"Task failed, skipping it: {exc}")
            return None

    return wrapper


def _with_progress(
    results: Iterator[R], total: int, progress: bool, desc: str | None
) -> Iterator[R]:
    """
    Optionally wrap an iterator of results in a tqdm progress bar.

    :param results: Iterator of results
    :param total: Total number of results expected
    :param progress: Whether to show a progress bar
    :param desc: Description for the progress bar
    :return: Iterator of results
    """
    if not progress:
        return results
    return tqdm(results, total=total, desc=desc)


def run_parallel(
    func: Callable[[T], R],
    tasks: Iterable[T],
    n_threads: int = DEFAULT_N_THREADS,
    progress: bool = False,
    desc: str | None = None,
) -> list[R]:
    """
    Map a function over a set of tasks, using a pool of threads.

    Results are returned in the same order as the tasks, regardless of the
    order in which they finish. If a task raises, the exception propagates
    and the remaining tasks are abandoned. Use :func:`tolerate_errors` to
    wrap func if that is not what you want.

    :param func: Function to call for each task
    :param tasks: Tasks to pass to the function, one at a time
    :param n_threads: Maximum number of threads to use
    :param progress: Whether to show a progress bar
    :param desc: Description for the progress bar
    :return: List of results, in the order of the tasks
    """
    if n_threads < 1:
        raise ValueError(f"n_threads must be at least one, got {n_threads}")

    task_list = list(tasks)

    if len(task_list) == 0:
        return []

    # No point having more threads than tasks
    n_threads = min(len(task_list), n_threads)

    if n_threads == 1:
        # Avoid the overhead of a pool for a single task
        return list(
            _with_progress(map(func, task_list), len(task_list), progress, desc)
        )

    logger.debug(f"Running {len(task_list)} tasks on {n_threads} threads")

    with ThreadPool(processes=n_threads) as pool:
        return list(
            _with_progress(pool.imap(func, task_list), len(task_list), progress, desc)
        )


def run_parallel_funcs(
    funcs: Sequence[Callable[[], R]],
    n_threads: int = DEFAULT_N_THREADS,
    progress: bool = False,
    desc: str | None = None,
) -> list[R]:
    """
    Run a set of zero-argument functions in parallel, using a pool of threads.

    This is a convenience wrapper around :func:`run_parallel` for cases where
    each task is a different call, e.g. a set of functools.partial objects.

    :param funcs: Zero-argument functions to call
    :param n_threads: Maximum number of threads to use
    :param progress: Whether to show a progress bar
    :param desc: Description for the progress bar
    :return: List of results, in the order of the functions
    """
    return run_parallel(_call, funcs, n_threads=n_threads, progress=progress, desc=desc)
