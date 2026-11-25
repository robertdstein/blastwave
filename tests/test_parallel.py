"""
Unit tests for the parallel helpers used to run queries in a thread pool.
"""

# pylint: disable=missing-function-docstring

import threading
import time
import unittest

from blastwave.query.parallel import (
    DEFAULT_N_THREADS,
    run_parallel,
    run_parallel_funcs,
    tolerate_errors,
)


class TestRunParallel(unittest.TestCase):
    """
    Tests for run_parallel
    """

    def test_results_are_in_task_order(self):
        # Later tasks finish first, so the order has to come from the input
        def slow_for_small_x(x):
            time.sleep(0.05 * (5 - x))
            return x * 2

        res = run_parallel(slow_for_small_x, range(5), n_threads=5)
        self.assertEqual(res, [0, 2, 4, 6, 8])

    def test_tasks_run_concurrently(self):
        # The barrier only releases if all four tasks are in flight at once
        barrier = threading.Barrier(4, timeout=10)
        res = run_parallel(lambda x: barrier.wait() >= 0, range(4), n_threads=4)
        self.assertEqual(res, [True] * 4)

    def test_no_tasks_returns_no_results(self):
        self.assertEqual(run_parallel(lambda x: x, []), [])

    def test_single_thread_still_runs_every_task(self):
        res = run_parallel(lambda x: x + 1, [1, 2, 3], n_threads=1)
        self.assertEqual(res, [2, 3, 4])

    def test_zero_threads_raises(self):
        with self.assertRaises(ValueError):
            run_parallel(lambda x: x, [1], n_threads=0)

    def test_error_in_task_is_raised(self):
        with self.assertRaises(ZeroDivisionError):
            run_parallel(lambda x: 1 / x, [1, 0, 2], n_threads=3)

    def test_progress_bar_does_not_change_results(self):
        res = run_parallel(lambda x: x, [1, 2, 3], n_threads=2, progress=True)
        self.assertEqual(res, [1, 2, 3])

    def test_consumes_iterators(self):
        res = run_parallel(lambda x: x, iter([1, 2, 3]), n_threads=2)
        self.assertEqual(res, [1, 2, 3])


class TestRunParallelFuncs(unittest.TestCase):
    """
    Tests for run_parallel_funcs
    """

    def test_each_function_is_called(self):
        res = run_parallel_funcs([lambda: "a", lambda: "b", lambda: "c"], n_threads=3)
        self.assertEqual(res, ["a", "b", "c"])

    def test_no_funcs_returns_no_results(self):
        self.assertEqual(run_parallel_funcs([]), [])


class TestTolerateErrors(unittest.TestCase):
    """
    Tests for tolerate_errors
    """

    def test_failed_tasks_become_none(self):
        with self.assertLogs("blastwave.query.parallel", level="ERROR"):
            res = run_parallel(tolerate_errors(lambda x: 1 / x), [1, 0, 4], n_threads=3)
        self.assertEqual(res, [1.0, None, 0.25])

    def test_successful_task_is_unchanged(self):
        self.assertEqual(tolerate_errors(lambda x: x * 2)(3), 6)

    def test_works_for_zero_argument_functions(self):
        def fail():
            raise RuntimeError("no luck")

        with self.assertLogs("blastwave.query.parallel", level="ERROR"):
            res = run_parallel_funcs([tolerate_errors(fail), lambda: 1])
        self.assertEqual(res, [None, 1])


class TestDefaults(unittest.TestCase):
    """
    Tests for the default thread count
    """

    def test_default_is_more_than_one_thread(self):
        self.assertGreater(DEFAULT_N_THREADS, 1)


if __name__ == "__main__":
    unittest.main()
