"""
Unit tests for run_parallel, which runs queries in a thread pool.
"""

# pylint: disable=missing-function-docstring

import threading
import time
import unittest
from functools import partial

from blastwave.query.parallel import run_parallel


class TestRunParallel(unittest.TestCase):
    """
    Tests for run_parallel
    """

    def test_results_are_in_func_order(self):
        # Later funcs finish first, so the order has to come from the input
        def slow_for_small_x(x):
            time.sleep(0.05 * (5 - x))
            return x * 2

        res = run_parallel(
            [partial(slow_for_small_x, x) for x in range(5)], n_threads=5
        )
        self.assertEqual(res, [0, 2, 4, 6, 8])

    def test_funcs_run_concurrently(self):
        # The barrier only releases if all four funcs are in flight at once
        barrier = threading.Barrier(4, timeout=10)
        res = run_parallel([lambda: barrier.wait() >= 0] * 4, n_threads=4)
        self.assertEqual(res, [True] * 4)

    def test_no_funcs_returns_no_results(self):
        self.assertEqual(run_parallel([]), [])

    def test_single_thread_still_calls_every_func(self):
        res = run_parallel([partial(int, x) for x in "123"], n_threads=1)
        self.assertEqual(res, [1, 2, 3])

    def test_zero_threads_raises(self):
        with self.assertRaises(ValueError):
            run_parallel([int], n_threads=0)

    def test_error_in_func_is_raised(self):
        with self.assertRaises(ZeroDivisionError):
            run_parallel([partial(lambda x: 1 / x, x) for x in [1, 0, 2]], n_threads=3)

    def test_progress_bar_does_not_change_results(self):
        res = run_parallel([partial(int, x) for x in "123"], progress=True)
        self.assertEqual(res, [1, 2, 3])
