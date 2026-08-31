"""
Unit tests for AlertClient (via ZTFClient/LSSTClient), mocking out BOOM
network calls (query/cone_search) so no credentials or connectivity are
required.
"""

# pylint: disable=missing-function-docstring,unused-argument,duplicate-code

import unittest
from unittest import mock

import pandas as pd

from blastwave.models import Source
from blastwave.projections import lsst_aux_projection, ztf_aux_projection
from blastwave.query import LSSTClient, ZTFClient


def ztf_photometry_row(jd, band="g"):
    return {
        "jd": jd,
        "diffmaglim": 20.0,
        "psfFlux": 100.0,
        "psfFluxErr": 1.0,
        "nbad": 0,
        "drb": 0.9,
        "snr_psf": 8.0,
        "band": band,
        "ra": 150.0,
        "dec": 20.0,
        "isdiffpos": True,
        "magpsf": 19.0,
        "sigmapsf": 0.05,
    }


def observation_row(jd, band="g", survey="ZTF"):
    return {
        "jd": jd,
        "magpsf": 19.0,
        "sigmapsf": 0.05,
        "diffmaglim": 20.0,
        "ra": 150.0,
        "dec": 20.0,
        "snr": 8.0,
        "band": band,
        "survey": survey,
        "det_type": "alert",
        "isdiffpos": True,
    }


class TestCatalogProperties(unittest.TestCase):
    """
    Tests for AlertClient.catalog / aux_table
    """

    def test_ztf(self):
        client = ZTFClient()
        self.assertEqual(client.catalog, "ZTF_alerts")
        self.assertEqual(client.aux_table, "ZTF_alerts_aux")

    def test_lsst(self):
        client = LSSTClient()
        self.assertEqual(client.catalog, "LSST_alerts")
        self.assertEqual(client.aux_table, "LSST_alerts_aux")


class TestGetLatestAlert(unittest.TestCase):
    """
    Tests for AlertClient.get_latest_alert
    """

    def test_builds_expected_query(self):
        client = ZTFClient()
        with mock.patch.object(client, "query") as query:
            query.return_value = [{"objectId": "ZTF26aaonmha", "candidate": {}}]
            res = client.get_latest_alert("ZTF26aaonmha")

        self.assertEqual(res["objectId"], "ZTF26aaonmha")
        (sent_query,), _ = query.call_args
        self.assertEqual(sent_query.catalog_name, "ZTF_alerts")
        self.assertEqual(sent_query.filter, {"objectId": {"$eq": "ZTF26aaonmha"}})
        self.assertEqual(sent_query.limit, 1)
        self.assertEqual(sent_query.sort, {"candidate.jd": -1})

    def test_object_id_is_stringified(self):
        client = LSSTClient()
        with mock.patch.object(client, "query") as query:
            query.return_value = [{"objectId": "313853517419249797"}]
            client.get_latest_alert(313853517419249797)

        (sent_query,), _ = query.call_args
        self.assertEqual(sent_query.filter, {"objectId": {"$eq": "313853517419249797"}})

    def test_explicit_catalog_overrides_default(self):
        client = ZTFClient()
        with mock.patch.object(client, "query") as query:
            query.return_value = [{}]
            client.get_latest_alert("id", catalog="LSST_alerts")

        (sent_query,), _ = query.call_args
        self.assertEqual(sent_query.catalog_name, "LSST_alerts")


class TestGetAuxData(unittest.TestCase):
    """
    Tests for AlertClient.get_aux_data
    """

    def test_default_trim_uses_survey_projection(self):
        client = ZTFClient()
        with mock.patch.object(client, "query") as query:
            query.return_value = [{"_id": "ZTF1"}]
            client.get_aux_data("ZTF1")

        (sent_query,), _ = query.call_args
        self.assertEqual(sent_query.catalog_name, "ZTF_alerts_aux")
        self.assertEqual(sent_query.projection, ztf_aux_projection)

    def test_lsst_uses_lsst_projection(self):
        client = LSSTClient()
        with mock.patch.object(client, "query") as query:
            query.return_value = [{"_id": "L1"}]
            client.get_aux_data("L1")

        (sent_query,), _ = query.call_args
        self.assertEqual(sent_query.projection, lsst_aux_projection)

    def test_trim_false_leaves_projection_none(self):
        client = ZTFClient()
        with mock.patch.object(client, "query") as query:
            query.return_value = [{}]
            client.get_aux_data("ZTF1", trim=False)

        (sent_query,), _ = query.call_args
        self.assertIsNone(sent_query.projection)

    def test_explicit_projection_overrides_trim(self):
        client = ZTFClient()
        custom = {"aliases": 1}
        with mock.patch.object(client, "query") as query:
            query.return_value = [{}]
            client.get_aux_data("ZTF1", projection=custom)

        (sent_query,), _ = query.call_args
        self.assertEqual(sent_query.projection, custom)


