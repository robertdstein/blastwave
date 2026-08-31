"""
Unit tests for BoomClient query-building logic, mocking out the network layer
so these tests do not require BOOM credentials or connectivity.
"""

# pylint: disable=missing-function-docstring,protected-access

import math
import unittest
from unittest import mock

from blastwave.errors import BOOMCredentialsError
from blastwave.models.query import BOOMQuery
from blastwave.query.boom import BASE_URL, BoomClient


def mock_response(json_data, status_code=200):
    response = mock.Mock()
    response.status_code = status_code
    response.json.return_value = json_data
    if status_code >= 400:
        response.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    else:
        response.raise_for_status.return_value = None
    return response


class TestGetNearSphereDist(unittest.TestCase):
    """
    Tests for BoomClient.get_near_sphere_dist
    """

    def test_matches_independent_computation(self):
        # Independently computed via math.radians, rather than reusing the
        # function's own numpy expression.
        radius_arcsec = 20.0
        expected = math.radians(radius_arcsec / 3600.0) * 6371008.8
        self.assertAlmostEqual(BoomClient.get_near_sphere_dist(radius_arcsec), expected)

    def test_scales_linearly(self):
        self.assertAlmostEqual(
            BoomClient.get_near_sphere_dist(20.0) * 2,
            BoomClient.get_near_sphere_dist(40.0),
        )

    def test_zero_radius_is_zero(self):
        self.assertEqual(BoomClient.get_near_sphere_dist(0.0), 0.0)


class TestResolveCatalog(unittest.TestCase):
    """
    Tests for BoomClient.resolve_catalog
    """

    def test_explicit_catalog_wins(self):
        client = BoomClient()
        self.assertEqual(client.resolve_catalog("milliquas_v8"), "milliquas_v8")

    def test_raises_without_catalog(self):
        client = BoomClient()
        with self.assertRaises(ValueError):
            client.resolve_catalog(None)


class TestApi(unittest.TestCase):
    """
    Tests for BoomClient.api, using a mocked session so no HTTP call is made.
    """

    def setUp(self):
        self.client = BoomClient()
        self.session = mock.Mock()
        self.client._session = self.session
        self.client._session_headers = {"Authorization": "Bearer TOKEN"}

    def test_invalid_method_raises(self):
        with self.assertRaises(ValueError):
            self.client.api("options", "ping")

    def test_missing_endpoint_raises(self):
        with self.assertRaises(ValueError):
            self.client.api("get", None)

    def test_get_passes_data_as_params(self):
        self.client.api("get", "catalogs", data={"a": 1})
        self.session.get.assert_called_once_with(
            f"{BASE_URL}/catalogs",
            params={"a": 1},
            headers={"Authorization": "Bearer TOKEN"},
        )

    def test_post_passes_data_as_json_body(self):
        self.client.api("post", "queries/find", data={"a": 1})
        self.session.post.assert_called_once_with(
            f"{BASE_URL}/queries/find",
            json={"a": 1},
            headers={"Authorization": "Bearer TOKEN"},
        )

    def test_method_is_case_insensitive(self):
        self.client.api("GET", "ping")
        self.session.get.assert_called_once()


class TestSessionHeaders(unittest.TestCase):
    """
    Tests for BoomClient.get_session_headers caching
    """

    def test_token_only_fetched_once(self):
        client = BoomClient()
        with mock.patch.object(
            client, "_get_boom_token", return_value="TOKEN"
        ) as get_token:
            headers1 = client.get_session_headers()
            headers2 = client.get_session_headers()

        get_token.assert_called_once()
        self.assertIs(headers1, headers2)
        self.assertEqual(headers1["Authorization"], "Bearer TOKEN")
        self.assertEqual(headers1["Content-Type"], "application/json")


class TestGetBoomToken(unittest.TestCase):
    """
    Tests for BoomClient._get_boom_token credential handling
    """

    def test_missing_user_raises(self):
        client = BoomClient()
        with (
            mock.patch("blastwave.query.boom.load_dotenv"),
            mock.patch.dict("os.environ", {}, clear=True),
        ):
            with self.assertRaises(BOOMCredentialsError):
                client._get_boom_token()

    def test_missing_password_raises(self):
        client = BoomClient()
        with (
            mock.patch("blastwave.query.boom.load_dotenv"),
            mock.patch.dict("os.environ", {"BOOM_API_USER": "user"}, clear=True),
        ):
            with self.assertRaises(BOOMCredentialsError):
                client._get_boom_token()

    def test_valid_credentials_fetch_fresh_token(self):
        client = BoomClient()
        with (
            mock.patch("blastwave.query.boom.load_dotenv"),
            mock.patch.dict(
                "os.environ",
                {"BOOM_API_USER": "user", "BOOM_API_PASSWORD": "pass"},
                clear=True,
            ),
            mock.patch.object(
                client, "get_fresh_token", return_value="FRESH_TOKEN"
            ) as get_fresh,
        ):
            token = client._get_boom_token()

        get_fresh.assert_called_once_with("user", "pass")
        self.assertEqual(token, "FRESH_TOKEN")


class TestGetFreshToken(unittest.TestCase):
    """
    Tests for BoomClient.get_fresh_token
    """

    def test_success_returns_access_token(self):
        client = BoomClient()
        with mock.patch("blastwave.query.boom.requests.post") as post:
            post.return_value = mock_response({"access_token": "abc123"})
            token = client.get_fresh_token("user", "pass")
        self.assertEqual(token, "abc123")

    def test_failure_raises_credentials_error(self):
        client = BoomClient()
        with mock.patch("blastwave.query.boom.requests.post") as post:
            response = mock.Mock(status_code=401, text="unauthorized")
            post.return_value = response
            with self.assertRaises(BOOMCredentialsError):
                client.get_fresh_token("user", "wrong")


