"""
Tests for photometry deduplication/quality-cut logic
"""

# pylint: disable=missing-function-docstring,too-many-arguments,too-many-positional-arguments

import unittest

from blastwave.utils.photometry import (
    deduplicate_lsst_photometry,
    deduplicate_ztf_photometry,
)


def ztf_row(jd, diffmaglim=20.0, psf_flux=100.0, nbad=0, drb=0.9, band="g"):
    return {
        "jd": jd,
        "diffmaglim": diffmaglim,
        "psfFlux": psf_flux,
        "psfFluxErr": 1.0,
        "nbad": nbad,
        "drb": drb,
        "snr_psf": 8.0,
        "band": band,
        "ra": 150.0,
        "dec": 20.0,
        "isdiffpos": psf_flux > 0.0,
        "magpsf": 19.0,
        "sigmapsf": 0.05,
    }


class TestDeduplicateZtfPhotometry(unittest.TestCase):
    """
    Tests for deduplicate_ztf_photometry
    """

    def setUp(self):
        self.full_data = {
            "prv_candidates": [
                ztf_row(2460100.0),  # kept
                ztf_row(2460100.1, diffmaglim=18.0),  # filtered: shallow diffmaglim
                ztf_row(2460100.2, psf_flux=-5.0),  # filtered: negative flux
            ],
            "fp_hists": [
                ztf_row(2460100.0),  # duplicate jd -> dropped before quality cuts
                ztf_row(2460100.3, nbad=2),  # filtered: nbad > 1
                ztf_row(2460100.4, drb=0.5),  # filtered: low drb
                ztf_row(2460100.5),  # kept
            ],
            "prv_nondetections": [
                ztf_row(2460100.0),  # duplicate jd -> dropped
                ztf_row(2460100.6),  # kept
            ],
        }

    def test_keeps_only_good_unique_rows(self):
        df = deduplicate_ztf_photometry(self.full_data)
        self.assertEqual(sorted(df["jd"].tolist()), [2460100.0, 2460100.5, 2460100.6])

    def test_det_type_assigned_per_source(self):
        df = deduplicate_ztf_photometry(self.full_data)
        det_types = dict(zip(df["jd"], df["det_type"]))
        self.assertEqual(det_types[2460100.0], "alert")
        self.assertEqual(det_types[2460100.5], "fp")
        self.assertEqual(det_types[2460100.6], "ul")

    def test_columns_renamed(self):
        df = deduplicate_ztf_photometry(self.full_data)
        self.assertIn("psf_flux", df.columns)
        self.assertIn("psf_flux_err", df.columns)
        self.assertIn("snr", df.columns)
        self.assertNotIn("psfFlux", df.columns)

    def test_isdiffpos_recomputed_from_flux(self):
        df = deduplicate_ztf_photometry(self.full_data)
        self.assertTrue(df["isdiffpos"].all())

    def test_sorted_by_jd(self):
        df = deduplicate_ztf_photometry(self.full_data)
        self.assertEqual(df["jd"].tolist(), sorted(df["jd"].tolist()))

    def test_no_forced_photometry(self):
        full_data = dict(self.full_data)
        full_data["fp_hists"] = []
        df = deduplicate_ztf_photometry(full_data)
        self.assertNotIn(2460100.5, df["jd"].tolist())


def lsst_row(
    jd,
    reliability=0.8,
    is_dipole=False,
    pixel_flags=False,
    centroid_flag=False,
    is_negative=False,
    psf_flux_flag=False,
    glint_trail=False,
    isdiffpos=True,
    psf_flux=80.0,
    band="g",
):
    return {
        "jd": jd,
        "reliability": reliability,
        "isDipole": is_dipole,
        "pixelFlags": pixel_flags,
        "centroid_flag": centroid_flag,
        "isNegative": is_negative,
        "psfFlux_flag": psf_flux_flag,
        "glint_trail": glint_trail,
        "isdiffpos": isdiffpos,
        "psfFlux": psf_flux,
        "psfFluxErr": 1.0,
        "band": band,
        "ra": 150.0,
        "dec": 20.0,
        "magpsf": 19.0,
        "sigmapsf": 0.05,
        "diffmaglim": 21.0,
        "snr_psf": 8.0,
    }


class TestDeduplicateLsstPhotometry(unittest.TestCase):
    """
    Tests for deduplicate_lsst_photometry
    """

    def setUp(self):
        self.full_data = {
            "prv_candidates": [
                lsst_row(2460200.0),  # kept
                lsst_row(2460200.1, reliability=0.2),  # filtered: low reliability
                lsst_row(2460200.2, is_dipole=True),  # filtered: dipole
            ],
            "fp_hists": [
                lsst_row(2460200.0),  # duplicate jd -> dropped
                lsst_row(2460200.3, psf_flux=40.0),  # kept
                lsst_row(2460200.4, pixel_flags=True),  # filtered: pixel flag
            ],
        }

    def test_keeps_only_good_unique_rows(self):
        df = deduplicate_lsst_photometry(self.full_data)
        self.assertEqual(sorted(df["jd"].tolist()), [2460200.0, 2460200.3])

    def test_det_type_assigned_per_source(self):
        df = deduplicate_lsst_photometry(self.full_data)
        det_types = dict(zip(df["jd"], df["det_type"]))
        self.assertEqual(det_types[2460200.0], "alert")
        self.assertEqual(det_types[2460200.3], "fp")

    def test_negative_detection_filtered(self):
        full_data = {
            "prv_candidates": [lsst_row(2460200.0, isdiffpos=False)],
            "fp_hists": [],
        }
        df = deduplicate_lsst_photometry(full_data)
        self.assertEqual(len(df), 0)

    def test_columns_renamed(self):
        df = deduplicate_lsst_photometry(self.full_data)
        self.assertIn("psf_flux", df.columns)
        self.assertIn("psf_flux_err", df.columns)
        self.assertNotIn("psfFlux", df.columns)

    def test_no_forced_photometry(self):
        full_data = dict(self.full_data)
        full_data["fp_hists"] = []
        df = deduplicate_lsst_photometry(full_data)
        self.assertNotIn(2460200.3, df["jd"].tolist())


if __name__ == "__main__":
    unittest.main()
