"""
Tests for the Source model
"""

# pylint: disable=missing-function-docstring,wrong-import-position,duplicate-code

import json
import math
import tempfile
import unittest

import matplotlib
import pandas as pd

matplotlib.use("Agg")

from matplotlib import pyplot as plt

from blastwave.models import Observation, Source


def make_obs(**overrides) -> dict:
    defaults = dict(  # pylint: disable=use-dict-literal
        jd=2460100.5,
        magpsf=19.0,
        sigmapsf=0.05,
        diffmaglim=20.5,
        ra=150.0,
        dec=20.0,
        snr=8.0,
        band="g",
        survey="ZTF",
        det_type="alert",
        isdiffpos=True,
    )
    defaults.update(overrides)
    return defaults


def make_source(photometry_rows, **overrides) -> Source:
    defaults = dict(  # pylint: disable=use-dict-literal
        objectid="ZTF_TEST1",
        jd=2460100.5,
        ztfid="ZTF_TEST1",
        lsstid=None,
        ra=150.0,
        dec=20.0,
        offset=1.2,
        host_origin="PS1",
        crossmatches={"NED": []},
    )
    defaults.update(overrides)
    photometry = [Observation(**row) for row in photometry_rows]
    return Source(photometry=photometry, **defaults)  # type: ignore[arg-type]


class TestSourceComputedFieldsEmpty(unittest.TestCase):
    """
    Tests for Source computed fields with no photometry
    """

    def setUp(self):
        self.source = make_source([])

    def test_ndethist_zero(self):
        self.assertEqual(self.source.ndethist, 0)

    def test_filters_empty(self):
        self.assertEqual(self.source.filters, [])
        self.assertEqual(self.source.ndetfilters, 0)

    def test_stats_are_nan(self):
        self.assertTrue(math.isnan(self.source.jdstarthist))
        self.assertTrue(math.isnan(self.source.jdendhist))
        self.assertTrue(math.isnan(self.source.age))
        self.assertTrue(math.isnan(self.source.peak_mag))
        self.assertTrue(math.isnan(self.source.median_ra))
        self.assertTrue(math.isnan(self.source.median_dec))


class TestSourceGetDetections(unittest.TestCase):
    """
    Tests for Source.get_detections filtering logic
    """

    def setUp(self):
        rows = [
            # 0: good ZTF alert detection
            make_obs(
                jd=2460100.0, magpsf=19.0, diffmaglim=20.5, snr=8.0, isdiffpos=True
            ),
            # 1: negative subtraction -> excluded
            make_obs(jd=2460100.1, magpsf=19.0, isdiffpos=False),
            # 2: below min_snr -> excluded
            make_obs(jd=2460100.2, snr=1.0, isdiffpos=True),
            # 3: too faint relative to diffmaglim + 1 -> excluded
            make_obs(jd=2460100.3, magpsf=22.0, diffmaglim=20.5, isdiffpos=True),
            # 4: LSST forced-photometry point -> excluded by default
            make_obs(
                jd=2460100.4,
                magpsf=19.0,
                diffmaglim=20.5,
                snr=8.0,
                isdiffpos=True,
                det_type="fp",
                survey="LSST",
            ),
            # 5: ZTF forced-photometry point -> included (mask is LSST-specific)
            make_obs(
                jd=2460100.5,
                magpsf=19.0,
                diffmaglim=20.5,
                snr=8.0,
                isdiffpos=True,
                det_type="fp",
                survey="ZTF",
            ),
            # 6: missing magnitude -> excluded
            make_obs(jd=2460100.6, magpsf=float("nan"), isdiffpos=True),
        ]
        self.source = make_source(rows)

    def test_default_excludes_lsst_fp_and_bad_rows(self):
        df = self.source.get_detections()
        self.assertEqual(sorted(df["jd"].tolist()), [2460100.0, 2460100.5])

    def test_include_lsst_fp(self):
        df = self.source.get_detections(include_lsst_fp=True)
        self.assertEqual(sorted(df["jd"].tolist()), [2460100.0, 2460100.4, 2460100.5])

    def test_min_snr_threshold(self):
        df = self.source.get_detections(min_snr=100.0)
        self.assertEqual(len(df), 0)

    def test_ndethist_matches_detections(self):
        self.assertEqual(self.source.ndethist, 2)


class TestSourceComputedFieldsPopulated(unittest.TestCase):
    """
    Tests for Source computed fields with photometry present
    """

    def setUp(self):
        rows = [
            make_obs(jd=2460100.0, magpsf=19.0, band="g", ra=150.0, dec=20.0),
            make_obs(jd=2460102.0, magpsf=18.0, band="r", ra=150.2, dec=20.2),
        ]
        self.source = make_source(rows)

    def test_filters(self):
        self.assertEqual(set(self.source.filters), {"g", "r"})
        self.assertEqual(self.source.ndetfilters, 2)

    def test_time_span(self):
        self.assertAlmostEqual(self.source.jdstarthist, 2460100.0)
        self.assertAlmostEqual(self.source.jdendhist, 2460102.0)
        self.assertAlmostEqual(self.source.age, 2.0)

    def test_peak_mag_is_brightest(self):
        self.assertAlmostEqual(self.source.peak_mag, 18.0)

    def test_median_position(self):
        self.assertAlmostEqual(self.source.median_ra, 150.1)
        self.assertAlmostEqual(self.source.median_dec, 20.1)


