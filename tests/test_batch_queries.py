"""
Unit tests for the parallel/batch query methods of the clients, mocking out
the network layer so these tests need no BOOM credentials or connectivity.
"""

# pylint: disable=missing-function-docstring,protected-access,unused-argument

import threading
import unittest
from typing import Callable
from unittest import mock

from blastwave.models import Source
from blastwave.query import LSSTClient, ZTFClient
from blastwave.query.boom import BOOM_POOL_MAXSIZE, BOOMClient


def fake_source(object_id, **kwargs) -> Source:
    return Source(
        objectid=str(object_id),
        jd=2460100.0,
        ra=150.0,
        dec=20.0,
        offset=None,
        host_origin=None,
        photometry=[],
    )


def concurrency_counter(hold: float = 0.02) -> tuple[Callable, dict]:
    """
    Make a stand-in call which holds briefly, alongside the tally it keeps of
    the most calls which were ever in flight at once
    """
    tally = {"in_flight": 0, "max_in_flight": 0}
    lock = threading.Lock()

    def counter(*args, **kwargs):
        with lock:
            tally["in_flight"] += 1
            tally["max_in_flight"] = max(tally["max_in_flight"], tally["in_flight"])
        try:
            threading.Event().wait(hold)
            return mock.Mock()
        finally:
            with lock:
                tally["in_flight"] -= 1

    return counter, tally


class TestValidateNThreads(unittest.TestCase):
    """
    Tests for BOOMClient thread count handling
    """

    def test_default_client_uses_multiple_threads(self):
        self.assertGreater(BOOMClient().n_threads, 1)

    def test_thread_count_is_capped_at_pool_size(self):
        with self.assertLogs("blastwave.query.boom", level="WARNING"):
            client = BOOMClient(n_threads=BOOM_POOL_MAXSIZE + 10)
        self.assertEqual(client.n_threads, BOOM_POOL_MAXSIZE)

    def test_zero_threads_raises(self):
        with self.assertRaises(ValueError):
            BOOMClient(n_threads=0)

    def test_resolve_falls_back_to_client_default(self):
        client = BOOMClient(n_threads=3)
        self.assertEqual(client._resolve_n_threads(None), 3)
        self.assertEqual(client._resolve_n_threads(2), 2)


class TestBatchQuery(unittest.TestCase):
    """
    Tests for BOOMClient.batch_query
    """

    def test_runs_every_query_in_order(self):
        client = BOOMClient(n_threads=4)
        queries = [{"catalog_name": "CatWISE2020", "limit": i} for i in range(1, 6)]

        with mock.patch.object(
            client, "query", side_effect=lambda q: [{"limit": q["limit"]}]
        ) as query:
            res = client.batch_query(queries)

        self.assertEqual(query.call_count, 5)
        self.assertEqual(res, [[{"limit": i}] for i in range(1, 6)])

    def test_no_queries_returns_no_results(self):
        client = BOOMClient()
        with mock.patch.object(client, "query") as query:
            self.assertEqual(client.batch_query([]), [])
        query.assert_not_called()

    def test_error_is_raised_by_default(self):
        client = BOOMClient(n_threads=2)
        with mock.patch.object(client, "query", side_effect=ValueError("bad query")):
            with self.assertRaises(ValueError):
                client.batch_query([{"catalog_name": "a"}, {"catalog_name": "b"}])

    def test_skip_errors_returns_none_for_failures(self):
        client = BOOMClient(n_threads=2)

        def fake_query(query):
            if query["catalog_name"] == "bad":
                raise ValueError("bad query")
            return [{"ok": True}]

        with mock.patch.object(client, "query", side_effect=fake_query):
            with self.assertLogs("blastwave.query.parallel", level="ERROR"):
                res = client.batch_query(
                    [
                        {"catalog_name": "good"},
                        {"catalog_name": "bad"},
                        {"catalog_name": "good"},
                    ],
                    skip_errors=True,
                )

        self.assertEqual(res, [[{"ok": True}], None, [{"ok": True}]])

    def test_queries_are_sent_concurrently(self):
        client = BOOMClient(n_threads=4)
        counter, tally = concurrency_counter()

        with mock.patch.object(client, "query", side_effect=counter):
            client.batch_query([{"catalog_name": "CatWISE2020"}] * 4)

        self.assertGreater(tally["max_in_flight"], 1)