class TestQueryAndCount(unittest.TestCase):
    """
    Tests for BoomClient.query / count
    """

    def test_query_builds_boom_query_and_hits_find_endpoint(self):
        client = BoomClient()
        with mock.patch.object(client, "api") as api:
            api.return_value = mock_response({"data": [{"ra": 1.0}]})
            res = client.query(
                {"catalog_name": "milliquas_v8", "filter": {"ra": {"$gt": 0}}}
            )

        self.assertEqual(res, [{"ra": 1.0}])
        args, kwargs = api.call_args
        self.assertEqual(args[0], "post")
        self.assertEqual(args[1], "queries/find")
        self.assertEqual(kwargs["data"]["catalog_name"], "milliquas_v8")

    def test_query_accepts_boom_query_instance(self):
        client = BoomClient()
        query = BOOMQuery(catalog_name="milliquas_v8", limit=3)
        with mock.patch.object(client, "api") as api:
            api.return_value = mock_response({"data": []})
            client.query(query)
        _, kwargs = api.call_args
        self.assertEqual(kwargs["data"]["limit"], 3)

    def test_count_hits_count_endpoint(self):
        client = BoomClient()
        with mock.patch.object(client, "api") as api:
            api.return_value = mock_response({"data": 42})
            res = client.count({"catalog_name": "milliquas_v8"})

        self.assertEqual(res, 42)
        args, _ = api.call_args
        self.assertEqual(args[1], "queries/count")


class TestPing(unittest.TestCase):
    """
    Tests for BoomClient.ping
    """

    def test_calls_root_endpoint(self):
        client = BoomClient()
        with mock.patch.object(client, "api") as api:
            client.ping()
        api.assert_called_once_with("get", "")


class TestGetCatalogs(unittest.TestCase):
    """
    Tests for BoomClient.get_catalogs caching
    """

    def test_caches_result(self):
        client = BoomClient()
        with mock.patch.object(client, "api") as api:
            api.return_value = mock_response(
                {"data": [{"name": "milliquas_v8"}, {"name": "CatWISE2020"}]}
            )
            cats1 = client.get_catalogs()
            cats2 = client.get_catalogs()

        api.assert_called_once()
        self.assertEqual(cats1, ["milliquas_v8", "CatWISE2020"])
        self.assertIs(cats1, cats2)


class TestGetEntryCount(unittest.TestCase):
    """
    Tests for BoomClient.get_entry_count
    """

    def test_hits_estimated_count_endpoint(self):
        client = BoomClient()
        with mock.patch.object(client, "api") as api:
            api.return_value = mock_response({"data": 2224655225})
            count = client.get_entry_count("CatWISE2020")

        self.assertEqual(count, 2224655225)
        args, kwargs = api.call_args
        self.assertEqual(args[1], "queries/estimated_count")
        self.assertEqual(kwargs["data"], {"catalog_name": "CatWISE2020"})

    def test_requires_catalog(self):
        client = BoomClient()
        with self.assertRaises(ValueError):
            client.get_entry_count()


class TestGetCatalogIndexesAndSampleData(unittest.TestCase):
    """
    Tests for BoomClient.get_catalog_indexes / get_sample_data
    """

    def test_get_catalog_indexes_uses_resolved_catalog_in_endpoint(self):
        client = BoomClient()
        with mock.patch.object(client, "api") as api:
            api.return_value = mock_response({"data": ["ra", "dec"]})
            res = client.get_catalog_indexes("CatWISE2020")

        self.assertEqual(res, ["ra", "dec"])
        args, _ = api.call_args
        self.assertEqual(args[1], "/catalogs/CatWISE2020/indexes")

    def test_get_sample_data_uses_resolved_catalog_in_endpoint(self):
        client = BoomClient()
        with mock.patch.object(client, "api") as api:
            api.return_value = mock_response({"data": [{"ra": 1.0}]})
            res = client.get_sample_data("CatWISE2020")

        self.assertEqual(res, {"ra": 1.0})
        args, _ = api.call_args
        self.assertEqual(args[1], "/catalogs/CatWISE2020/sample")


class TestConeSearch(unittest.TestCase):
    """
    Tests for BoomClient.cone_search
    """

    def test_builds_near_sphere_query(self):
        client = BoomClient()
        with mock.patch.object(client, "query") as query:
            query.return_value = [{"source_name": "J1"}]
            res = client.cone_search(
                191.6182623, -1.7184336, radius_arcsec=20.0, catalog="CatWISE2020"
            )

        self.assertEqual(res, [{"source_name": "J1"}])
        (sent_query,), _ = query.call_args
        self.assertEqual(sent_query.catalog_name, "CatWISE2020")
        near_sphere = sent_query.filter["coordinates.radec_geojson"]["$nearSphere"]
        self.assertEqual(
            near_sphere["$geometry"]["coordinates"],
            [191.6182623 - 180.0, -1.7184336],
        )
        self.assertAlmostEqual(
            near_sphere["$maxDistance"],
            BoomClient.get_near_sphere_dist(20.0),
        )

    def test_default_limit_is_one(self):
        client = BoomClient()
        with mock.patch.object(client, "query") as query:
            query.return_value = []
            client.cone_search(191.0, -1.0, catalog="CatWISE2020")

        (sent_query,), _ = query.call_args
        self.assertEqual(sent_query.limit, 1)

    def test_requires_catalog(self):
        client = BoomClient()
        with self.assertRaises(ValueError):
            client.cone_search(191.0, -1.0)


if __name__ == "__main__":
    unittest.main()