class TestSourceCrossmatches(unittest.TestCase):
    """
    Tests for Source.get_crossmatches
    """

    def test_none_returns_empty_dict(self):
        source = make_source([], crossmatches=None)
        self.assertEqual(source.get_crossmatches(), {})

    def test_dict_is_returned_as_is(self):
        cm = {"NED": [{"name": "foo"}]}
        source = make_source([], crossmatches=cm)
        self.assertEqual(source.get_crossmatches(), cm)


class TestSourceFromZtf(unittest.TestCase):
    """
    Tests for Source.from_ztf
    """

    def setUp(self):
        self.photometry_df = pd.DataFrame(
            [
                make_obs(jd=2460100.0, band="g"),
                make_obs(jd=2460101.0, band="r"),
            ]
        )
        self.full_data = {
            "objectId": "ZTF26aaonmha",
            "candidate": {"ra": 150.0, "dec": 20.0, "jd": 2460101.0, "distpsnr1": 0.5},
            "aliases": {"LSST": ["313853517419249797"]},
            "cross_matches": {"NED": [], "PS1_DR2": []},
        }

    def test_basic_fields(self):
        source = Source.from_ztf(self.full_data, self.photometry_df)
        self.assertEqual(source.objectid, "ZTF26aaonmha")
        self.assertEqual(source.ztfid, "ZTF26aaonmha")
        self.assertEqual(source.lsstid, "313853517419249797")
        self.assertEqual(source.offset, 0.5)
        self.assertEqual(source.host_origin, "PS1")
        self.assertEqual(source.ra, 150.0)
        self.assertEqual(source.dec, 20.0)
        self.assertEqual(len(source.photometry), 2)

    def test_missing_lsst_alias_is_none(self):
        self.full_data["aliases"] = {}
        source = Source.from_ztf(self.full_data, self.photometry_df)
        self.assertIsNone(source.lsstid)


class TestSourceFromLsst(unittest.TestCase):
    """
    Tests for Source.from_lsst
    """

    def setUp(self):
        self.photometry_df = pd.DataFrame(
            [
                make_obs(jd=2460100.0, band="g", survey="LSST"),
                make_obs(jd=2460101.0, band="r", survey="LSST"),
            ]
        )
        self.full_data = {
            "objectId": "313853517419249797",
            "candidate": {"ra": 150.0, "dec": 20.0, "jd": 2460101.0},
            "aliases": {"ZTF": ["ZTF26aaonmha"]},
            "cross_matches": {
                "NED": [],
                "DESI_DR1": [
                    {
                        "distance_arcsec": 0.8,
                        "z": 0.05,
                        "z_unc": 0.001,
                        "z_tech": "spec",
                    }
                ],
                "LSPSC": [],
                "PS1_DR2": [],
            },
        }

    def test_basic_fields(self):
        source = Source.from_lsst(self.full_data, self.photometry_df)
        self.assertEqual(source.objectid, "313853517419249797")
        self.assertEqual(source.lsstid, "313853517419249797")
        self.assertEqual(source.ztfid, "ZTF26aaonmha")

    def test_redshift_pulled_from_first_matching_crossmatch(self):
        source = Source.from_lsst(self.full_data, self.photometry_df)
        self.assertEqual(source.offset, 0.8)
        self.assertEqual(source.host_origin, "DESI_DR1")
        self.assertEqual(source.redshift, 0.05)
        self.assertEqual(source.redshift_error, 0.001)
        self.assertEqual(source.redshift_origin, "DESI_DR1_spec")

    def test_no_crossmatch_leaves_host_fields_none(self):
        self.full_data["cross_matches"] = {"NED": [], "LSPSC": []}
        source = Source.from_lsst(self.full_data, self.photometry_df)
        self.assertIsNone(source.offset)
        self.assertIsNone(source.host_origin)
        self.assertIsNone(source.redshift)

    def test_missing_ztf_alias_is_none(self):
        self.full_data["aliases"] = {}
        source = Source.from_lsst(self.full_data, self.photometry_df)
        self.assertIsNone(source.ztfid)