class TestBatchCount(unittest.TestCase):
    """
    Tests for BOOMClient.batch_count
    """

    def test_counts_every_query_in_order(self):
        client = BOOMClient(n_threads=3)
        with mock.patch.object(
            client, "count", side_effect=lambda q: q["limit"]
        ) as count:
            res = client.batch_count([{"limit": 1}, {"limit": 2}, {"limit": 3}])

        self.assertEqual(count.call_count, 3)
        self.assertEqual(res, [1, 2, 3])

    def test_skip_errors_returns_none_for_failures(self):
        client = BOOMClient(n_threads=2)
        with mock.patch.object(client, "count", side_effect=ValueError("nope")):
            with self.assertLogs("blastwave.query.parallel", level="ERROR"):
                res = client.batch_count([{"catalog_name": "a"}], skip_errors=True)
        self.assertEqual(res, [None])


class TestBatchConeSearch(unittest.TestCase):
    """
    Tests for BOOMClient.batch_cone_search
    """

    def test_one_search_per_position(self):
        client = BOOMClient(n_threads=4)
        coordinates = [(191.6182623, -1.7184336), (150.0, 20.0)]

        with mock.patch.object(
            client, "cone_search", side_effect=lambda ra, dec, **kwargs: [(ra, dec)]
        ) as cone_search:
            res = client.batch_cone_search(
                coordinates, radius_arcsec=20.0, catalog="CatWISE2020", limit=None
            )

        self.assertEqual(res, [[coordinates[0]], [coordinates[1]]])
        _, kwargs = cone_search.call_args
        self.assertEqual(kwargs["catalog"], "CatWISE2020")
        self.assertEqual(kwargs["radius_arcsec"], 20.0)
        self.assertIsNone(kwargs["limit"])

    def test_skip_errors_returns_none_for_failures(self):
        client = BOOMClient(n_threads=2)

        def fake_cone_search(ra, dec, **kwargs):
            if dec < 0:
                raise ValueError("bad position")
            return [{"ra": ra, "dec": dec}]

        with mock.patch.object(client, "cone_search", side_effect=fake_cone_search):
            with self.assertLogs("blastwave.query.parallel", level="ERROR"):
                res = client.batch_cone_search(
                    [(150.0, 20.0), (150.0, -20.0)],
                    catalog="CatWISE2020",
                    skip_errors=True,
                )

        self.assertEqual(res, [[{"ra": 150.0, "dec": 20.0}], None])

    def test_no_positions_returns_no_results(self):
        client = BOOMClient()
        with mock.patch.object(client, "cone_search") as cone_search:
            self.assertEqual(client.batch_cone_search([], catalog="a"), [])
        cone_search.assert_not_called()