class TestGetFullData(unittest.TestCase):
    """
    Tests for AlertClient.get_full_data
    """

    def test_merges_latest_alert_into_aux_data_then_updates_crossmatches(self):
        client = ZTFClient()
        with (
            mock.patch.object(
                client, "get_latest_alert", return_value={"objectId": "ZTF1", "jd": 2.0}
            ) as latest,
            mock.patch.object(
                client, "get_aux_data", return_value={"aliases": {}}
            ) as aux,
            mock.patch.object(
                client, "update_crossmatches", side_effect=lambda d: d
            ) as update,
        ):
            res = client.get_full_data("ZTF1")

        latest.assert_called_once()
        aux.assert_called_once()
        update.assert_called_once_with({"aliases": {}, "objectId": "ZTF1", "jd": 2.0})
        self.assertEqual(res["objectId"], "ZTF1")


class TestUpdateCrossmatches(unittest.TestCase):
    """
    Tests for AlertClient.update_crossmatches
    """

    def test_drops_empty_string_key_and_adds_distances(self):
        client = ZTFClient()
        aux_data = {
            "candidate": {"ra": 150.0, "dec": 20.0},
            "cross_matches": {"": [{"junk": True}], "milliquas_v8": []},
        }

        def fake_cone_search(ra, dec, catalog=None, limit=1):
            if catalog == "LSPSC":
                return [
                    {
                        "coordinates": {
                            "radec_geojson": {"coordinates": [ra - 180.0, dec]}
                        },
                        "name": "host1",
                    }
                ]
            return []

        with mock.patch.object(client, "cone_search", side_effect=fake_cone_search):
            res = client.update_crossmatches(aux_data)

        self.assertNotIn("", res["cross_matches"])
        self.assertIn("milliquas_v8", res["cross_matches"])
        self.assertEqual(len(res["cross_matches"]["LSPSC"]), 1)
        self.assertAlmostEqual(
            res["cross_matches"]["LSPSC"][0]["distance_arcsec"], 0.0, places=6
        )
        self.assertNotIn("coordinates", res["cross_matches"]["LSPSC"][0])
        self.assertIn("NED", res["cross_matches"])
        self.assertIn("PS1_DR2", res["cross_matches"])

    def test_missing_cross_matches_key_is_initialised(self):
        client = ZTFClient()
        aux_data = {"candidate": {"ra": 150.0, "dec": 20.0}}
        with mock.patch.object(client, "cone_search", return_value=[]):
            res = client.update_crossmatches(aux_data)
        self.assertEqual(res["cross_matches"], {"LSPSC": [], "NED": [], "PS1_DR2": []})


class TestGetMatchPhotometry(unittest.TestCase):
    """
    Tests for AlertClient.get_match_photometry
    """

    def test_missing_alias_returns_empty_dataframe(self):
        client = ZTFClient()
        df = client.get_match_photometry("ZTF_alerts", aliases={})
        self.assertTrue(df.empty)

    def test_present_alias_returns_labelled_photometry(self):
        client = ZTFClient()
        full_alert = {
            "prv_candidates": [ztf_photometry_row(2460100.0)],
            "fp_hists": [],
            "prv_nondetections": [],
        }
        with mock.patch.object(client, "get_full_data", return_value=full_alert):
            df = client.get_match_photometry(
                "ZTF_alerts", aliases={"ZTF": ["ZTF26aaonmha"]}
            )

        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["survey"], "ZTF")

    def test_index_error_on_empty_alias_list_returns_empty_dataframe(self):
        client = ZTFClient()
        df = client.get_match_photometry("ZTF_alerts", aliases={"ZTF": []})
        self.assertTrue(df.empty)