class TestSourceJsonRoundtrip(unittest.TestCase):
    """
    Tests for Source.to_json / from_json
    """

    def setUp(self):
        rows = [
            make_obs(jd=2460100.0, magpsf=19.0, band="g", isdiffpos=True, snr=8.0),
            make_obs(jd=2460101.0, magpsf=18.5, band="r", isdiffpos=True, snr=9.0),
            # excluded by get_detections when trimming
            make_obs(jd=2460102.0, magpsf=19.0, isdiffpos=False),
        ]
        self.source = make_source(rows)

    def test_roundtrip_preserves_metadata(self):
        data = self.source.to_json()
        restored = Source.from_json(data)
        self.assertEqual(restored.objectid, self.source.objectid)
        self.assertEqual(restored.ra, self.source.ra)
        self.assertEqual(restored.dec, self.source.dec)

    def test_trim_photometry_keeps_only_detections(self):
        data = json.loads(self.source.to_json(trim_photometry=True))
        self.assertEqual(len(data["photometry"]["jd"]), 2)

    def test_no_trim_keeps_all_photometry(self):
        data = json.loads(self.source.to_json(trim_photometry=False))
        self.assertEqual(len(data["photometry"]["jd"]), 3)

    def test_computed_fields_excluded_from_json(self):
        data = json.loads(self.source.to_json())
        self.assertNotIn("ndethist", data)
        self.assertNotIn("peak_mag", data)


class TestSourceConvertToZtfStyle(unittest.TestCase):
    """
    Tests for Source.convert_to_ztfstyle
    """

    def test_last_detection_becomes_candidate(self):
        rows = [
            make_obs(jd=2460100.0, magpsf=19.0, band="g"),
            make_obs(jd=2460101.0, magpsf=18.5, band="r"),
        ]
        source = make_source(rows)
        res = source.convert_to_ztfstyle()
        self.assertEqual(res["objectId"], source.objectid)
        self.assertIn("candidate", res)
        self.assertIn("prv_candidates", res)
        self.assertEqual(res["candidate"]["jd"], 2460101.0)
        self.assertEqual(res["candidate"]["filter"], "r")
        self.assertEqual(res["candidate"]["fid"], 2)
        self.assertEqual(len(res["prv_candidates"]), 1)
        self.assertEqual(res["prv_candidates"][0]["jd"], 2460100.0)


class TestSourceParquetRoundtrip(unittest.TestCase):
    """
    Tests for Source.to_parquet / from_parquet
    """

    def test_roundtrip(self):
        rows = [
            make_obs(jd=2460100.0, magpsf=19.0, band="g"),
            make_obs(jd=2460101.0, magpsf=18.5, band="r"),
        ]
        source = make_source(rows, crossmatches={"NED": [{"name": "foo"}]})

        with tempfile.TemporaryDirectory() as tmp:
            source.to_parquet(base_path=tmp)
            restored = Source.from_parquet(source.objectid, base_path=tmp)

        self.assertEqual(restored.objectid, source.objectid)
        self.assertEqual(restored.ra, source.ra)
        self.assertEqual(restored.dec, source.dec)
        self.assertEqual(len(restored.photometry), len(source.photometry))
        self.assertEqual(restored.crossmatches, {"NED": [{"name": "foo"}]})

    def test_trim_photometry_writes_only_detections(self):
        rows = [
            make_obs(jd=2460100.0, magpsf=19.0, isdiffpos=True, snr=8.0),
            make_obs(jd=2460101.0, magpsf=18.5, isdiffpos=False),
        ]
        source = make_source(rows)

        with tempfile.TemporaryDirectory() as tmp:
            source.to_parquet(base_path=tmp, trim_photometry=True)
            restored = Source.from_parquet(source.objectid, base_path=tmp)

        self.assertEqual(len(restored.photometry), 1)

    def test_no_detections_writes_empty_photometry_table(self):
        rows = [make_obs(jd=2460100.0, isdiffpos=False)]
        source = make_source(rows)

        with tempfile.TemporaryDirectory() as tmp:
            source.to_parquet(base_path=tmp, trim_photometry=True)
            restored = Source.from_parquet(source.objectid, base_path=tmp)

        self.assertEqual(len(restored.photometry), 0)


class TestSourceLightcurveAndTrimmedPhotometry(unittest.TestCase):
    """
    Tests for Source.show_lightcurve and Source.get_trimmed_photometry
    """

    def setUp(self):
        rows = [
            make_obs(jd=2460100.0, magpsf=19.0, band="g", isdiffpos=True, snr=8.0),
            make_obs(jd=2460101.0, magpsf=18.5, band="r", isdiffpos=False),
        ]
        self.source = make_source(rows)

    def test_show_lightcurve_returns_figure(self):
        fig = self.source.show_lightcurve()
        self.assertIsInstance(fig, plt.Figure)

    def test_get_trimmed_photometry_keeps_only_detections(self):
        trimmed = self.source.get_trimmed_photometry()
        self.assertEqual(len(trimmed), 1)
        self.assertIsInstance(trimmed[0], Observation)
        self.assertAlmostEqual(trimmed[0].jd, 2460100.0)


if __name__ == "__main__":
    unittest.main()