class TestThreadSafeSetUp(unittest.TestCase):
    """
    Tests that the lazily set up session, headers and catalogs are only
    created once, even when many threads start querying at the same time.
    """

    @staticmethod
    def call_from_threads(func, n_threads: int = 8):
        barrier = threading.Barrier(n_threads, timeout=10)

        def target():
            barrier.wait()
            func()

        threads = [threading.Thread(target=target) for _ in range(n_threads)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

    def test_token_is_only_requested_once(self):
        client = BOOMClient()
        with mock.patch.object(
            client, "_get_boom_token", return_value="TOKEN"
        ) as get_token:
            self.call_from_threads(client.get_session_headers)

        get_token.assert_called_once()

    def test_session_is_only_set_up_once(self):
        client = BOOMClient()
        with mock.patch.object(
            client, "set_up_session", side_effect=BOOMClient.set_up_session
        ) as set_up:
            self.call_from_threads(client.get_session)

        set_up.assert_called_once()

    def test_catalogs_are_only_requested_once(self):
        client = BOOMClient()
        with mock.patch.object(client, "api") as api:
            api.return_value.json.return_value = {"data": [{"name": "CatWISE2020"}]}
            self.call_from_threads(client.get_catalogs)

        api.assert_called_once()
        self.assertEqual(client.get_catalogs(), ["CatWISE2020"])


class TestRequestsInFlight(unittest.TestCase):
    """
    Tests that the client never has more requests in flight than its
    connection pool can hold.
    """

    def test_api_calls_are_capped_by_the_semaphore(self):
        client = BOOMClient()
        counter, tally = concurrency_counter()
        client._session = mock.Mock(post=counter)
        client._session_headers = {"Authorization": "Bearer TOKEN"}
        client._request_semaphore = threading.BoundedSemaphore(2)

        threads = [
            threading.Thread(target=client.api, args=("post", "queries/find"))
            for _ in range(6)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(tally["max_in_flight"], 2)


class TestBatchGetFullData(unittest.TestCase):
    """
    Tests for AlertClient.batch_get_full_data
    """

    def test_one_call_per_object_in_order(self):
        client = ZTFClient(n_threads=4)
        object_ids = ["ZTF1", "ZTF2", "ZTF3"]

        with mock.patch.object(
            client,
            "get_full_data",
            side_effect=lambda object_id, **kwargs: {"objectId": object_id},
        ) as get_full_data:
            res = client.batch_get_full_data(object_ids)

        self.assertEqual(get_full_data.call_count, 3)
        self.assertEqual(res, [{"objectId": name} for name in object_ids])

    def test_projections_are_passed_through(self):
        client = LSSTClient()
        with mock.patch.object(client, "get_full_data", return_value={}) as get_full:
            client.batch_get_full_data(
                ["L1"],
                catalog="LSST_alerts",
                alert_projection={"candidate": 1},
                aux_projection={"aliases": 1},
                trim=True,
            )

        _, kwargs = get_full.call_args
        self.assertEqual(kwargs["catalog"], "LSST_alerts")
        self.assertEqual(kwargs["alert_projection"], {"candidate": 1})
        self.assertEqual(kwargs["aux_projection"], {"aliases": 1})
        self.assertTrue(kwargs["trim"])


class TestBatchGetSource(unittest.TestCase):
    """
    Tests for AlertClient.batch_get_source
    """

    def test_one_source_per_object_in_order(self):
        client = ZTFClient(n_threads=4)
        object_ids = ["ZTF1", "ZTF2", "ZTF3", "ZTF4"]

        with mock.patch.object(client, "get_source", side_effect=fake_source):
            sources = client.batch_get_source(object_ids)

        self.assertEqual([x.objectid for x in sources], object_ids)

    def test_skip_errors_returns_none_for_failures(self):
        client = ZTFClient(n_threads=2)

        def fake_get_source(object_id, **kwargs):
            if object_id == "bad":
                raise KeyError("missing alert")
            return fake_source(object_id)

        with mock.patch.object(client, "get_source", side_effect=fake_get_source):
            with self.assertLogs("blastwave.query.parallel", level="ERROR"):
                sources = client.batch_get_source(["ZTF1", "bad"], skip_errors=True)

        self.assertEqual(sources[0].objectid, "ZTF1")
        self.assertIsNone(sources[1])

    def test_sources_are_fetched_concurrently(self):
        client = ZTFClient(n_threads=4)
        counter, tally = concurrency_counter()

        with mock.patch.object(client, "get_source", side_effect=counter):
            client.batch_get_source(["ZTF1", "ZTF2", "ZTF3", "ZTF4"])

        self.assertGreater(tally["max_in_flight"], 1)


if __name__ == "__main__":
    unittest.main()