class TestGetAllMatchPhotometry(unittest.TestCase):
    """
    Tests for AlertClient.get_all_match_photometry
    """

    def test_concatenates_per_survey_results(self):
        client = ZTFClient()

        def fake_match_photometry(catalog, aliases):
            survey = catalog.split("_")[0]
            return pd.DataFrame([{"jd": 1.0, "survey": survey}])

        with mock.patch.object(
            client, "get_match_photometry", side_effect=fake_match_photometry
        ):
            df = client.get_all_match_photometry({"ZTF": ["a"], "LSST": ["b"]})

        self.assertEqual(set(df["survey"]), {"ZTF", "LSST"})
        self.assertEqual(len(df), 2)


class TestGetAllPhotometry(unittest.TestCase):
    """
    Tests for AlertClient.get_all_photometry
    """

    def test_no_aliases_only_base_survey_photometry(self):
        client = ZTFClient()
        full_alert = {
            "prv_candidates": [
                ztf_photometry_row(2460100.0),
                ztf_photometry_row(2460099.0),
            ],
            "fp_hists": [],
            "prv_nondetections": [],
        }
        df = client.get_all_photometry(full_alert, catalog="ZTF_alerts")

        self.assertEqual(len(df), 2)
        self.assertTrue((df["survey"] == "ZTF").all())
        self.assertEqual(df["jd"].tolist(), sorted(df["jd"].tolist()))

    def test_with_aliases_appends_match_photometry(self):
        client = ZTFClient()
        full_alert = {
            "prv_candidates": [ztf_photometry_row(2460100.0)],
            "fp_hists": [],
            "prv_nondetections": [],
            "aliases": {"LSST": ["313853517419249797"]},
        }
        match_df = pd.DataFrame([{"jd": 2460099.0, "survey": "LSST"}])

        with mock.patch.object(
            client, "get_all_match_photometry", return_value=match_df
        ):
            df = client.get_all_photometry(full_alert, catalog="ZTF_alerts")

        self.assertEqual(len(df), 2)
        self.assertEqual(set(df["survey"]), {"ZTF", "LSST"})
        self.assertEqual(df["jd"].tolist(), sorted(df["jd"].tolist()))

    def test_empty_match_photometry_is_not_appended(self):
        client = ZTFClient()
        full_alert = {
            "prv_candidates": [ztf_photometry_row(2460100.0)],
            "fp_hists": [],
            "prv_nondetections": [],
            "aliases": {"LSST": []},
        }
        with mock.patch.object(
            client, "get_all_match_photometry", return_value=pd.DataFrame()
        ):
            df = client.get_all_photometry(full_alert, catalog="ZTF_alerts")

        self.assertEqual(len(df), 1)


class TestGetSource(unittest.TestCase):
    """
    Tests for AlertClient.get_source, the top-level pipeline used in the
    ZTF/LSST client notebooks.
    """

    def test_ztf_client_builds_source_via_from_ztf(self):
        client = ZTFClient()
        full_data = {
            "objectId": "ZTF26aaonmha",
            "candidate": {"ra": 150.0, "dec": 20.0, "jd": 2460100.0, "distpsnr1": 0.5},
            "aliases": {},
            "cross_matches": {},
        }
        photometry_df = pd.DataFrame([observation_row(2460100.0)])

        with (
            mock.patch.object(
                client, "get_full_data", return_value=full_data
            ) as get_full,
            mock.patch.object(
                client, "get_all_photometry", return_value=photometry_df
            ) as get_photometry,
        ):
            source = client.get_source("ZTF26aaonmha")

        get_full.assert_called_once()
        get_photometry.assert_called_once_with(full_data, catalog="ZTF_alerts")
        self.assertIsInstance(source, Source)
        self.assertEqual(source.objectid, "ZTF26aaonmha")

    def test_lsst_client_builds_source_via_from_lsst(self):
        client = LSSTClient()
        full_data = {
            "objectId": "313853517419249797",
            "candidate": {"ra": 150.0, "dec": 20.0, "jd": 2460100.0},
            "aliases": {},
            "cross_matches": {},
        }
        photometry_df = pd.DataFrame([observation_row(2460100.0, survey="LSST")])

        with (
            mock.patch.object(client, "get_full_data", return_value=full_data),
            mock.patch.object(client, "get_all_photometry", return_value=photometry_df),
        ):
            source = client.get_source("313853517419249797")

        self.assertIsInstance(source, Source)
        self.assertEqual(source.objectid, "313853517419249797")
        self.assertEqual(source.lsstid, "313853517419249797")


if __name__ == "__main__":
    unittest.main()
