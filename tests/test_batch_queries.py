"""
Unit tests for the batch query methods of the clients, mocking out the
network layer so these tests need no BOOM credentials or connectivity.
"""

# pylint: disable=missing-function-docstring,protected-access,unused-argument

import threading
import unittest
from unittest import mock

import requests

from blastwave.errors import BOOMCredentialsError
from blastwave.models import Source
from blastwave.query import ZTFClient
from blastwave.query.boom import BOOMClient


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

    def test_queries_are_sent_concurrently(self):
        # The barrier only releases if all four queries are in flight at once
        client = BOOMClient(n_threads=4)
        barrier = threading.Barrier(4, timeout=10)

        with mock.patch.object(client, "query", side_effect=lambda q: barrier.wait()):
            res = client.batch_query([{"catalog_name": "CatWISE2020"}] * 4)

        self.assertEqual(sorted(res), [0, 1, 2, 3])

    def test_error_is_raised_by_default(self):
        client = BOOMClient(n_threads=2)
        with mock.patch.object(client, "query", side_effect=requests.Timeout("slow")):
            with self.assertRaises(requests.Timeout):
                client.batch_query([{"catalog_name": "a"}, {"catalog_name": "b"}])

    def test_skip_errors_returns_none_for_failures(self):
        client = BOOMClient(n_threads=2)

        def fake_query(query):
            if query["catalog_name"] == "bad":
                raise requests.HTTPError("500 Server Error")
            return [{"ok": True}]

        with mock.patch.object(client, "query", side_effect=fake_query):
            with self.assertLogs("blastwave.query.boom", level="ERROR"):
                res = client.batch_query(
                    [
                        {"catalog_name": "good"},
                        {"catalog_name": "bad"},
                        {"catalog_name": "good"},
                    ],
                    skip_errors=True,
                )

        self.assertEqual(res, [[{"ok": True}], None, [{"ok": True}]])

    def test_skip_errors_still_raises_a_batch_wide_error(self):
        client = BOOMClient(n_threads=2)
        with mock.patch.object(
            client, "query", side_effect=BOOMCredentialsError("no token")
        ):
            with self.assertRaises(BOOMCredentialsError):
                client.batch_query(
                    [{"catalog_name": "a"}, {"catalog_name": "b"}], skip_errors=True
                )


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
                raise requests.ConnectionError("no route")
            return [{"ra": ra, "dec": dec}]

        with mock.patch.object(client, "cone_search", side_effect=fake_cone_search):
            with self.assertLogs("blastwave.query.boom", level="ERROR"):
                res = client.batch_cone_search(
                    [(150.0, 20.0), (150.0, -20.0)],
                    catalog="CatWISE2020",
                    skip_errors=True,
                )

        self.assertEqual(res, [[{"ra": 150.0, "dec": 20.0}], None])


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

    def test_arguments_are_passed_through(self):
        client = ZTFClient()
        with mock.patch.object(client, "get_source", side_effect=fake_source) as get:
            client.batch_get_source(
                ["ZTF1"], catalog="ZTF_alerts", alert_projection={"candidate": 1}
            )

        _, kwargs = get.call_args
        self.assertEqual(kwargs["catalog"], "ZTF_alerts")
        self.assertEqual(kwargs["alert_projection"], {"candidate": 1})

    def test_skip_errors_returns_none_for_failures(self):
        client = ZTFClient(n_threads=2)

        def fake_get_source(object_id, **kwargs):
            if object_id == "bad":
                raise KeyError("missing alert")
            return fake_source(object_id)

        with mock.patch.object(client, "get_source", side_effect=fake_get_source):
            with self.assertLogs("blastwave.query.boom", level="ERROR"):
                sources = client.batch_get_source(["ZTF1", "bad"], skip_errors=True)

        self.assertEqual(sources[0].objectid, "ZTF1")
        self.assertIsNone(sources[1])

    def test_sources_are_fetched_concurrently(self):
        # The barrier only releases if all four fetches are in flight at once
        client = ZTFClient(n_threads=4)
        barrier = threading.Barrier(4, timeout=10)

        with mock.patch.object(
            client, "get_source", side_effect=lambda o: barrier.wait()
        ):
            res = client.batch_get_source(["ZTF1", "ZTF2", "ZTF3", "ZTF4"])

        self.assertEqual(sorted(res), [0, 1, 2, 3])


if __name__ == "__main__":
    unittest.main()
